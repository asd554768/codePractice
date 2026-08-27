"""batch_runner 模組單元測試。"""
import unittest
from unittest.mock import MagicMock, patch
import tempfile
import time
import os
import sys

# 確保專案根目錄在 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from runner.batch_runner import BatchRunner, BatchConfig, ErrorPolicy, SingleResult
from runner.csv_parser import CsvTestCase


class TestBatchRunner(unittest.TestCase):
    """測試批次執行引擎流程控制、回呼機制與錯誤策略。"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("runner.batch_runner.NvmeDriver")
    def test_batch_runner_success_flow(self, mock_driver_cls):
        # 設定 Mock NvmeDriver
        mock_driver_instance = MagicMock()
        mock_driver_instance.get_log_page.return_value = (b"\xAA" * 512, 0)
        mock_driver_instance.__enter__.return_value = mock_driver_instance
        mock_driver_cls.return_value = mock_driver_instance

        test_cases = [
            CsvTestCase(index=1, lid=0x02, length_bytes=512, lid_name="SMART"),
            CsvTestCase(index=2, lid=0x01, length_bytes=1024, lid_name="Error"),
        ]

        config = BatchConfig(
            device_number=1,
            test_cases=test_cases,
            delay_ms=10,
            error_policy=ErrorPolicy.CONTINUE,
            output_dir=self.temp_dir.name
        )

        progress_events = []
        result_events = []
        complete_events = []

        runner = BatchRunner(config)
        runner.on_progress = lambda cur, tot: progress_events.append((cur, tot))
        runner.on_result = lambda res: result_events.append(res)
        runner.on_complete = lambda res_list: complete_events.append(res_list)

        runner.start()
        runner._thread.join(timeout=3.0)

        # 驗證執行緒正常結束
        self.assertFalse(runner.is_running)

        # 驗證結果與回呼
        self.assertEqual(len(runner.results), 2)
        self.assertEqual(progress_events, [(1, 2), (2, 2)])
        self.assertEqual(len(result_events), 2)
        self.assertEqual(len(complete_events), 1)
        self.assertTrue(runner.results[0].success)
        self.assertEqual(runner.results[0].data, b"\xAA" * 512)

    @patch("runner.batch_runner.NvmeDriver")
    def test_error_policy_stop(self, mock_driver_cls):
        # 模擬第 1 筆失敗，後續應停止
        mock_driver_instance = MagicMock()
        mock_driver_instance.get_log_page.return_value = (None, 0x4005)  # Error status
        mock_driver_instance.__enter__.return_value = mock_driver_instance
        mock_driver_cls.return_value = mock_driver_instance

        test_cases = [
            CsvTestCase(index=1, lid=0x02, length_bytes=512, lid_name="SMART"),
            CsvTestCase(index=2, lid=0x01, length_bytes=1024, lid_name="Error"),
        ]

        config = BatchConfig(
            device_number=1,
            test_cases=test_cases,
            delay_ms=0,
            error_policy=ErrorPolicy.STOP,
            output_dir=self.temp_dir.name
        )

        runner = BatchRunner(config)
        runner.start()
        runner._thread.join(timeout=3.0)

        # 因為 ErrorPolicy.STOP，執行第 1 筆失敗後應中斷，總結果只有 1 筆
        self.assertEqual(len(runner.results), 1)
        self.assertFalse(runner.results[0].success)

    @patch("runner.batch_runner.NvmeDriver")
    def test_manual_stop(self, mock_driver_cls):
        # 測試中途呼叫 stop() 中斷
        mock_driver_instance = MagicMock()
        # 模擬延遲
        def slow_get_log(cmd):
            time.sleep(0.05)
            return (b"\x00" * cmd.length_bytes, 0)
        
        mock_driver_instance.get_log_page.side_effect = slow_get_log
        mock_driver_instance.__enter__.return_value = mock_driver_instance
        mock_driver_cls.return_value = mock_driver_instance

        test_cases = [
            CsvTestCase(index=i, lid=0x02, length_bytes=512, lid_name="SMART")
            for i in range(1, 10)
        ]

        config = BatchConfig(
            device_number=1,
            test_cases=test_cases,
            delay_ms=50,
            error_policy=ErrorPolicy.CONTINUE,
            output_dir=self.temp_dir.name
        )

        runner = BatchRunner(config)
        runner.start()
        time.sleep(0.08)  # 等待執行 1~2 筆後中斷
        runner.stop()
        runner._thread.join(timeout=3.0)

        self.assertFalse(runner.is_running)
        self.assertLess(len(runner.results), 10)


if __name__ == "__main__":
    unittest.main()
