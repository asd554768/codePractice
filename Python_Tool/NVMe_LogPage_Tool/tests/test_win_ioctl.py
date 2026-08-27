"""Windows IOCTL 與裝置開啟單元測試。"""
import unittest
from unittest.mock import patch
import ctypes
import sys
import os

# 確保專案根目錄在 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.win_ioctl import open_device, open_device_query, INVALID_HANDLE_VALUE

class TestWinIoctl(unittest.TestCase):
    
    @patch("ctypes.windll.kernel32.CreateFileW")
    @patch("ctypes.GetLastError")
    def test_open_device_access_denied(self, mock_get_last_error, mock_create_file):
        """驗證當 Windows 返回 Error 5 (存取被拒) 時，會拋出明確的 PermissionError 提示。"""
        # 模擬開啟失敗
        mock_create_file.return_value = INVALID_HANDLE_VALUE
        mock_get_last_error.return_value = 5  # ERROR_ACCESS_DENIED
        
        with self.assertRaises(PermissionError) as context:
            open_device(1)
            
        self.assertIn("存取被拒", str(context.exception))
        self.assertIn("請右鍵點擊程式選擇「以系統管理員身分執行」", str(context.exception))
        
    @patch("ctypes.windll.kernel32.CreateFileW")
    @patch("ctypes.GetLastError")
    def test_open_device_other_error(self, mock_get_last_error, mock_create_file):
        """驗證當 Windows 返回其他錯誤碼時，會拋出 OSError。"""
        mock_create_file.return_value = INVALID_HANDLE_VALUE
        mock_get_last_error.return_value = 2  # ERROR_FILE_NOT_FOUND
        
        with self.assertRaises(OSError) as context:
            open_device(99)
            
        self.assertIn("Windows 錯誤碼: 2", str(context.exception))

    @patch("ctypes.windll.kernel32.CreateFileW")
    def test_open_device_query_success(self, mock_create_file):
        """驗證 DesiredAccess=0 的 open_device_query 能正確回傳 Handle。"""
        mock_create_file.return_value = 12345
        
        handle = open_device_query(2)
        
        self.assertEqual(handle, 12345)
        # 驗證呼叫時 DesiredAccess 參數為 0
        args, _ = mock_create_file.call_args
        self.assertEqual(args[1], 0)

if __name__ == "__main__":
    unittest.main()
