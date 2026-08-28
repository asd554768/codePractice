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
        content = """LID,NUMD
0x02,7F
1,3FF
0x03,7F
0x05,FF
0xC0,0F
"""
        path = self._create_temp_csv(content)
        try:
            cases = parse_csv(path)
            self.assertEqual(len(cases), 5)
            
            # Case 1: 0x02, 7F (NUMD=127 -> 512B)
            self.assertEqual(cases[0].index, 1)
            self.assertEqual(cases[0].lid, 0x02)
            self.assertEqual(cases[0].numd, 127)
            self.assertEqual(cases[0].length_bytes, 512)
            self.assertEqual(cases[0].lid_name, "SMART_Health_Information")

            # Case 2: 1 (0x01), 3FF (NUMD=1023 -> 4096B)
            self.assertEqual(cases[1].index, 2)
            self.assertEqual(cases[1].lid, 0x01)
            self.assertEqual(cases[1].numd, 1023)
            self.assertEqual(cases[1].length_bytes, 4096)
            self.assertEqual(cases[1].lid_name, "Error_Information")

            # Case 5: 0xC0, 0F (NUMD=15 -> 64B)
            self.assertEqual(cases[4].index, 5)
            self.assertEqual(cases[4].lid, 0xC0)
            self.assertEqual(cases[4].numd, 15)
            self.assertEqual(cases[4].length_bytes, 64)
            self.assertEqual(cases[4].lid_name, "Vendor_Specific_0xC0")
        finally:
            os.remove(path)

    def test_length_with_units(self):
        content = """lid,numd
0x02,4KB
0x01,64K
0x03,0
0x04,1MB
"""
        path = self._create_temp_csv(content)
        try:
            cases = parse_csv(path)
            self.assertEqual(len(cases), 4)
            self.assertEqual(cases[0].length_bytes, 4096)
            self.assertEqual(cases[1].length_bytes, 65536)
            self.assertEqual(cases[2].numd, 0)
            self.assertEqual(cases[2].length_bytes, 4)
            self.assertEqual(cases[3].length_bytes, 1048576)
        finally:
            os.remove(path)

    def test_inline_comments_and_custom_names(self):
        content = """# 頂部註解
LID,NUMD,Name
0x02,7F,MyCustomSMART # 行內註解說明
0x01,FF // C++風格註解
"""
        path = self._create_temp_csv(content)
        try:
            cases = parse_csv(path)
            self.assertEqual(len(cases), 2)
            self.assertEqual(cases[0].lid, 0x02)
            self.assertEqual(cases[0].numd, 0x7F)
            self.assertEqual(cases[0].length_bytes, 512)
            self.assertEqual(cases[0].lid_name, "MyCustomSMART")
            self.assertEqual(cases[1].lid, 0x01)
            self.assertEqual(cases[1].numd, 0xFF)
            self.assertEqual(cases[1].length_bytes, 1024)
            self.assertEqual(cases[1].lid_name, "Error_Information")
        finally:
            os.remove(path)

    def test_semicolon_and_tab_delimiters(self):
        content = "0x02; 7F\n0x03\tFF"
        path = self._create_temp_csv(content)
        try:
            cases = parse_csv(path)
            self.assertEqual(len(cases), 2)
            self.assertEqual(cases[0].lid, 0x02)
            self.assertEqual(cases[0].numd, 0x7F)
            self.assertEqual(cases[0].length_bytes, 512)
            self.assertEqual(cases[1].lid, 0x03)
            self.assertEqual(cases[1].numd, 0xFF)
            self.assertEqual(cases[1].length_bytes, 1024)
        finally:
            os.remove(path)

    def test_actual_sample_test_csv_file(self):
        sample_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test_cases", "sample_test.csv"))
        cases = parse_csv(sample_path)
        self.assertEqual(len(cases), 9)
        self.assertEqual(cases[0].lid, 0x02)
        self.assertEqual(cases[0].numd, 0x7F)
        self.assertEqual(cases[0].length_bytes, 512)
        self.assertEqual(cases[-1].lid, 0x02)
        self.assertEqual(cases[-1].numd, 0x00)
        self.assertEqual(cases[-1].length_bytes, 4)

    def test_utf8_sig_bom_support(self):
        content = "LID,NUMD\n0x02,7F\n"
        path = self._create_temp_csv(content, encoding="utf-8-sig")
        try:
            cases = parse_csv(path)
            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0].lid, 0x02)
            self.assertEqual(cases[0].numd, 127)
            self.assertEqual(cases[0].length_bytes, 512)
        finally:
            os.remove(path)

    def test_special_log_page_arbitrary_numd(self):
        content = """LID,NUMD,Name
0xC0,0,Vendor_4B
0xC1,1,Vendor_8B
0xC2,7F,Vendor_Hex7F
0xC3,0x7F,Vendor_0x7F
0xC4,FF,Vendor_1024B
0xC5,0x3FF,Vendor_4096B
0xC6,4KB,Vendor_Unit4K
"""
        path = self._create_temp_csv(content)
        try:
            cases = parse_csv(path)
            self.assertEqual(len(cases), 7)
            self.assertEqual(cases[0].numd, 0)
            self.assertEqual(cases[0].length_bytes, 4)
            self.assertEqual(cases[1].numd, 1)
            self.assertEqual(cases[1].length_bytes, 8)
            self.assertEqual(cases[2].numd, 127)
            self.assertEqual(cases[2].length_bytes, 512)
            self.assertEqual(cases[3].numd, 127)
            self.assertEqual(cases[3].length_bytes, 512)
            self.assertEqual(cases[4].numd, 255)
            self.assertEqual(cases[4].length_bytes, 1024)
            self.assertEqual(cases[5].numd, 1023)
            self.assertEqual(cases[5].length_bytes, 4096)
            self.assertEqual(cases[6].numd, 1023)
            self.assertEqual(cases[6].length_bytes, 4096)
        finally:
            os.remove(path)

    def test_custom_opcode_csv(self):
        content = """OPCODE,LID,NUMD
0xC0,0xF0,0x00
0x02,0x02,0x7F
0xD5,0x01,0x03,CustomVendorLog
"""
        path = self._create_temp_csv(content)
        try:
            cases = parse_csv(path)
            self.assertEqual(len(cases), 3)
            
            # Case 1: Opcode 0xC0, LID 0xF0, NUMD 0x00 (4B)
            self.assertEqual(cases[0].opcode, 0xC0)
            self.assertEqual(cases[0].lid, 0xF0)
            self.assertEqual(cases[0].numd, 0)
            self.assertEqual(cases[0].length_bytes, 4)
            cmd1 = cases[0].to_command()
            self.assertEqual(cmd1.opcode, 0xC0)
            self.assertEqual(cmd1.numd, 0)
            
            # Case 2: Opcode 0x02, LID 0x02, NUMD 0x7F
            self.assertEqual(cases[1].opcode, 0x02)
            self.assertEqual(cases[1].lid, 0x02)
            self.assertEqual(cases[1].numd, 127)
            
            # Case 3: Opcode 0xD5, LID 0x01, NUMD 0x03, Name
            self.assertEqual(cases[2].opcode, 0xD5)
            self.assertEqual(cases[2].lid, 0x01)
            self.assertEqual(cases[2].numd, 3)
            self.assertEqual(cases[2].lid_name, "CustomVendorLog")
        finally:
            os.remove(path)

    def test_to_command_conversion(self):
        case = CsvTestCase(index=1, lid=0x02, numd=127, length_bytes=512, lid_name="SMART", opcode=0xC0)
        cmd = case.to_command()
        self.assertEqual(cmd.lid, 0x02)
        self.assertEqual(cmd.length_bytes, 512)
        self.assertEqual(cmd.numd, 127)
        self.assertEqual(cmd.opcode, 0xC0)


if __name__ == "__main__":
    unittest.main()
