"""裝置掃描器單元測試。"""
import unittest
from unittest.mock import patch, MagicMock
import ctypes
import struct
import sys
import os

# 確保專案根目錄在 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.device_scanner import scan_nvme_devices, NvmeDeviceInfo

class TestDeviceScanner(unittest.TestCase):
    
    @patch("core.device_scanner.device_io_control")
    @patch("core.device_scanner.open_device_query")
    @patch("core.device_scanner.close_device")
    def test_scan_nvme_devices_success(self, mock_close, mock_open_query, mock_ioctl):
        """驗證能否正確識別 NVMe (BusType=17) 並取得裝置名稱與大小。"""
        # 模擬存在 PhysicalDrive0 和 PhysicalDrive1，PhysicalDrive2 不存在
        def fake_open(drive_num):
            if drive_num < 2:
                return 100 + drive_num
            raise OSError("Access Denied")
            
        mock_open_query.side_effect = fake_open
        
        def fake_ioctl(handle, ioctl_code, in_buf, in_size, out_buf, out_size):
            if ioctl_code == 0x002D1400:
                if handle == 100: # Drive 0 (NVMe)
                    header = struct.pack("<IIBBBBIIIII", 46, 46, 0, 0, 0, 1, 0, 32, 0, 0, 17)
                    model_str = b"Test NVMe SSD\x00"
                    data = header + model_str
                    ctypes.memmove(ctypes.addressof(out_buf), data, len(data))
                    return True, len(data)
                elif handle == 101: # Drive 1 (SATA, BusType=11)
                    header = struct.pack("<IIBBBBIIIII", 44, 44, 0, 0, 0, 1, 0, 32, 0, 0, 11)
                    model_str = b"SATA HDD\x00"
                    data = header + model_str
                    ctypes.memmove(ctypes.addressof(out_buf), data, len(data))
                    return True, len(data)
            # IOCTL_DISK_GET_DRIVE_GEOMETRY = 0x00070000
            elif ioctl_code == 0x00070000:
                geo = struct.pack("<qI12s", 10000, 12, struct.pack("<III", 255, 63, 512))
                ctypes.memmove(ctypes.addressof(out_buf), geo, len(geo))
                return True, len(geo)
                
            return False, 0
            
        mock_ioctl.side_effect = fake_ioctl
        
        devices = scan_nvme_devices()
        
        # 應該只回傳 NVMe 的 Drive 0，因為 Drive 1 是 SATA
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].drive_number, 0)
        self.assertEqual(devices[0].model, "Test NVMe SSD")
        # 驗證大小計算是否正確 (1000000 * 255 * 63 * 512 = 82252800000 Bytes = 76.6 GB)
        self.assertAlmostEqual(devices[0].size_gb, 76.6, places=1)
        
    @patch("core.device_scanner.device_io_control")
    @patch("core.device_scanner.open_device_query")
    @patch("core.device_scanner.close_device")
    def test_scan_fallback_when_no_nvme(self, mock_close, mock_open_query, mock_ioctl):
        """驗證當系統中沒有 NVMe 設備時，掃描器會回傳所有可存取的設備。"""
        def fake_open(drive_num):
            if drive_num == 0:
                return 100
            raise OSError("Access Denied")
            
        mock_open_query.side_effect = fake_open
        
        def fake_ioctl(handle, ioctl_code, in_buf, in_size, out_buf, out_size):
            if ioctl_code == 0x002D1400: # Query Property
                header = struct.pack("<IIBBBBIIIII", 44, 44, 0, 0, 0, 1, 0, 32, 0, 0, 11) # BusType=11
                model_str = b"SATA HDD\x00"
                data = header + model_str
                ctypes.memmove(ctypes.addressof(out_buf), data, len(data))
                return True, len(data)
            elif ioctl_code == 0x00070000: # Geometry
                return False, 0 # 模擬無法取得大小
            return False, 0
            
        mock_ioctl.side_effect = fake_ioctl
        
        devices = scan_nvme_devices()
        
        # 由於沒有 NVMe，應 fallback 回傳所有抓到的磁碟
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].drive_number, 0)
        self.assertEqual(devices[0].model, "SATA HDD")
        self.assertEqual(devices[0].size_gb, 0.0) # Geometry 失敗時應為 0.0

if __name__ == "__main__":
    unittest.main()
