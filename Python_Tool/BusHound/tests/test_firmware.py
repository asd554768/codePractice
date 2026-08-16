"""
test_firmware.py — MCU 韌體更新功能全面性單元測試
=================================================
涵蓋範疇：
  A. 自然排序 (Natural Sort) — 4 項
  B. Address 位元組計算與 CDB 組裝 — 8 項
  C. CDB 模板載入與防呆 — 5 項
  D. 分塊資料夾載入 — 9 項
  E. Worker Thread 模擬傳輸 (Mock SPTD) — 6 項
  F. GUI Tab 4 元件存在性與互動邏輯 — 9 項
"""

import unittest
from unittest.mock import patch, MagicMock, call
import os
import sys
import tempfile
import shutil
import threading
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from firmware_updater import (
    FirmwareUpdateEngine, natural_sort_key, CHUNK_SIZE, ADDR_INCREMENT
)


# =====================================================================
# A. 自然排序 (Natural Sort) — 4 項
# =====================================================================
class TestNaturalSort(unittest.TestCase):
    """自然排序邏輯全面驗證"""

    def test_basic_numeric_sort(self):
        """基本數字排序：chunk_10 應排在 chunk_2 之後"""
        files = ["chunk_10.bin", "chunk_2.bin", "chunk_1.bin", "chunk_20.bin", "chunk_3.bin"]
        result = sorted(files, key=natural_sort_key)
        self.assertEqual(result, ["chunk_1.bin", "chunk_2.bin", "chunk_3.bin",
                                  "chunk_10.bin", "chunk_20.bin"])

    def test_three_digit_numbers(self):
        """三位數字排序：fw_100 排在 fw_9 / fw_10 之後"""
        files = ["fw_0.bin", "fw_100.bin", "fw_9.bin", "fw_10.bin"]
        result = sorted(files, key=natural_sort_key)
        self.assertEqual(result, ["fw_0.bin", "fw_9.bin", "fw_10.bin", "fw_100.bin"])

    def test_case_insensitive(self):
        """大小寫不敏感排序"""
        files = ["Data_2.bin", "data_1.bin", "DATA_10.bin"]
        result = sorted(files, key=natural_sort_key)
        self.assertEqual(result[0].lower(), "data_1.bin")
        self.assertEqual(result[1].lower(), "data_2.bin")

    def test_no_numbers(self):
        """無數字時退化為字母排序"""
        files = ["c.bin", "a.bin", "b.bin"]
        result = sorted(files, key=natural_sort_key)
        self.assertEqual(result, ["a.bin", "b.bin", "c.bin"])


