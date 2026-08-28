"""Direct PCIe MMIO Direct NVMe 引擎單元測試。"""
import unittest
from unittest.mock import patch, MagicMock, call
import ctypes
import struct
import sys
import os

# 確保專案根目錄在 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.nvme_mmio_direct import NvmeMmioDirect, get_nvme_pci_bar0_addresses


class TestNvmeMmioDirect(unittest.TestCase):
    """測試 NvmeMmioDirect 的暫存器解析、SQE 結構組裝與 Doorbell 門鈴觸發。"""

    @patch("subprocess.run")
    def test_get_nvme_pci_bar0_addresses(self, mock_subproc):
        mock_subproc.return_value = MagicMock(
            stdout="2775580672\n2775580672\n",
            returncode=0
        )
        addrs = get_nvme_pci_bar0_addresses()
        self.assertEqual(addrs, [2775580672])  # 自動去重

    @patch("ctypes.windll.LoadLibrary")
    def test_mmio_direct_init_and_register_reads(self, mock_load):
        mock_ols = MagicMock()
        mock_ols.InitializeOls.return_value = True
        mock_load.return_value = mock_ols

        # 模擬 MMIO 讀取回傳值：
        # offset 0x04 (CAP high): DSTRD = 0
        # offset 0x24 (AQA): ASQS = 31 (32 entries), ACQS = 31
        # offset 0x28 (ASQB low): 0x10000000
        # offset 0x2C (ASQB high): 0x00000001 -> ASQB = 0x110000000
        # offset 0x30 (ACQB low): 0x20000000
        # offset 0x34 (ACQB high): 0x00000001 -> ACQB = 0x120000000
        def fake_read_phys(addr, buf, size, unit):
            offset = addr - 0xA5700000
            val = 0
            if offset == 0x04:
                val = 0x00000000  # DSTRD = 0
            elif offset == 0x24:
                val = 0x001F001F  # ASQS=31, ACQS=31
            elif offset == 0x28:
                val = 0x10000000
            elif offset == 0x2C:
                val = 0x00000001
            elif offset == 0x30:
                val = 0x20000000
            elif offset == 0x34:
                val = 0x00000001
            elif offset == 0x1000:
                val = 5           # Current Tail = 5
            ctypes.memmove(buf, struct.pack("<I", val), 4)
            return True

        mock_ols.ReadPhysicalMemory.side_effect = fake_read_phys

        with patch("os.path.exists", return_value=True):
            engine = NvmeMmioDirect(bar0_phys_addr=0xA5700000)

        self.assertEqual(engine.dstrd, 0)
        self.assertEqual(engine.asq_size, 32)
        self.assertEqual(engine.asq_phys, 0x110000000)
        self.assertEqual(engine.acq_phys, 0x120000000)

    @patch("ctypes.windll.LoadLibrary")
    def test_send_raw_get_log_page_sqe_and_doorbell(self, mock_load):
        mock_ols = MagicMock()
        mock_ols.InitializeOls.return_value = True
        mock_load.return_value = mock_ols

        written_sqe = None
        doorbell_writes = []

        def fake_read_phys(addr, buf, size, unit):
            offset = addr - 0xA5700000
            val = 0
            if offset == 0x04:
                val = 0
            elif offset == 0x24:
                val = 0x001F001F
            elif offset == 0x28:
                val = 0x10000000
            elif offset == 0x2C:
                val = 0x00000001
            elif offset == 0x30:
                val = 0x20000000
            elif offset == 0x34:
                val = 0x00000001
            elif offset == 0x1000:
                val = 2  # Current Tail = 2
            ctypes.memmove(buf, struct.pack("<I", val), 4)
            return True

        def fake_write_phys(addr, buf, size, unit):
            nonlocal written_sqe
            offset = addr - 0xA5700000
            if addr >= 0x110000000:
                # 寫入 ASQ
                written_sqe = bytes(ctypes.string_at(buf, size))
            elif offset == 0x1000:
                # 寫入 Doorbell
                val = struct.unpack("<I", ctypes.string_at(buf, size))[0]
                doorbell_writes.append(val)
            return True

        mock_ols.ReadPhysicalMemory.side_effect = fake_read_phys
        mock_ols.WritePhysicalMemory.side_effect = fake_write_phys

        with patch("os.path.exists", return_value=True):
            engine = NvmeMmioDirect(bar0_phys_addr=0xA5700000)
            # 下發 LID=0xF0, NUMD=0x00 (4 Bytes)
            success, cid = engine.send_raw_get_log_page(
                lid=0xF0,
                numd=0x00,
                data_buffer_phys_addr=0x200000000,
                nsid=0xFFFFFFFF
            )

        self.assertTrue(success)
        self.assertIsNotNone(written_sqe)
        self.assertEqual(len(written_sqe), 64)

        # 驗證 SQE 內容：
        # CDW0: Opcode = 0x02
        opc = struct.unpack_from("<B", written_sqe, 0)[0]
        self.assertEqual(opc, 0x02)

        # CDW1: NSID = 0xFFFFFFFF
        nsid = struct.unpack_from("<I", written_sqe, 4)[0]
        self.assertEqual(nsid, 0xFFFFFFFF)

        # CDW6/7: PRP1 = 0x200000000
        prp1 = struct.unpack_from("<Q", written_sqe, 24)[0]
        self.assertEqual(prp1, 0x200000000)

        # CDW10: 必須包含 NUMDL = 0x00, LID = 0xF0 -> 0x000000F0 (完全無 0x7F 篡改！)
        cdw10 = struct.unpack_from("<I", written_sqe, 40)[0]
        self.assertEqual(cdw10, 0x000000F0, f"CDW10 應為 0x000000F0，實際為 0x{cdw10:08X}")
        numdl = (cdw10 >> 16) & 0xFFFF
        self.assertEqual(numdl, 0x00, f"NUMDL 應為 0x00，實際為 0x{numdl:04X}")

        # 驗證 Doorbell 門鈴敲擊：Tail 從 2 更新為 3
        self.assertIn(3, doorbell_writes, "Admin SQ0 Tail Doorbell 應寫入 new_tail=3")


if __name__ == "__main__":
    unittest.main()
