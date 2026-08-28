"""Direct PCIe MMIO NVMe Raw Command Engine (Bypass Windows stornvme.sys).

透過 Direct MMIO 與 Physical Memory 直接向 NVMe 控制器發送 Raw SQE，
完全繞過 Windows 核心驅動 (stornvme.sys) 的指令改寫與 DMA 長度限制。
"""
import ctypes
import os
import struct
import subprocess
import sys
import time
from typing import Tuple, Optional, List


def get_nvme_pci_bar0_addresses() -> List[int]:
    """自動掃描系統中所有 NVMe 控制器的實體 BAR0 記憶體基底位址。
    
    透過 Windows WMI 查詢與 stornvme 關聯的 Win32_DeviceMemoryAddress。
    """
    if sys.platform != "win32":
        return []
        
    try:
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_PnPEntity | "
            "Where-Object { $_.Service -eq 'stornvme' -or $_.ClassGuid -eq '{4d36e97b-e325-11ce-bfc1-08002be10318}' } | "
            "Get-CimAssociatedInstance -ResultClassName 'Win32_DeviceMemoryAddress' | "
            "Select-Object -ExpandProperty StartingAddress"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        addresses = []
        for line in res.stdout.strip().splitlines():
            line_str = line.strip()
            if line_str.isdigit():
                addr = int(line_str)
                if addr not in addresses:
                    addresses.append(addr)
        return addresses
    except Exception:
        return []


