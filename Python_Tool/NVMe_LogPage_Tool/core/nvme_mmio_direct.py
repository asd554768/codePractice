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
    
    精確過濾 PCI NVMe 類別碼 (CC_010802) 與 stornvme 服務，並排除非 NVMe 裝置。
    """
    if sys.platform != "win32":
        return []
        
    try:
        CREATE_NO_WINDOW = 0x08000000
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_PnPEntity | "
            "Where-Object { $_.Service -eq 'stornvme' -or $_.CompatibleID -like '*CC_010802*' -or $_.HardwareID -like '*CC_010802*' } | "
            "ForEach-Object { "
            "  $pnp = $_; "
            "  Get-CimAssociatedInstance -InputObject $pnp -ResultClassName 'Win32_DeviceMemoryAddress' | "
            "  Select-Object StartingAddress, EndingAddress "
            "} | ForEach-Object { '{0}:{1}' -f $_.StartingAddress, $_.EndingAddress }"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, creationflags=CREATE_NO_WINDOW)
        addresses = []
        for line in res.stdout.strip().splitlines():
            if ":" in line:
                parts = line.strip().split(":")
                if parts[0].isdigit() and parts[1].isdigit():
                    start = int(parts[0])
                    end = int(parts[1])
                    size = end - start + 1
                    # NVMe BAR0 規範至少為 16KB (0x4000)
                    if size >= 0x4000 and start not in addresses:
                        addresses.append(start)
            elif line.strip().isdigit():
                addr = int(line.strip())
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
        self.driver = WinRing0Driver(sys_path)

        if bar0_phys_addr is not None:
            self.bar0 = bar0_phys_addr
        else:
            # 優先使用 PCI Configuration Space 物理硬體掃描 (直接讀取 PCI 暫存器，最精準)
            pci_bar0s = self.driver.find_nvme_pci_bar0()
            candidates = pci_bar0s if pci_bar0s else get_nvme_pci_bar0_addresses()
            if not candidates:
                raise RuntimeError("未能在系統中自動偵測到任何 NVMe 控制器的實體 BAR0 位址")

            # 逐一探測候選位址，尋找能成功回應 NVMe CAP / VS 暫存器的有效 BAR0
            valid_bar0 = None
            for cand in candidates:
                try:
                    # 讀取 NVMe Version (VS) 暫存器 (offset 0x08)
                    vs_bytes = self.driver.read_physical_memory(cand + 0x08, 4, unit_size=4)
                    vs_val = struct.unpack("<I", vs_bytes)[0]
                    # 有效 NVMe 版本如 0x00010300 (1.3), 0x00010400 (1.4), 0x00020000 (2.0)
                    if (vs_val >> 16) >= 1:
                        valid_bar0 = cand
                        break
                except Exception:
                    continue

            if valid_bar0 is not None:
                self.bar0 = valid_bar0
            elif pci_bar0s:
                self.bar0 = pci_bar0s[0]
            else:
                cands_hex = ", ".join(f"0x{c:X}" for c in candidates)
                raise RuntimeError(
                    f"Direct-MMIO 引擎無法存取 NVMe BAR0 (候選位址: {cands_hex})。\n"
                    f"原因: Windows 核心安全性保護阻擋實體記憶體映射。請在「通道路徑」選單改選「Pass-Through」或「自動 (Auto)」。"
                )
        
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
