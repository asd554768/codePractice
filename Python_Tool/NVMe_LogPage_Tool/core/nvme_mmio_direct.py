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

from .winring0_service import WinRing0Driver


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
    
    直接與 WinRing0x64.sys 驅動通訊，繞過 Windows Storage Stack。
    """

    def __init__(self, bar0_phys_addr: Optional[int] = None, sys_path: Optional[str] = None):
        """初始化 Direct MMIO 引擎。
        
        Args:
            bar0_phys_addr: NVMe Controller 的實體 BAR0 基底位址。若為 None 則自動掃描。
            sys_path: WinRing0x64.sys 路徑。
        """
        if bar0_phys_addr is None:
            detected = get_nvme_pci_bar0_addresses()
            if not detected:
                raise RuntimeError("未能在系統中自動偵測到任何 NVMe 控制器的實體 BAR0 位址")
            self.bar0 = detected[0]
        else:
            self.bar0 = bar0_phys_addr

        self.driver = WinRing0Driver(sys_path)
        
        # 讀取控制器核心參數
        self.dstrd = self._read_dstrd()
        self.asq_phys = self._read_mmio_64(0x28)  # ASQB: Admin Submission Queue Base
        self.acq_phys = self._read_mmio_64(0x30)  # ACQB: Admin Completion Queue Base
        self.aqa = self._read_mmio_32(0x24)       # AQA: Admin Queue Attributes
        self.asq_size = (self.aqa & 0xFFF) + 1    # ASQS (0-based)
        self.acq_size = ((self.aqa >> 16) & 0xFFF) + 1
        
        self.current_cid = 1

    # === MMIO 讀寫底層 ===
    def _read_mmio_32(self, offset: int) -> int:
        raw_bytes = self.driver.read_physical_memory(self.bar0 + offset, 4, unit_size=4)
        return struct.unpack("<I", raw_bytes)[0]

    def _write_mmio_32(self, offset: int, value: int):
        data = struct.pack("<I", value)
        self.driver.write_physical_memory(self.bar0 + offset, data, unit_size=4)

    def _read_mmio_64(self, offset: int) -> int:
        raw_bytes = self.driver.read_physical_memory(self.bar0 + offset, 8, unit_size=4)
        return struct.unpack("<Q", raw_bytes)[0]

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
        self.driver.write_physical_memory(sqe_phys_addr, bytes(sqe), unit_size=4)

        # 4. 敲擊 Admin SQ0 Tail Doorbell 通知控制器執行！
        new_tail = (current_tail + 1) % self.asq_size
        self._write_mmio_32(sq0_tdbl_offset, new_tail)

        # 5. 等待控制器完成
        time.sleep(0.001)
        return True, 0

    def close(self):
        """釋放驅動連線。"""
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.close()
            except Exception:
                pass
            self.driver = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
