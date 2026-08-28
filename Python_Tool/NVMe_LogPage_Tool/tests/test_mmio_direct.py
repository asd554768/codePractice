"""Direct PCIe MMIO Direct NVMe 引擎單元測試。"""
import unittest
from unittest.mock import patch, MagicMock, call
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
        self.assertEqual(addrs, [2775580672])

    @patch("core.nvme_mmio_direct.WinRing0Driver")
    def test_mmio_direct_init_and_register_reads(self, mock_driver_cls):
        mock_drv = MagicMock()
        mock_driver_cls.return_value = mock_drv

        # 模擬 MMIO 讀取回傳值：
        def fake_read_phys(addr, size, unit_size=4):
            offset = addr - 0xA5700000
            val = 0
            if offset == 0x04:
                val = 0x00000000  # DSTRD = 0
            elif offset == 0x24:
                val = 0x001F001F  # ASQS=31, ACQS=31
            elif offset == 0x28:
                return struct.pack("<Q", 0x110000000)
            elif offset == 0x30:
                return struct.pack("<Q", 0x120000000)
            elif offset == 0x1000:
                val = 5           # Current Tail = 5
            return struct.pack("<I", val)

        mock_drv.read_physical_memory.side_effect = fake_read_phys

        engine = NvmeMmioDirect(bar0_phys_addr=0xA5700000)

        self.assertEqual(engine.dstrd, 0)
        self.assertEqual(engine.asq_size, 32)
        self.assertEqual(engine.asq_phys, 0x110000000)
        self.assertEqual(engine.acq_phys, 0x120000000)

    @patch("core.nvme_mmio_direct.WinRing0Driver")
    def test_send_raw_get_log_page_sqe_and_doorbell(self, mock_driver_cls):
        mock_drv = MagicMock()
        mock_driver_cls.return_value = mock_drv

        written_sqe = None
        doorbell_writes = []

        def fake_read_phys(addr, size, unit_size=4):
            offset = addr - 0xA5700000
            val = 0
            if offset == 0x04:
                val = 0
            elif offset == 0x24:
                val = 0x001F001F
            elif offset == 0x28:
                return struct.pack("<Q", 0x110000000)
            elif offset == 0x30:
                return struct.pack("<Q", 0x120000000)
            elif offset == 0x1000:
                val = 2  # Current Tail = 2
            return struct.pack("<I", val)

        def fake_write_phys(addr, data, unit_size=4):
            nonlocal written_sqe
            offset = addr - 0xA5700000
            if addr >= 0x110000000:
                written_sqe = data
            elif offset == 0x1000:
                doorbell_writes.append(struct.unpack("<I", data)[0])
            return True

        mock_drv.read_physical_memory.side_effect = fake_read_phys
        mock_drv.write_physical_memory.side_effect = fake_write_phys

        engine = NvmeMmioDirect(bar0_phys_addr=0xA5700000)
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
