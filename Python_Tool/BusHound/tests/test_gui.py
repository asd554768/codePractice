import unittest
from unittest.mock import patch, MagicMock
import tkinter as tk
import os
import sys

# 加入 src 目錄到模組搜尋路徑
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from BusHound import ScsiToolGUI
from backend_storage import MAX_TRANSFER_BYTES


class TestGuiLogic(unittest.TestCase):
    """測試 GUI 內部狀態、資料轉換與事件邏輯"""

    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()  # 隱藏主視窗，避免彈出干擾
            cls.gui = ScsiToolGUI(cls.root)
        except Exception as e:
            raise unittest.SkipTest(f"Tkinter 初始化失敗 (無圖形環境): {e}")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'root') and cls.root:
            cls.root.destroy()

    def test_tab1_clear_cdb(self):
        # 填入非 0 值後呼叫清空
        self.gui.t1_cdb_entries[0].delete(0, tk.END)
        self.gui.t1_cdb_entries[0].insert(0, "12")
        self.gui.t1_clear_cdb()
        for e in self.gui.t1_cdb_entries:
            self.assertEqual(e.get(), "00")

    def test_tab2_clear_grid(self):
        self.gui.t2_entries[0].delete(0, tk.END)
        self.gui.t2_entries[0].insert(0, "FF")
        self.gui.t2_clear_grid()
        for e in self.gui.t2_entries:
            self.assertEqual(e.get(), "00")

    @patch("tkinter.messagebox.askyesno", return_value=True)
    def test_tab2_auto_parse_length_apply(self, mock_ask):
        # 構造 64 bytes 資料，Offset 40~43 設為 0x00000004 (4 sectors -> 16 bytes)
        raw_payload = bytearray([0] * 64)
        raw_payload[40:44] = (4).to_bytes(4, byteorder="little")

        with patch("tkinter.filedialog.askopenfilename", return_value="dummy.bin"), \
             patch("builtins.open", unittest.mock.mock_open(read_data=bytes(raw_payload))):
            self.gui.t2_load_64b_bin()

        self.assertEqual(self.gui.t2_len_entry.get(), "16")

    @patch("tkinter.messagebox.askyesno", return_value=False)
    def test_tab2_auto_parse_length_reject(self, mock_ask):
        self.gui.t2_len_entry.delete(0, tk.END)
        self.gui.t2_len_entry.insert(0, "0")

        raw_payload = bytearray([0] * 64)
        raw_payload[40:44] = (4).to_bytes(4, byteorder="little")

        with patch("tkinter.filedialog.askopenfilename", return_value="dummy.bin"), \
             patch("builtins.open", unittest.mock.mock_open(read_data=bytes(raw_payload))):
            self.gui.t2_load_64b_bin()

        self.assertEqual(self.gui.t2_len_entry.get(), "0")

    def test_tab2_auto_parse_length_exceed_max(self):
        self.gui.t2_len_entry.delete(0, tk.END)
        self.gui.t2_len_entry.insert(0, "0")

        # 構造超大長度 (> MAX_TRANSFER_BYTES 256MB)
        huge_val = (MAX_TRANSFER_BYTES // 4) + 100
        raw_payload = bytearray([0] * 64)
        raw_payload[40:44] = huge_val.to_bytes(4, byteorder="little")

        with patch("tkinter.filedialog.askopenfilename", return_value="dummy.bin"), \
             patch("builtins.open", unittest.mock.mock_open(read_data=bytes(raw_payload))):
            self.gui.t2_load_64b_bin()

        # 超出上限應略過自動填入
        self.assertEqual(self.gui.t2_len_entry.get(), "0")


if __name__ == "__main__":
    unittest.main()
