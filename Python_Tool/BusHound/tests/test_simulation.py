import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import tkinter as tk

# 加入 src 目錄到模組搜尋路徑
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from mock_storage import MockStorageDevice, MockWin32Driver
from backend_storage import (
    open_drive,
    close_drive,
    lock_drive,
    unlock_drive,
    send_scsi_command,
    SCSI_IOCTL_DATA_IN,
    SCSI_IOCTL_DATA_OUT,
    SCSI_IOCTL_DATA_UNSPECIFIED,
    packet_logger,
)
from BusHound import ScsiToolGUI


class TestMockStorageDeviceDirect(unittest.TestCase):
    """測試虛擬儲存裝置 (MockStorageDevice) 協定行為"""

    def setUp(self):
        self.device = MockStorageDevice(drive_index=0, model="Mock NVMe SSD", size_mb=1)

    def test_test_unit_ready(self):
        st, data, sense = self.device.execute_scsi([0x00] * 16, 0)
        self.assertEqual(st, 0x00)

    def test_inquiry(self):
        cdb = [0x12, 0x00, 0x00, 0x00, 36, 0x00] + [0] * 10
        st, data, sense = self.device.execute_scsi(cdb, 36)
        self.assertEqual(st, 0x00)
        self.assertEqual(len(data), 36)
        self.assertIn(b"MOCKDEV", data)
        self.assertIn(b"Mock NVMe SSD", data)

    def test_read_capacity(self):
        cdb = [0x25] + [0] * 15
        st, data, sense = self.device.execute_scsi(cdb, 8)
        self.assertEqual(st, 0x00)
        self.assertEqual(len(data), 8)

    def test_read_write_sector_loopback(self):
        # 寫入 512 bytes 到 LBA 2
        test_payload = bytes([i % 256 for i in range(512)])
        write_cdb = [0x2A, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x01, 0x00] + [0] * 6
        st_w, _, _ = self.device.execute_scsi(write_cdb, 0, test_payload)
        self.assertEqual(st_w, 0x00)

        # 從 LBA 2 讀回 512 bytes
        read_cdb = [0x28, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x01, 0x00] + [0] * 6
        st_r, read_data, _ = self.device.execute_scsi(read_cdb, 512)
        self.assertEqual(st_r, 0x00)
        self.assertEqual(read_data, test_payload)

    def test_lba_out_of_range(self):
        # 存取超出範圍的 LBA
        huge_lba_cdb = [0x28, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0x00, 0x00, 0x01, 0x00] + [0] * 6
        st, data, sense = self.device.execute_scsi(huge_lba_cdb, 512)
        self.assertEqual(st, 0x02)  # CHECK CONDITION
        self.assertEqual(sense[2] & 0x0F, 0x05)  # ILLEGAL REQUEST

    def test_fault_injection(self):
        # 注入硬體錯誤 (Sense Key 0x04)
        self.device.set_fault(scsi_status=0x02, sense_key=0x04, asc=0x44, ascq=0x00)
        st, data, sense = self.device.execute_scsi([0x00] * 16, 0)
        self.assertEqual(st, 0x02)
        self.assertEqual(sense[2] & 0x0F, 0x04)
        self.assertEqual(sense[12], 0x44)

        # 清除故障注入
        self.device.clear_fault()
        st_ok, _, _ = self.device.execute_scsi([0x00] * 16, 0)
        self.assertEqual(st_ok, 0x00)

    def test_ap_key_and_vuc_sequence(self):
        # 1. 尚未解鎖時發送 VUC Data-In -> 應被拒絕 (0x02)
        vuc_read_cdb = [0x06, 0xFE, 0xC2, 0x00, 0x01, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        st, _, sense = self.device.execute_scsi(vuc_read_cdb, 512)
        self.assertEqual(st, 0x02)

        # 2. 執行 AP_Key 3-step 解鎖序列
        key_data = [0x5A] * 512
        cdb1 = [0x06, 0xFE, 0xC0, 0x00, 0x01, 0x00, 0x00, 0x02] + [0] * 8
        st1, _, _ = self.device.execute_scsi(cdb1, 0, key_data)
        self.assertEqual(st1, 0x00)

        cdb2 = [0x06, 0xFE, 0xC1, 0x00, 0x00, 0x00] + [0] * 10
        st2, _, _ = self.device.execute_scsi(cdb2, 0)
        self.assertEqual(st2, 0x00)

        cdb3 = [0x06, 0xFE, 0xC3, 0x00, 0x01, 0x00, 0x00, 0x02] + [0] * 8
        st3, status_data, _ = self.device.execute_scsi(cdb3, 512)
        self.assertEqual(st3, 0x00)
        self.assertTrue(self.device.is_ap_key_unlocked)
        self.assertEqual(status_data[0], 0x00)  # Status Unlocked

        # 3. 解鎖後執行 64-Byte VUC 配置與讀取
        vuc_payload = [0x88] + [0] * 63
        st_cfg, _, _ = self.device.execute_scsi(cdb1, 0, vuc_payload)
        self.assertEqual(st_cfg, 0x00)

        st_read, data_vuc, _ = self.device.execute_scsi(vuc_read_cdb, 512)
        self.assertEqual(st_read, 0x00)
        self.assertEqual(data_vuc[0], 0x88)  # 驗證模擬資料關聯性


class TestEndToEndWithMockDriver(unittest.TestCase):
    """端到端模擬驅動整合測試 (Mock Win32 Driver IOCTL)"""

    def setUp(self):
        self.mock_driver = MockWin32Driver(device_count=2)

    def test_open_lock_scsi_unlock_close(self):
        with patch("ctypes.windll.kernel32.CreateFileW", side_effect=self.mock_driver.mock_CreateFileW), \
             patch("ctypes.windll.kernel32.CloseHandle", side_effect=self.mock_driver.mock_CloseHandle), \
             patch("ctypes.windll.kernel32.DeviceIoControl", side_effect=self.mock_driver.mock_DeviceIoControl):

            # 1. 開啟虛擬 PhysicalDrive0
            handle = open_drive(0)
            self.assertIsNotNone(handle)
            self.assertNotEqual(handle, -1)

            # 2. 鎖定裝置
            is_locked, err = lock_drive(handle)
            self.assertTrue(is_locked)
            self.assertTrue(self.mock_driver.devices[0].is_locked)

            # 3. 發送 INQUIRY 指令
            inq_cdb = [0x12, 0x00, 0x00, 0x00, 36, 0x00] + [0] * 10
            st, data, sense = send_scsi_command(
                handle, inq_cdb, 36, SCSI_IOCTL_DATA_IN, drive_label="PhysicalDrive0"
            )
            self.assertEqual(st, 0x00)
            self.assertIn(b"Virtual SCSI", data)

            # 4. 解鎖裝置
            unlock_drive(handle)
            self.assertFalse(self.mock_driver.devices[0].is_locked)

            # 5. 關閉握柄
            close_drive(handle)
            self.assertNotIn(handle, self.mock_driver.open_handles)


class TestGuiWithSimulationEnvironment(unittest.TestCase):
    """端到端 GUI 與模擬環境互動測試"""

    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
            cls.gui = ScsiToolGUI(cls.root)
        except Exception as e:
            raise unittest.SkipTest(f"Tkinter 無圖形環境: {e}")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'root') and cls.root:
            cls.root.destroy()

    def setUp(self):
        self.mock_driver = MockWin32Driver(device_count=2)
        # 設定下拉選單指向虛擬 PhysicalDrive0
        self.gui.drive_combo['values'] = ["PhysicalDrive0 - Virtual Mock SSD"]
        self.gui.drive_combo.current(0)

    def test_gui_tab1_execute_inquiry_simulation(self):
        with patch("ctypes.windll.kernel32.CreateFileW", side_effect=self.mock_driver.mock_CreateFileW), \
             patch("ctypes.windll.kernel32.CloseHandle", side_effect=self.mock_driver.mock_CloseHandle), \
             patch("ctypes.windll.kernel32.DeviceIoControl", side_effect=self.mock_driver.mock_DeviceIoControl):

            # 設定 INQUIRY CDB (0x12)
            for i, e in enumerate(self.gui.t1_cdb_entries):
                e.delete(0, tk.END)
                if i == 0: e.insert(0, "12")
                elif i == 4: e.insert(0, "24")
                else: e.insert(0, "00")

            self.gui.t1_len_entry.delete(0, tk.END)
            self.gui.t1_len_entry.insert(0, "36")
            self.gui.t1_dir_var.set(SCSI_IOCTL_DATA_IN)

            # 執行 Tab 1
            self.gui.t1_execute()
            out_text = self.gui.t1_out.get(1.0, tk.END)

            self.assertIn("INQUIRY", out_text)
            self.assertIn("GOOD (0x00)", out_text)
            self.assertIn("MOCKDEV", out_text)

    def test_gui_tab2_execute_apkey_and_vuc_simulation(self):
        with patch("ctypes.windll.kernel32.CreateFileW", side_effect=self.mock_driver.mock_CreateFileW), \
             patch("ctypes.windll.kernel32.CloseHandle", side_effect=self.mock_driver.mock_CloseHandle), \
             patch("ctypes.windll.kernel32.DeviceIoControl", side_effect=self.mock_driver.mock_DeviceIoControl), \
             patch("builtins.open", unittest.mock.mock_open(read_data=b"\x5A" * 512)), \
             patch("os.path.exists", return_value=True):

            self.gui.t2_ap_key_var.set(True)
            self.gui.t2_lock_var.set(True)
            self.gui.t2_len_entry.delete(0, tk.END)
            self.gui.t2_len_entry.insert(0, "512")
            self.gui.t2_dir_var.set(SCSI_IOCTL_DATA_IN)

            # 填入 64-Byte VUC payload (首 Byte 設為 0x99)
            for i, e in enumerate(self.gui.t2_entries):
                e.delete(0, tk.END)
                e.insert(0, "99" if i == 0 else "00")

            # 執行 Tab 2
            self.gui.t2_execute()
            out_text = self.gui.t2_out.get(1.0, tk.END)

            self.assertIn("FSCTL_LOCK_VOLUME", out_text)
            self.assertIn("[AP_KEY Auth] 解鎖成功", out_text)
            self.assertIn("[VUC Sequence] 全部指令序列執行成功", out_text)


if __name__ == "__main__":
    unittest.main()