# =====================================================================
# B. Address 位元組計算與 CDB 組裝 — 8 項
# =====================================================================
class TestAddressCalculation(unittest.TestCase):
    """Address 遞增與 CDB Byte 3/4 組裝的全面驗證"""

    def test_address_0x0000(self):
        cdb = FirmwareUpdateEngine.build_cdb([0x00] * 16, 0x0000)
        self.assertEqual(cdb[3], 0x00)
        self.assertEqual(cdb[4], 0x00)

    def test_address_0x0080(self):
        """第 2 塊 (idx=1): Address = 0x0080"""
        cdb = FirmwareUpdateEngine.build_cdb([0x00] * 16, 0x0080)
        self.assertEqual(cdb[3], 0x00)
        self.assertEqual(cdb[4], 0x80)

    def test_address_0x0100(self):
        """第 3 塊 (idx=2): Address = 0x0100, 進位至 Byte 3"""
        cdb = FirmwareUpdateEngine.build_cdb([0x00] * 16, 0x0100)
        self.assertEqual(cdb[3], 0x01)
        self.assertEqual(cdb[4], 0x00)

    def test_address_0x6F80(self):
        """28KB 韌體最後一塊 (idx=223): Address = 0x6F80"""
        cdb = FirmwareUpdateEngine.build_cdb([0x00] * 16, 0x6F80)
        self.assertEqual(cdb[3], 0x6F)
        self.assertEqual(cdb[4], 0x80)

    def test_address_0xFFFF_boundary(self):
        """16-bit 最大值邊界測試"""
        cdb = FirmwareUpdateEngine.build_cdb([0x00] * 16, 0xFFFF)
        self.assertEqual(cdb[3], 0xFF)
        self.assertEqual(cdb[4], 0xFF)

    def test_full_224_chunk_sequence(self):
        """完整 224 塊 Address 遞增序列精確驗證"""
        for i in range(224):
            addr = i * ADDR_INCREMENT
            cdb = FirmwareUpdateEngine.build_cdb([0x00] * 16, addr)
            self.assertEqual(cdb[3], (addr >> 8) & 0xFF, f"Chunk {i}: CDB[3]")
            self.assertEqual(cdb[4], addr & 0xFF, f"Chunk {i}: CDB[4]")

    def test_preserves_non_address_bytes(self):
        """build_cdb 不可改動 Byte 0~2 與 Byte 5~15"""
        base = [0x2A, 0x11, 0x22, 0xAA, 0xBB, 0x55, 0x66, 0x77,
                0x88, 0x99, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF]
        cdb = FirmwareUpdateEngine.build_cdb(base, 0x1234)
        # Byte 0~2 不動
        self.assertEqual(cdb[0], 0x2A)
        self.assertEqual(cdb[1], 0x11)
        self.assertEqual(cdb[2], 0x22)
        # Byte 3~4 被覆寫
        self.assertEqual(cdb[3], 0x12)
        self.assertEqual(cdb[4], 0x34)
        # Byte 5~15 不動
        for i in range(5, 16):
            self.assertEqual(cdb[i], base[i], f"CDB[{i}] should not change")

    def test_build_cdb_returns_new_list(self):
        """build_cdb 應回傳新 list，不可修改原始 base_cdb"""
        base = [0x2A] + [0x00] * 15
        original_copy = list(base)
        cdb = FirmwareUpdateEngine.build_cdb(base, 0x1234)
        self.assertEqual(base, original_copy, "base_cdb 不應被修改")
        self.assertIsNot(cdb, base)


# =====================================================================
# C. CDB 模板載入與防呆 — 5 項
# =====================================================================
class TestCdbTemplate(unittest.TestCase):
    """CDB 模板載入的全面驗證"""

    def test_load_from_16_byte_list(self):
        engine = FirmwareUpdateEngine()
        template = [0x2A, 0x00, 0x00, 0x00, 0x00, 0x00,
                    0x00, 0x00, 0x00, 0x80, 0x00, 0x00,
                    0x00, 0x00, 0x00, 0x00]
        engine.load_cdb_template(template)
        self.assertEqual(engine.base_cdb, template)

    def test_load_from_bytes_object(self):
        engine = FirmwareUpdateEngine()
        engine.load_cdb_template(bytes([0xFF] * 16))
        self.assertEqual(engine.base_cdb[0], 0xFF)
        self.assertEqual(engine.base_cdb[15], 0xFF)

    def test_load_from_bytearray(self):
        engine = FirmwareUpdateEngine()
        engine.load_cdb_template(bytearray([0xAB] * 16))
        self.assertEqual(engine.base_cdb[0], 0xAB)

    def test_short_input_pads_to_16(self):
        """不足 16 bytes 的輸入應自動補零"""
        engine = FirmwareUpdateEngine()
        engine.load_cdb_template([0x2A, 0x11])
        self.assertEqual(len(engine.base_cdb), 16)
        self.assertEqual(engine.base_cdb[0], 0x2A)
        self.assertEqual(engine.base_cdb[1], 0x11)
        self.assertEqual(engine.base_cdb[2], 0x00)
        self.assertEqual(engine.base_cdb[15], 0x00)

    def test_long_input_truncates_to_16(self):
        """超過 16 bytes 的輸入應截斷"""
        engine = FirmwareUpdateEngine()
        engine.load_cdb_template(list(range(32)))
        self.assertEqual(len(engine.base_cdb), 16)
        self.assertEqual(engine.base_cdb[15], 15)


