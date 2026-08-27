"""nvme_driver 模組單元測試。"""
import unittest
from unittest.mock import patch, MagicMock
import ctypes
import struct
import sys
import os

# 確保專案根目錄在 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.commands import GetLogPageCommand
from core.nvme_driver import NvmeDriver
from core.win_ioctl import (
    STORAGE_PROTOCOL_COMMAND,
    STORAGE_PROTOCOL_STRUCTURE_VERSION,
    PROTOCOL_TYPE_NVME,
    STORAGE_PROTOCOL_SPECIFIC_NVME_ADMIN_COMMAND,
    STORAGE_PROTOCOL_COMMAND_FLAG_ADAPTER_REQUEST,
    IOCTL_STORAGE_PROTOCOL_COMMAND,
    IOCTL_STORAGE_QUERY_PROPERTY
)
from config import OPCODE_GET_LOG_PAGE


class TestNvmeDriver(unittest.TestCase):
    """測試 NvmeDriver 底層 SPC 結構組合、雙通道 IOCTL 呼叫與資料裁切。"""

    def test_spc_structure_size(self):
        # Windows SDK 規範: 20 DWORDs (80 Bytes) + Command[64] = 144 Bytes
        self.assertEqual(ctypes.sizeof(STORAGE_PROTOCOL_COMMAND), 144)

    def test_constants_definitions(self):
        self.assertEqual(IOCTL_STORAGE_PROTOCOL_COMMAND, 0x002DD3C0)
        self.assertEqual(STORAGE_PROTOCOL_STRUCTURE_VERSION, 1)
        self.assertEqual(PROTOCOL_TYPE_NVME, 3)
        self.assertEqual(STORAGE_PROTOCOL_SPECIFIC_NVME_ADMIN_COMMAND, 1)
        self.assertEqual(STORAGE_PROTOCOL_COMMAND_FLAG_ADAPTER_REQUEST, 0x80000000)

    @patch("core.nvme_driver.device_io_control")
    @patch("core.nvme_driver.open_device")
    def test_get_log_page_passthrough_success(self, mock_open, mock_ioctl):
        mock_open.return_value = 100  # Fake Handle
        
        captured_io_buffer = None
        
        def fake_ioctl(handle, ioctl_code, in_buf, in_size, out_buf, out_size):
            nonlocal captured_io_buffer
            captured_io_buffer = in_buf
            if ioctl_code == IOCTL_STORAGE_PROTOCOL_COMMAND:
                # 設定 ReturnStatus = 0, ErrorCode = 0
                struct.pack_into("<I", out_buf, 16, 0)
                struct.pack_into("<I", out_buf, 20, 0)
                # 模擬設備在 offset 208 寫入 4 Bytes 回應
                ctypes.memmove(ctypes.byref(out_buf, 208), b"\x12\x34\x56\x78", 4)
                return True, in_size
            return False, 0
            
        mock_ioctl.side_effect = fake_ioctl

        with NvmeDriver(1) as driver:
            # 請求 1 Byte (Vendor LID >= 0xC0 優先走 Pass-Through)
            cmd = GetLogPageCommand(lid=0xC0, length_bytes=1)
            data, status = driver.get_log_page(cmd)

        self.assertEqual(status, 0)
        self.assertEqual(data, b"\x12")  # 精準裁切為 1 Byte

    @patch("core.nvme_driver.device_io_control")
    @patch("core.nvme_driver.open_device")
    def test_get_log_page_fallback_to_query_property(self, mock_open, mock_dev_ioctl):
        mock_open.return_value = 100
        
        call_count = 0
        def fake_dual_ioctl(handle, ioctl_code, in_b, in_s, out_b, out_s):
            nonlocal call_count
            call_count += 1
            if ioctl_code == IOCTL_STORAGE_PROTOCOL_COMMAND:
                # 第一次 Pass-Through 模擬失敗
                return False, 0
            elif ioctl_code == IOCTL_STORAGE_QUERY_PROPERTY:
                # 第二次 Query Property 模擬成功
                struct.pack_into("<I", out_b, 0, 1)    # Version
                struct.pack_into("<I", out_b, 4, 48)   # Size
                struct.pack_into("<I", out_b, 24, 40)  # ProtocolDataOffset (40 from SPSD, total 48)
                struct.pack_into("<I", out_b, 28, 512) # ProtocolDataLength
                ctypes.memmove(ctypes.byref(out_b, 48), b"\xAA" * 512, 512)
                return True, 48 + 512
            return False, 0

        mock_dev_ioctl.side_effect = fake_dual_ioctl

        with NvmeDriver(1) as driver:
            cmd = GetLogPageCommand(lid=0x02, length_bytes=512)
            data, status = driver.get_log_page(cmd)

        self.assertEqual(status, 0)
        self.assertEqual(data, b"\xAA" * 512)

    @patch("core.nvme_driver.device_io_control")
    @patch("core.nvme_driver.open_device")
    def test_get_log_page_fallback_to_intel_miniport(self, mock_open, mock_dev_ioctl):
        mock_open.return_value = 100
        
        def fake_miniport_ioctl(handle, ioctl_code, in_b, in_s, out_b, out_s):
            if ioctl_code == 0x0004D008: # IOCTL_SCSI_MINIPORT
                out_b.header.SrbIoCtrl.ReturnCode = 0
                ctypes.memmove(ctypes.byref(out_b.buffer), b"\xBB" * 512, 512)
                return True, out_s
            return False, 0

        mock_dev_ioctl.side_effect = fake_miniport_ioctl

        with NvmeDriver(1) as driver:
            cmd = GetLogPageCommand(lid=0x02, length_bytes=512)
            data, status = driver.get_log_page(cmd)

        self.assertEqual(status, 0)
        self.assertEqual(data, b"\xBB" * 512)

    @patch("core.nvme_driver.device_io_control")
    @patch("core.nvme_driver.open_device")
    def test_get_log_page_arbitrary_lengths_exact_slicing(self, mock_open, mock_dev_ioctl):
        mock_open.return_value = 100
        
        def fake_ioctl(handle, ioctl_code, in_b, in_s, out_b, out_s):
            if ioctl_code == IOCTL_STORAGE_QUERY_PROPERTY:
                struct.pack_into("<I", out_b, 0, 48)   # Size
                struct.pack_into("<I", out_b, 24, 40)  # Offset 40 (total 48)
                copy_len = min(out_s - 48, 1024)
                if copy_len > 0:
                    ctypes.memmove(ctypes.byref(out_b, 48), bytes(range(256)) * 4, copy_len)
                return True, out_s
            return False, 0

        mock_dev_ioctl.side_effect = fake_ioctl

        with NvmeDriver(1) as driver:
            for length in [1, 2, 3, 7, 13, 64, 100, 128, 256, 512, 700, 1024]:
                cmd = GetLogPageCommand(lid=0x02, length_bytes=length)
                data, status = driver.get_log_page(cmd)
                self.assertEqual(status, 0)
                self.assertEqual(len(data), length)
                expected = (bytes(range(256)) * 4)[:length]
                self.assertEqual(data, expected)


if __name__ == "__main__":
    unittest.main()
