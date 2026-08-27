"""CLI 命令行介面單元測試。"""
import unittest
from unittest.mock import patch, MagicMock
import io
import sys
import os

# 確保專案根目錄在 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cli.cli_runner import run_cli
from core.device_scanner import NvmeDeviceInfo


class TestCliRunner(unittest.TestCase):
    """測試 CLI 參數解析與各子模式的分派。"""

    @patch("cli.cli_runner.scan_nvme_devices")
    def test_cli_scan(self, mock_scan):
        mock_scan.return_value = [
            NvmeDeviceInfo(
                drive_number=1,
                model="Samsung SSD 980 PRO",
                serial="S5GXNF0R123456",
                firmware_rev="5B2QGXA7",
                size_gb=1000.0
            )
        ]
        
        test_args = ["main.py", "--scan"]
        with patch.object(sys, "argv", test_args):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                run_cli()
                output = mock_stdout.getvalue()
                self.assertIn("PhysicalDrive1", output)
                self.assertIn("Samsung SSD 980 PRO", output)

    @patch("cli.cli_runner.BatchRunner")
    @patch("cli.cli_runner.parse_csv")
    def test_cli_csv_mode(self, mock_parse_csv, mock_batch_runner_cls):
        mock_parse_csv.return_value = [MagicMock()]
        
        mock_runner = MagicMock()
        mock_runner.start.return_value = None
        mock_runner._thread.join.return_value = None
        mock_batch_runner_cls.return_value = mock_runner

        test_args = ["main.py", "--device", "1", "--csv", "dummy.csv", "--delay", "50"]
        with patch.object(sys, "argv", test_args):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                run_cli()
                output = mock_stdout.getvalue()
                self.assertIn("開始執行 CSV 批次測試", output)
                mock_runner.start.assert_called_once()
                mock_runner._thread.join.assert_called_once()

    @patch("cli.cli_runner.BatchRunner")
    def test_cli_single_mode(self, mock_batch_runner_cls):
        mock_runner = MagicMock()
        mock_res = MagicMock()
        mock_res.success = True
        mock_res.data = b"\x01\x02\x03\x04"
        mock_runner.results = [mock_res]
        mock_runner._thread.join.return_value = None
        mock_batch_runner_cls.return_value = mock_runner

        test_args = ["main.py", "--device", "1", "--lid", "0x02", "--length", "4"]
        with patch.object(sys, "argv", test_args):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                run_cli()
                output = mock_stdout.getvalue()
                self.assertIn("取得資料成功", output)
                self.assertIn("01 02 03 04", output)


if __name__ == "__main__":
    unittest.main()
