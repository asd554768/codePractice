"""GetLogPageCommand 單元測試。"""
import unittest
import sys
import os

# 確保專案根目錄在 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.commands import GetLogPageCommand


class TestGetLogPageCommand(unittest.TestCase):
    """測試 NVMe Get Log Page 指令 CDW 生成與 Dword 計算邏輯。"""

    def test_dword_alignment_and_numd(self):
        # 1 Byte -> 1 Dword (4 Bytes), NUMD = 0
        cmd1 = GetLogPageCommand(lid=0x02, length_bytes=1)
        self.assertEqual(cmd1.aligned_length, 4)
        self.assertEqual(cmd1.numd, 0)

        # 4 Bytes -> 1 Dword (4 Bytes), NUMD = 0
        cmd4 = GetLogPageCommand(lid=0x02, length_bytes=4)
        self.assertEqual(cmd4.aligned_length, 4)
        self.assertEqual(cmd4.numd, 0)

        # 5 Bytes -> 2 Dwords (8 Bytes), NUMD = 1
        cmd5 = GetLogPageCommand(lid=0x02, length_bytes=5)
        self.assertEqual(cmd5.aligned_length, 8)
        self.assertEqual(cmd5.numd, 1)

        # 512 Bytes -> 128 Dwords (512 Bytes), NUMD = 127
        cmd512 = GetLogPageCommand(lid=0x02, length_bytes=512)
        self.assertEqual(cmd512.aligned_length, 512)
        self.assertEqual(cmd512.numd, 127)

        # 1024 Bytes -> 256 Dwords (1024 Bytes), NUMD = 255
        cmd1024 = GetLogPageCommand(lid=0x02, length_bytes=1024)
        self.assertEqual(cmd1024.aligned_length, 1024)
        self.assertEqual(cmd1024.numd, 255)

    def test_cdw10_construction(self):
        # LID = 0x02, Length = 512 (NUMD=127), RAE = 0, LSP = 0
        # CDW10 = (127 << 16) | (0 << 15) | (0 << 8) | 0x02 = 0x007F0002
        cmd = GetLogPageCommand(lid=0x02, length_bytes=512, rae=0, lsp=0)
        self.assertEqual(cmd.cdw10, 0x007F0002)

        # 測試 RAE = 1, LSP = 0x5, LID = 0xC0, Length = 8 (NUMD = 1)
        # NUMDL = 1
        # CDW10 = (1 << 16) | (1 << 15) | (5 << 8) | 0xC0
        cmd_flags = GetLogPageCommand(lid=0xC0, length_bytes=8, rae=1, lsp=0x5)
        expected_cdw10 = (1 << 16) | (1 << 15) | (0x5 << 8) | 0xC0
        self.assertEqual(cmd_flags.cdw10, expected_cdw10)

    def test_cdw11_large_transfer(self):
        # 測試大於 64K Dwords 的傳輸 (例如 65536 Dwords = 262144 Bytes, NUMD = 65535, numdu = 0)
        # 65537 Dwords = 262148 Bytes, NUMD = 65536 = 0x00010000 -> numdl = 0, numdu = 1
        cmd_large = GetLogPageCommand(lid=0x07, length_bytes=262148)
        self.assertEqual(cmd_large.numd, 65536)
        self.assertEqual(cmd_large.cdw11, 1)
        self.assertEqual(cmd_large.cdw10 & 0xFFFF0000, 0)

    def test_cdw12_cdw13_lpo(self):
        # 測試 64-bit Log Page Offset (LPO)
        # lpo = 0x123456789ABCDEF0
        lpo = 0x123456789ABCDEF0
        cmd_lpo = GetLogPageCommand(lid=0x07, length_bytes=512, lpo=lpo)
        self.assertEqual(cmd_lpo.cdw12, 0x9ABCDEF0)
        self.assertEqual(cmd_lpo.cdw13, 0x12345678)

    def test_direct_numd_specification(self):
        # NUMD = 0x7F -> length_bytes = 512
        cmd = GetLogPageCommand(lid=0x02, numd_val=0x7F)
        self.assertEqual(cmd.numd, 127)
        self.assertEqual(cmd.numdl, 127)
        self.assertEqual(cmd.length_bytes, 512)
        self.assertEqual(cmd.aligned_length, 512)
        self.assertEqual(cmd.cdw10, 0x007F0002)

        # NUMD = 0x01 -> length_bytes = 8
        cmd8 = GetLogPageCommand(lid=0xC0, numd_val=1)
        self.assertEqual(cmd8.numd, 1)
        self.assertEqual(cmd8.length_bytes, 8)
        self.assertEqual(cmd8.cdw10, 0x000100C0)


if __name__ == "__main__":
    unittest.main()