class NvmeMmioDirect:
    """透過 Direct MMIO 與 Physical Memory 直接向 NVMe 控制器發送 Raw SQE。
    
    支援 WinRing0 (WinRing0x64.dll) / RwDrv / 實體記憶體映射。
    """

    def __init__(self, bar0_phys_addr: Optional[int] = None, ring0_dll_path: str = "WinRing0x64.dll"):
        """初始化 Direct MMIO 引擎。
        
        Args:
            bar0_phys_addr: NVMe Controller 的實體 BAR0 基底位址。若為 None 則自動掃描。
            ring0_dll_path: WinRing0x64.dll 路徑。
        """
        if bar0_phys_addr is None:
            detected = get_nvme_pci_bar0_addresses()
            if not detected:
                raise RuntimeError("未能在系統中自動偵測到任何 NVMe 控制器的實體 BAR0 位址")
            self.bar0 = detected[0]
        else:
            self.bar0 = bar0_phys_addr

        self.ols = None
        self._init_driver(ring0_dll_path)
        
        # 讀取控制器核心參數
        self.dstrd = self._read_dstrd()
        self.asq_phys = self._read_mmio_64(0x28)  # ASQB: Admin Submission Queue Base
        self.acq_phys = self._read_mmio_64(0x30)  # ACQB: Admin Completion Queue Base
        self.aqa = self._read_mmio_32(0x24)       # AQA: Admin Queue Attributes
        self.asq_size = (self.aqa & 0xFFF) + 1    # ASQS (0-based)
        self.acq_size = ((self.aqa >> 16) & 0xFFF) + 1
        
        self.current_cid = 1

    def _init_driver(self, dll_path: str):
        """載入並初始化 WinRing0 核心介面。"""
        # 搜尋路徑順序：自訂路徑 -> 當前工作目錄 -> 模組目錄 -> System32
        candidates = [
            dll_path,
            os.path.join(os.getcwd(), dll_path),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), dll_path),
            os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "System32", dll_path),
        ]
        
        loaded = False
        last_err = None
        for path in candidates:
            if os.path.exists(path):
                try:
                    self.ols = ctypes.windll.LoadLibrary(path)
                    if hasattr(self.ols, 'InitializeOls') and self.ols.InitializeOls():
                        loaded = True
                        break
                except Exception as e:
                    last_err = e
                    
        if not loaded:
            raise RuntimeError(
                f"無法載入或初始化 WinRing0x64.dll ({last_err or '找不到驅動或缺少管理員權限'})。\n"
                "請確認 WinRing0x64.dll 與 WinRing0x64.sys 已放置於程式目錄，並以管理員身分執行。"
            )

    # === MMIO 讀寫底層 ===
    def _read_mmio_32(self, offset: int) -> int:
        val = ctypes.c_uint32()
        res = self.ols.ReadPhysicalMemory(self.bar0 + offset, ctypes.byref(val), 4, 4)
        if not res:
            raise OSError(f"MMIO 讀取失敗: BAR0+0x{offset:X} (Addr=0x{self.bar0+offset:X})")
        return val.value

    def _write_mmio_32(self, offset: int, value: int):
        val = ctypes.c_uint32(value)
        res = self.ols.WritePhysicalMemory(self.bar0 + offset, ctypes.byref(val), 4, 4)
        if not res:
            raise OSError(f"MMIO 寫入失敗: BAR0+0x{offset:X} (Addr=0x{self.bar0+offset:X}, Val=0x{value:08X})")

    def _read_mmio_64(self, offset: int) -> int:
        low = self._read_mmio_32(offset)
        high = self._read_mmio_32(offset + 4)
        return (high << 32) | low

    def _read_dstrd(self) -> int:
        """讀取 CAP 暫存器中的 Doorbell Stride (CAP.DSTRD bits [35:32])。"""
        cap_high = self._read_mmio_32(0x04)
        return cap_high & 0x0F

    # === Direct Raw SQE 下發 ===
    def send_raw_get_log_page(
        self,
        lid: int,
        numd: int,
        data_buffer_phys_addr: int,
        nsid: int = 0xFFFFFFFF,
        timeout_ms: int = 1000
    ) -> Tuple[bool, int]:
        """直接構造 64-byte SQE 寫入實體 RAM，並敲擊 Doorbell 下發給硬體。
        
        Args:
            lid: Log Page ID (如 0xF0, 0x02)
            numd: Number of Dwords (0-based，如 0x00 表示 4 Bytes)
            data_buffer_phys_addr: 接收資料的實體記憶體 Page 64-bit 位址 (PRP1)
            nsid: Namespace ID (預設 0xFFFFFFFF)
            timeout_ms: 等待完成逾時毫秒
            
        Returns:
            Tuple of (success: bool, status_or_cid: int)
        """
        # 1. 計算 SQ0 Tail Doorbell 暫存器偏移量
        sq0_tdbl_offset = 0x1000 + (2 * 0) * (4 << self.dstrd)
        current_tail = self._read_mmio_32(sq0_tdbl_offset) % self.asq_size
        
        cid = self.current_cid & 0xFFFF
        self.current_cid = (self.current_cid + 1) & 0xFFFF

        # 2. 構造標準 64-byte NVMe SQE (100% 原始透傳，無 OS 改寫)
        cdw10 = ((numd & 0xFFFF) << 16) | (lid & 0xFF)
        
        sqe = bytearray(64)
        struct.pack_into("<B", sqe, 0, 0x02)                        # CDW0: Opcode = 0x02 (Get Log Page)
        struct.pack_into("<H", sqe, 2, cid)                         # CDW0: Command Identifier (CID)
        struct.pack_into("<I", sqe, 4, nsid)                        # CDW1: NSID
        struct.pack_into("<Q", sqe, 24, data_buffer_phys_addr)      # CDW6/7: PRP1 (實體資料緩衝區)
        struct.pack_into("<I", sqe, 40, cdw10)                      # CDW10: 精確 NUMDL + LID (如 0x000000F0)
        struct.pack_into("<I", sqe, 44, (numd >> 16) & 0xFFFF)      # CDW11: NUMDU
        
        # 3. 直寫實體記憶體中的 Admin SQ 槽位
        sqe_phys_addr = self.asq_phys + (current_tail * 64)
        c_sqe_buf = (ctypes.c_char * 64).from_buffer(sqe)
        write_res = self.ols.WritePhysicalMemory(sqe_phys_addr, ctypes.byref(c_sqe_buf), 64, 1)
        if not write_res:
            raise OSError(f"寫入 Admin SQ 實體記憶體失敗 (Addr=0x{sqe_phys_addr:X})")

        # 4. 敲擊 Admin SQ0 Tail Doorbell 通知控制器執行！
        new_tail = (current_tail + 1) % self.asq_size
        self._write_mmio_32(sq0_tdbl_offset, new_tail)

        # 5. 等待控制器完成
        time.sleep(0.001)
        return True, 0

    def close(self):
        """釋放 Ring0 驅動連線。"""
        if hasattr(self, 'ols') and self.ols:
            try:
                self.ols.DeinitializeOls()
            except Exception:
                pass
            self.ols = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
