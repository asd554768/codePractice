"""csv_parser 模組單元測試。"""
import unittest
import tempfile
import os
import sys

# 確保專案根目錄在 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from runner.csv_parser import parse_csv, CsvTestCase


class TestCsvParser(unittest.TestCase):
    """測試 CSV 測試案例解析與容錯處理。"""

    def _create_temp_csv(self, content: str, encoding: str = "utf-8") -> str:
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
        return path

    def test_standard_csv_with_hex_and_dec(self):
        content = """LID,Length
0x02,512
1,4096
0x03,512
0x05,1024
0xC0,64
"""
        path = self._create_temp_csv(content)
        try:
            cases = parse_csv(path)
            self.assertEqual(len(cases), 5)
            
            # Case 1: 0x02, 512
            self.assertEqual(cases[0].index, 1)
            self.assertEqual(cases[0].lid, 0x02)
            self.assertEqual(cases[0].length_bytes, 512)
            self.assertEqual(cases[0].lid_name, "SMART_Health_Information")

            # Case 2: 1 (0x01), 4096
            self.assertEqual(cases[1].index, 2)
            self.assertEqual(cases[1].lid, 0x01)
            self.assertEqual(cases[1].length_bytes, 4096)
            self.assertEqual(cases[1].lid_name, "Error_Information")

            # Case 5: 0xC0, 64 (Vendor Specific)
            self.assertEqual(cases[4].index, 5)
            self.assertEqual(cases[4].lid, 0xC0)
            self.assertEqual(cases[4].length_bytes, 64)
            self.assertEqual(cases[4].lid_name, "Vendor_Specific_0xC0")
        finally:
            os.remove(path)

    def test_length_with_units(self):
        content = """lid,length
0x02,4KB
0x01,64K
0x03,1
0x04,1MB
"""
        path = self._create_temp_csv(content)
        try:
            cases = parse_csv(path)
            self.assertEqual(len(cases), 4)
            self.assertEqual(cases[0].length_bytes, 4096)
            self.assertEqual(cases[1].length_bytes, 65536)
            self.assertEqual(cases[2].length_bytes, 1)
            self.assertEqual(cases[3].length_bytes, 1048576)
        finally:
            os.remove(path)

    def test_inline_comments_and_custom_names(self):
        content = """# 頂部註解
LID,Length,Name
0x02,512,MyCustomSMART # 行內註解說明
0x01,1024 // C++風格註解
"""
        path = self._create_temp_csv(content)
        try:
            cases = parse_csv(path)
            self.assertEqual(len(cases), 2)
            self.assertEqual(cases[0].lid, 0x02)
            self.assertEqual(cases[0].length_bytes, 512)
            self.assertEqual(cases[0].lid_name, "MyCustomSMART")
            self.assertEqual(cases[1].lid, 0x01)
            self.assertEqual(cases[1].length_bytes, 1024)
            self.assertEqual(cases[1].lid_name, "Error_Information")
        finally:
            os.remove(path)

    def test_semicolon_and_tab_delimiters(self):
        content = "0x02; 512\n0x03\t1024"
        path = self._create_temp_csv(content)
        try:
            cases = parse_csv(path)
            self.assertEqual(len(cases), 2)
            self.assertEqual(cases[0].lid, 0x02)
            self.assertEqual(cases[0].length_bytes, 512)
            self.assertEqual(cases[1].lid, 0x03)
            self.assertEqual(cases[1].length_bytes, 1024)
        finally:
            os.remove(path)

    def test_actual_sample_test_csv_file(self):
        sample_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_cases", "sample_test.csv"))
        cases = parse_csv(sample_path)
        self.assertEqual(len(cases), 9)
        self.assertEqual(cases[0].lid, 0x02)
        self.assertEqual(cases[0].length_bytes, 512)
        self.assertEqual(cases[-1].lid, 0x02)
        self.assertEqual(cases[-1].length_bytes, 1)

    def test_utf8_sig_bom_support(self):
        content = "LID,Length\n0x02,512\n"
        path = self._create_temp_csv(content, encoding="utf-8-sig")
        try:
            cases = parse_csv(path)
            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0].lid, 0x02)
            self.assertEqual(cases[0].length_bytes, 512)
        finally:
            os.remove(path)

    def test_special_log_page_arbitrary_lengths(self):
        content = """LID,Length,Name
0xC0,1,Vendor_1B
0xC1,2,Vendor_2B
0xC2,3,Vendor_3B
0xC3,4,Vendor_4B
0xC4,7,Vendor_7B
0xC5,13,Vendor_13B
0xC6,64,Vendor_64B
0xC7,0x40,Vendor_Hex64B
0xC8,100,Vendor_100B
0xC9,128,Vendor_128B
0xCA,256,Vendor_256B
0xCB,0x200,Vendor_Hex512B
0xCC,700,Vendor_700B
0xCD,1024,Vendor_1024B
0xCE,0x400,Vendor_Hex1024B
"""
        path = self._create_temp_csv(content)
        try:
            cases = parse_csv(path)
            self.assertEqual(len(cases), 15)
            self.assertEqual(cases[0].length_bytes, 1)
            self.assertEqual(cases[1].length_bytes, 2)
            self.assertEqual(cases[2].length_bytes, 3)
            self.assertEqual(cases[3].length_bytes, 4)
            self.assertEqual(cases[4].length_bytes, 7)
            self.assertEqual(cases[5].length_bytes, 13)
            self.assertEqual(cases[6].length_bytes, 64)
            self.assertEqual(cases[7].length_bytes, 64)   # 0x40 -> 64
            self.assertEqual(cases[8].length_bytes, 100)
            self.assertEqual(cases[9].length_bytes, 128)
            self.assertEqual(cases[10].length_bytes, 256)
            self.assertEqual(cases[11].length_bytes, 512) # 0x200 -> 512
            self.assertEqual(cases[12].length_bytes, 700)
            self.assertEqual(cases[13].length_bytes, 1024)
            self.assertEqual(cases[14].length_bytes, 1024) # 0x400 -> 1024
        finally:
            os.remove(path)

    def test_to_command_conversion(self):
        case = CsvTestCase(index=1, lid=0x02, length_bytes=512, lid_name="SMART")
        cmd = case.to_command()
        self.assertEqual(cmd.lid, 0x02)
        self.assertEqual(cmd.length_bytes, 512)
        self.assertEqual(cmd.numd, 127)


if __name__ == "__main__":
    unittest.main()
