"""reporter 模組單元測試。"""
import unittest
import tempfile
import os
import sys
import csv
import json

# 確保專案根目錄在 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from runner.reporter import Reporter
from runner.batch_runner import SingleResult


class TestReporter(unittest.TestCase):
    """測試結果存檔、Hex/Json 匯出與 summary.csv 彙整。"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_single_result_and_dump_files(self):
        reporter = Reporter(base_dir=self.temp_dir.name)
        
        # 構造 SMART 資料 (512 bytes)
        smart_data = bytearray(512)
        smart_data[3] = 98  # available spare = 98%
        
        res_pass = SingleResult(
            index=1,
            lid=0x02,
            lid_name="SMART_Health_Information",
            numd=0x7F,
            length_bytes=512,
            cdw10=0x007F0002,
            status_code=0,
            latency_ms=1.25,
            success=True,
            data=bytes(smart_data),
            error_message=""
        )
        
        reporter.save_single_result(res_pass)
        
        # 驗證 dump 目錄下是否有 .bin, .hex, .json
        dump_dir = os.path.join(reporter.output_dir, "dump")
        self.assertTrue(os.path.exists(dump_dir))
        
        base_name = "001_LID_0x02_CDW10_0x007F0002_SMART_Health_Information_512B"
        bin_file = os.path.join(dump_dir, f"{base_name}.bin")
        hex_file = os.path.join(dump_dir, f"{base_name}.hex")
        json_file = os.path.join(dump_dir, f"{base_name}.json")
        
        self.assertTrue(os.path.exists(bin_file))
        self.assertTrue(os.path.exists(hex_file))
        self.assertTrue(os.path.exists(json_file))
        
        # 驗證二進位內容
        with open(bin_file, "rb") as f:
            self.assertEqual(f.read(), bytes(smart_data))
            
        # 驗證 json 內容
        with open(json_file, "r", encoding="utf-8") as f:
            parsed_json = json.load(f)
            self.assertEqual(parsed_json.get("available_spare"), 98)

    def test_write_summary_csv(self):
        reporter = Reporter(base_dir=self.temp_dir.name)
        
        results = [
            SingleResult(
                index=1,
                lid=0x02,
                lid_name="SMART_Health_Information",
                numd=0x7F,
                length_bytes=512,
                cdw10=0x007F0002,
                status_code=0,
                latency_ms=1.2,
                success=True,
                data=b"\x00" * 512,
                error_message=""
            ),
            SingleResult(
                index=2,
                lid=0x01,
                lid_name="Error_Information",
                numd=0xFF,
                length_bytes=1024,
                cdw10=0x00FF0001,
                status_code=0x4005,
                latency_ms=0.8,
                success=False,
                data=None,
                error_message="NVMe Error Status: 0x4005"
            ),
        ]
        
        summary_path = reporter.write_summary(results)
        self.assertTrue(os.path.exists(summary_path))
        
        with open(summary_path, "r", encoding="utf-8") as f:
            reader = list(csv.reader(f))
            
            # Header
            self.assertEqual(reader[0], ["Index", "LID", "LID_Name", "NUMD", "Length_Bytes", "CDW10", "Channel", "Status_Code", "Latency_ms", "Result", "Error_Message"])
            
            # Row 1 (PASS)
            self.assertEqual(reader[1][0], "1")
            self.assertEqual(reader[1][1], "0x02")
            self.assertEqual(reader[1][3], "0x7F")
            self.assertEqual(reader[1][4], "512")
            self.assertEqual(reader[1][5], "0x007F0002")
            self.assertEqual(reader[1][9], "PASS")
            
            # Row 2 (FAIL)
            self.assertEqual(reader[2][0], "2")
            self.assertEqual(reader[2][1], "0x01")
            self.assertEqual(reader[2][3], "0xFF")
            self.assertEqual(reader[2][4], "1024")
            self.assertEqual(reader[2][5], "0x00FF0001")
            self.assertEqual(reader[2][7], "0x4005")
            self.assertEqual(reader[2][9], "FAIL")
            self.assertEqual(reader[2][10], "NVMe Error Status: 0x4005")
            
            # 統計行
            self.assertEqual(reader[4], ["Total", "2"])
            self.assertEqual(reader[5], ["Pass", "1"])
            self.assertEqual(reader[6], ["Fail", "1"])


if __name__ == "__main__":
    unittest.main()
