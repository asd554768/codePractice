"""parsers 模組單元測試。"""
import unittest
import sys
import os
import struct

# 確保專案根目錄在 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.parsers import format_hex_dump, parse_smart_log, parse_log_data


class TestParsers(unittest.TestCase):
    """測試資料解析與 Hex Dump 格式化。"""

    def test_format_hex_dump_basic(self):
        data = b"Hello, NVMe World!"  # 18 bytes
        dump = format_hex_dump(data, bytes_per_line=16)
        lines = dump.splitlines()

        self.assertEqual(len(lines), 2)
        # Line 0: 16 bytes
        self.assertTrue(lines[0].startswith("00000000:"))
        self.assertIn("48 65 6C 6C 6F", lines[0])
        self.assertTrue(lines[0].endswith("Hello, NVMe Worl"))
        # Line 1: 2 bytes
        self.assertTrue(lines[1].startswith("00000010:"))
        self.assertIn("64 21", lines[1])
        self.assertTrue(lines[1].endswith("d!"))

    def test_format_hex_dump_non_printable(self):
        data = bytes([0x00, 0x01, 0x1F, 0x7F, 0xFF, 0x41])  # 包含不可見與可見字元 'A'
        dump = format_hex_dump(data, bytes_per_line=16)
        self.assertIn(".....A", dump)

    def test_parse_smart_log(self):
        # 構造 512 bytes 的假 SMART Log
        buffer = bytearray(512)
        
        # byte 0: critical_warning = 0x01 (available spare below threshold)
        buffer[0] = 0x01
        
        # byte 1..2: composite_temperature = 310 Kelvin (310 - 273 = 37 Celsius)
        struct.pack_into("<H", buffer, 1, 310)
        
        # byte 3: available_spare = 100%
        buffer[3] = 100
        
        # byte 5: percentage_used = 5%
        buffer[5] = 5
        
        # byte 32..47: data_units_read (16 bytes = 128-bit integer, e.g. 1,000,000)
        struct.pack_into("<Q", buffer, 32, 1_000_000)
        
        # byte 112..127: power_cycles = 150
        struct.pack_into("<Q", buffer, 112, 150)
        
        # byte 128..143: power_on_hours = 2400
        struct.pack_into("<Q", buffer, 128, 2400)

        parsed = parse_smart_log(bytes(buffer))
        
        self.assertEqual(parsed["critical_warning"], 1)
        self.assertEqual(parsed["composite_temperature"], 37)  # Kelvin -> Celsius
        self.assertEqual(parsed["available_spare"], 100)
        self.assertEqual(parsed["percentage_used"], 5)
        self.assertEqual(parsed["data_units_read"], 1_000_000)
        self.assertEqual(parsed["power_cycles"], 150)
        self.assertEqual(parsed["power_on_hours"], 2400)

    def test_parse_log_data_dispatch(self):
        data = bytearray(512)
        struct.pack_into("<H", data, 1, 300)  # 27 Celsius
        
        # LID 0x02 應分派給 parse_smart_log
        res_02 = parse_log_data(0x02, bytes(data))
        self.assertIsNotNone(res_02)
        self.assertEqual(res_02["composite_temperature"], 27)

        # LID 0x01 目前無結構化解析器，應回傳 None
        res_01 = parse_log_data(0x01, bytes(data))
        self.assertIsNone(res_01)


if __name__ == "__main__":
    unittest.main()
