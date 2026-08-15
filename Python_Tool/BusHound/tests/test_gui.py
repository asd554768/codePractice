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

    def test_tab3_sniffer_toggle(self):
        # 初始狀態為啟動 (Recording)
        from backend_storage import packet_logger
        self.assertTrue(packet_logger.is_enabled)

        # 切換停止
        self.gui.t3_toggle_sniffer()
        self.assertFalse(packet_logger.is_enabled)
        self.assertIn("啟動監控", self.gui.t3_toggle_btn.cget("text"))

        # 再次切換啟動
        self.gui.t3_toggle_sniffer()
        self.assertTrue(packet_logger.is_enabled)
        self.assertIn("停止監控", self.gui.t3_toggle_btn.cget("text"))

    def test_tab3_packet_insert_and_select(self):
        # 清空
        self.gui.t3_clear_packets()
        self.assertEqual(len(self.gui.t3_tree.get_children()), 0)

        # 模擬新封包進入
        rec = {
            "index": 1,
            "timestamp": "12:00:00.123",
            "drive": "PhysicalDrive0",
            "direction": "IN",
            "cdb_hex": "12 00 00 00 24 00",
            "cmd_name": "[INQUIRY (0x12)]",
            "data_len": 36,
            "payload_hex": "00 80 02 02",
            "scsi_status": "0x00 - GOOD",
            "sense_str": "(none)",
            "elapsed_ms": "1.23",
            "raw_payload": b"\x00\x80\x02\x02" + b"\x00"*32,
            "raw_cdb": b"\x12\x00\x00\x00\x24\x00",
            "raw_sense": b""
        }
        self.gui.t3_on_new_packet(rec)

        # 驗證 Treeview 有 1 筆資料
        children = self.gui.t3_tree.get_children()
        self.assertEqual(len(children), 1)

        # 選取該封包
        self.gui.t3_tree.selection_set(children[0])
        self.gui.t3_on_select_packet(None)

        # 驗證下方 Inspector 內容
        cdb_txt = self.gui.t3_cdb_txt.get(1.0, tk.END)
        self.assertIn("12 00 00 00 24 00", cdb_txt)
        dump_txt = self.gui.t3_dump_txt.get(1.0, tk.END)
        self.assertIn("00 80 02 02", dump_txt)

    def test_tab3_clear_packets(self):
        self.gui.t3_clear_packets()
        self.assertEqual(len(self.gui.t3_tree.get_children()), 0)
        self.assertEqual(self.gui.t3_count_lbl.cget("text"), "總封包數: 0")


if __name__ == "__main__":
    unittest.main()