# =====================================================================
# D. 分塊資料夾載入 — 9 項
# =====================================================================
class TestChunkLoading(unittest.TestCase):
    """分塊韌體資料夾載入的全面驗證"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="fw_test_")
        self.engine = FirmwareUpdateEngine()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_chunks(self, count, size=CHUNK_SIZE, prefix="chunk_"):
        """產生 count 個指定大小的 .bin 檔案"""
        for i in range(count):
            fpath = os.path.join(self.tmpdir, f"{prefix}{i}.bin")
            with open(fpath, 'wb') as f:
                f.write(bytes([i & 0xFF] * size))

    def test_load_full_28kb_firmware(self):
        """載入完整 28KB 韌體 (224 × 128B)"""
        self._create_chunks(224)
        ok, msg = self.engine.load_chunks(self.tmpdir)
        self.assertTrue(ok)
        self.assertEqual(len(self.engine.chunks), 224)
        self.assertIn("224", msg)
        # 驗證總大小
        total_bytes = sum(len(c) for c in self.engine.chunks)
        self.assertEqual(total_bytes, 28672)  # 28KB = 28672

    def test_natural_sort_order_preserved(self):
        """確認檔案按自然排序載入：fw_1 < fw_2 < fw_10"""
        for i in [10, 2, 1, 20, 3]:
            fpath = os.path.join(self.tmpdir, f"fw_{i}.bin")
            with open(fpath, 'wb') as f:
                f.write(bytes([i & 0xFF] * CHUNK_SIZE))
        ok, _ = self.engine.load_chunks(self.tmpdir)
        self.assertTrue(ok)
        self.assertEqual(self.engine.chunks[0][0], 1)   # fw_1.bin
        self.assertEqual(self.engine.chunks[1][0], 2)   # fw_2.bin
        self.assertEqual(self.engine.chunks[2][0], 3)   # fw_3.bin
        self.assertEqual(self.engine.chunks[3][0], 10)   # fw_10.bin
        self.assertEqual(self.engine.chunks[4][0], 20)   # fw_20.bin

    def test_file_names_tracked(self):
        """載入後 file_names 應與 chunks 一一對應"""
        self._create_chunks(5)
        self.engine.load_chunks(self.tmpdir)
        self.assertEqual(len(self.engine.file_names), 5)
        self.assertEqual(self.engine.file_names[0], "chunk_0.bin")

    def test_abnormal_size_warning(self):
        """異常大小分塊仍可載入但訊息包含警告"""
        self._create_chunks(3)
        bad_path = os.path.join(self.tmpdir, "chunk_3.bin")
        with open(bad_path, 'wb') as f:
            f.write(bytes(64))  # 只有 64B
        ok, msg = self.engine.load_chunks(self.tmpdir)
        self.assertTrue(ok)
        self.assertEqual(len(self.engine.chunks), 4)
        self.assertIn("⚠️", msg)
        self.assertIn("64", msg)

    def test_oversized_chunk_warning(self):
        """超大分塊 (256B) 也產生警告"""
        fpath = os.path.join(self.tmpdir, "big.bin")
        with open(fpath, 'wb') as f:
            f.write(bytes(256))
        ok, msg = self.engine.load_chunks(self.tmpdir)
        self.assertTrue(ok)
        self.assertIn("⚠️", msg)
        self.assertIn("256", msg)

    def test_empty_folder_fails(self):
        """空資料夾回傳失敗"""
        ok, msg = self.engine.load_chunks(self.tmpdir)
        self.assertFalse(ok)
        self.assertIn("沒有", msg)

    def test_nonexistent_folder_fails(self):
        """不存在的路徑回傳失敗"""
        ok, msg = self.engine.load_chunks("/this/path/does/not/exist")
        self.assertFalse(ok)
        self.assertIn("不存在", msg)

    def test_non_bin_files_ignored(self):
        """非 .bin 副檔名的檔案應被忽略"""
        self._create_chunks(3)
        # 加入非 .bin 檔案
        with open(os.path.join(self.tmpdir, "readme.txt"), 'w') as f:
            f.write("hello")
        with open(os.path.join(self.tmpdir, "config.json"), 'w') as f:
            f.write("{}")
        ok, _ = self.engine.load_chunks(self.tmpdir)
        self.assertTrue(ok)
        self.assertEqual(len(self.engine.chunks), 3)

    def test_end_address_in_message(self):
        """載入訊息應包含預計結束 Address"""
        self._create_chunks(10)
        self.engine.start_address = 0x0000
        ok, msg = self.engine.load_chunks(self.tmpdir)
        self.assertTrue(ok)
        expected_end = 10 * 0x80  # 0x0500
        self.assertIn("0x0500", msg)


# =====================================================================
# E. Worker Thread 模擬傳輸 (Mock SPTD) — 6 項
# =====================================================================
class TestWorkerTransmission(unittest.TestCase):
    """使用 Mock 模擬 SPTD 傳輸的 Worker Thread 全面驗證"""

    def setUp(self):
        self.engine = FirmwareUpdateEngine()
        self.engine.base_cdb = [0x2A] + [0x00] * 15
        self.engine.start_address = 0x0000
        # 預設 3 塊 128B 測試資料
        self.engine.chunks = [bytes([i] * CHUNK_SIZE) for i in range(3)]
        self.engine.file_names = [f"chunk_{i}.bin" for i in range(3)]

    @patch('firmware_updater.close_drive')
    @patch('firmware_updater.unlock_drive')
    @patch('firmware_updater.lock_drive', return_value=(True, 0))
    @patch('firmware_updater.open_drive', return_value=9999)
    @patch('firmware_updater.send_scsi_command')
    def test_full_success_transmission(self, mock_send, mock_open, mock_lock, mock_unlock, mock_close):
        """3 塊全部成功：done_cb(True, ...)"""
        mock_send.return_value = (0x00, b"", bytes(18))

        done_event = threading.Event()
        results = {}

        def on_done(ok, msg):
            results['ok'] = ok
            results['msg'] = msg
            done_event.set()

        self.engine.start(0, done_cb=on_done)
        done_event.wait(timeout=5)

        self.assertTrue(results.get('ok'))
        self.assertIn("完成", results.get('msg', ''))
        self.assertEqual(mock_send.call_count, 3)
        mock_open.assert_called_once_with(0)
        mock_lock.assert_called_once()
        mock_unlock.assert_called_once()
        mock_close.assert_called_once()

    @patch('firmware_updater.close_drive')
    @patch('firmware_updater.unlock_drive')
    @patch('firmware_updater.lock_drive', return_value=(True, 0))
    @patch('firmware_updater.open_drive', return_value=9999)
    @patch('firmware_updater.send_scsi_command')
    def test_check_condition_stops_immediately(self, mock_send, mock_open, mock_lock, mock_unlock, mock_close):
        """第 2 塊回傳 CHECK CONDITION (0x02) → 立即中斷，只送 2 塊"""
        sense_data = bytearray(18)
        sense_data[0] = 0x70
        sense_data[2] = 0x05  # ILLEGAL REQUEST
        sense_data[12] = 0x20
        mock_send.side_effect = [
            (0x00, b"", bytes(18)),      # Chunk 1: OK
            (0x02, b"", bytes(sense_data)),  # Chunk 2: CHECK CONDITION
        ]

        done_event = threading.Event()
        results = {}
        def on_done(ok, msg):
            results['ok'] = ok
            results['msg'] = msg
            done_event.set()

        self.engine.start(0, done_cb=on_done)
        done_event.wait(timeout=5)

        self.assertFalse(results.get('ok'))
        self.assertIn("失敗", results.get('msg', ''))
        self.assertEqual(mock_send.call_count, 2)

    @patch('firmware_updater.close_drive')
    @patch('firmware_updater.unlock_drive')
    @patch('firmware_updater.lock_drive', return_value=(True, 0))
    @patch('firmware_updater.open_drive', return_value=9999)
    @patch('firmware_updater.send_scsi_command')
    def test_abort_stops_transmission(self, mock_send, mock_open, mock_lock, mock_unlock, mock_close):
        """使用者中途 Abort → 應停止傳輸"""
        self.engine.chunks = [bytes(CHUNK_SIZE)] * 100  # 100 塊

        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 5:
                self.engine.abort()
            return (0x00, b"", bytes(18))
        mock_send.side_effect = side_effect

        done_event = threading.Event()
        results = {}
        def on_done(ok, msg):
            results['ok'] = ok
            results['msg'] = msg
            done_event.set()

        self.engine.start(0, done_cb=on_done)
        done_event.wait(timeout=5)

        self.assertFalse(results.get('ok'))
        self.assertIn("中止", results.get('msg', ''))
        self.assertLess(mock_send.call_count, 100)

    @patch('firmware_updater.close_drive')
    @patch('firmware_updater.unlock_drive')
    @patch('firmware_updater.lock_drive', return_value=(True, 0))
    @patch('firmware_updater.open_drive', return_value=9999)
    @patch('firmware_updater.send_scsi_command')
    def test_progress_callback_invoked(self, mock_send, mock_open, mock_lock, mock_unlock, mock_close):
        """progress_cb 應被呼叫 3 次 (每塊一次)"""
        mock_send.return_value = (0x00, b"", bytes(18))
        progress_records = []

        done_event = threading.Event()
        def on_done(ok, msg):
            done_event.set()

        self.engine.start(
            0,
            progress_cb=lambda cur, tot, addr: progress_records.append((cur, tot, addr)),
            done_cb=on_done,
        )
        done_event.wait(timeout=5)

        self.assertEqual(len(progress_records), 3)
        self.assertEqual(progress_records[0], (1, 3, 0x0000))
        self.assertEqual(progress_records[1], (2, 3, 0x0080))
        self.assertEqual(progress_records[2], (3, 3, 0x0100))

    @patch('firmware_updater.close_drive')
    @patch('firmware_updater.unlock_drive')
    @patch('firmware_updater.lock_drive', return_value=(True, 0))
    @patch('firmware_updater.open_drive', return_value=9999)
    @patch('firmware_updater.send_scsi_command')
    def test_cdb_byte34_correct_per_chunk(self, mock_send, mock_open, mock_lock, mock_unlock, mock_close):
        """驗證每次 send_scsi_command 收到的 CDB[3]/[4] 對應正確 Address"""
        mock_send.return_value = (0x00, b"", bytes(18))

        done_event = threading.Event()
        self.engine.start(0, done_cb=lambda ok, msg: done_event.set())
        done_event.wait(timeout=5)

        for i, c in enumerate(mock_send.call_args_list):
            cdb_arg = c[0][1]  # send_scsi_command(handle, cdb, ...)
            expected_addr = i * ADDR_INCREMENT
            self.assertEqual(cdb_arg[3], (expected_addr >> 8) & 0xFF, f"Chunk {i}: CDB[3]")
            self.assertEqual(cdb_arg[4], expected_addr & 0xFF, f"Chunk {i}: CDB[4]")

    @patch('firmware_updater.close_drive')
    @patch('firmware_updater.unlock_drive')
    @patch('firmware_updater.lock_drive', return_value=(True, 0))
    @patch('firmware_updater.open_drive', side_effect=PermissionError("Access Denied"))
    def test_open_drive_failure_handled(self, mock_open, mock_lock, mock_unlock, mock_close):
        """open_drive 拋出 PermissionError → done_cb(False, ...)"""
        done_event = threading.Event()
        results = {}
        def on_done(ok, msg):
            results['ok'] = ok
            results['msg'] = msg
            done_event.set()

        self.engine.start(0, done_cb=on_done)
        done_event.wait(timeout=5)

        self.assertFalse(results.get('ok'))
        self.assertIn("錯誤", results.get('msg', ''))


# =====================================================================
# F. GUI Tab 4 元件存在性與互動邏輯 — 9 項
# =====================================================================
class TestGuiTab4(unittest.TestCase):
    """Tab 4 GUI 元件的全面驗證"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.root = tk.Tk()
            cls.root.withdraw()
            from BusHound import ScsiToolGUI
            cls.gui = ScsiToolGUI(cls.root)
        except Exception as e:
            raise unittest.SkipTest(f"Tkinter 初始化失敗: {e}")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'root') and cls.root:
            cls.root.destroy()

    def test_tab4_frame_exists(self):
        """Tab 4 框架應存在"""
        self.assertTrue(hasattr(self.gui, 'tab4'))

    def test_fw_engine_is_correct_type(self):
        """fw_engine 應為 FirmwareUpdateEngine 實例"""
        self.assertIsInstance(self.gui.fw_engine, FirmwareUpdateEngine)

    def test_cdb_entries_count_is_16(self):
        """CDB Entry 格數應為 16"""
        self.assertEqual(len(self.gui.t4_cdb_entries), 16)

    def test_cdb_entries_default_value(self):
        """CDB Entry 預設值應全為 '00'"""
        for e in self.gui.t4_cdb_entries:
            self.assertEqual(e.get(), "00")

    def test_clear_cdb_resets_all(self):
        """t4_clear_cdb 應將所有 Entry 重設為 '00'"""
        # 先填入非零值
        self.gui.t4_cdb_entries[0].delete(0, 'end')
        self.gui.t4_cdb_entries[0].insert(0, "2A")
        self.gui.t4_cdb_entries[5].delete(0, 'end')
        self.gui.t4_cdb_entries[5].insert(0, "FF")
        # 清空
        self.gui.t4_clear_cdb()
        for e in self.gui.t4_cdb_entries:
            self.assertEqual(e.get(), "00")

    def test_read_cdb_from_entries(self):
        """_t4_read_cdb_from_entries 應正確解析 Hex 字串"""
        self.gui.t4_clear_cdb()
        self.gui.t4_cdb_entries[0].delete(0, 'end')
        self.gui.t4_cdb_entries[0].insert(0, "2A")
        self.gui.t4_cdb_entries[9].delete(0, 'end')
        self.gui.t4_cdb_entries[9].insert(0, "80")
        cdb = self.gui._t4_read_cdb_from_entries()
        self.assertEqual(len(cdb), 16)
        self.assertEqual(cdb[0], 0x2A)
        self.assertEqual(cdb[9], 0x80)
        self.assertEqual(cdb[1], 0x00)

    def test_read_cdb_invalid_hex_defaults_zero(self):
        """_t4_read_cdb_from_entries 遇到非法 Hex 應回傳 0x00"""
        self.gui.t4_clear_cdb()
        self.gui.t4_cdb_entries[0].delete(0, 'end')
        self.gui.t4_cdb_entries[0].insert(0, "ZZ")  # 非法 Hex
        cdb = self.gui._t4_read_cdb_from_entries()
        self.assertEqual(cdb[0], 0x00)

    def test_progress_bar_exists(self):
        """進度條元件應存在"""
        import tkinter.ttk as ttk
        self.assertIsInstance(self.gui.t4_progress, ttk.Progressbar)

    def test_start_addr_default_value(self):
        """起始 Address Entry 預設值應為 '0000'"""
        self.assertEqual(self.gui.t4_start_addr_entry.get(), "0000")


# =====================================================================
# G. Engine 狀態機 — 補充邊界測試 — 2 項
# =====================================================================
class TestEngineStateMachine(unittest.TestCase):
    """FirmwareUpdateEngine 狀態機邊界測試"""

    def test_start_without_chunks_logs_error(self):
        """未載入 chunks 就呼叫 start → 應呼叫 log_cb 報錯，不啟動 thread"""
        engine = FirmwareUpdateEngine()
        log_msgs = []
        engine.start(0, log_cb=lambda msg: log_msgs.append(msg))
        time.sleep(0.1)
        self.assertFalse(engine.is_running)
        self.assertTrue(any("尚未載入" in m for m in log_msgs))

    def test_default_state(self):
        """初始狀態：chunks 為空、is_running 為 False"""
        engine = FirmwareUpdateEngine()
        self.assertEqual(engine.chunks, [])
        self.assertFalse(engine.is_running)
        self.assertEqual(engine.start_address, 0x0000)
        self.assertEqual(engine.base_cdb, [0x00] * 16)


if __name__ == '__main__':
    unittest.main()
