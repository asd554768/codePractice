import unittest
from unittest.mock import patch, MagicMock
import ctypes
import os
import sys
import tempfile
import csv

# 加入 src 目錄到模組搜尋路徑
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from backend_storage import (
    SCSI_PASS_THROUGH_DIRECT,
    SENSE_DATA_BUFFER,
    SCSI_IOCTL_DATA_OUT,
    SCSI_IOCTL_DATA_IN,
    SCSI_IOCTL_DATA_UNSPECIFIED,
    MAX_TRANSFER_BYTES,
    decode_cdb,
    parse_sense_data,
    hexdump,
    get_win_error_msg,
    get_base_dir,
    get_physical_drives,
    PacketLogger,
    packet_logger,
    open_drive,
    close_drive,
    lock_drive,
    unlock_drive,
    send_scsi_command,
)


class TestCtypesStructures(unittest.TestCase):
    """測試 ctypes 記憶體結構體大小與對齊"""

    def test_scsi_pass_through_direct_size(self):
        # 64-bit OS 下 _pack_ = 4 時結構體大小為 56 Bytes
        size = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT)
        self.assertEqual(size, 56, f"SCSI_PASS_THROUGH_DIRECT size 應為 56，實際為 {size}")

    def test_sense_data_buffer_size(self):
        size = ctypes.sizeof(SENSE_DATA_BUFFER)
        self.assertEqual(size, 24, f"SENSE_DATA_BUFFER size 應為 24，實際為 {size}")


class TestProtocolParsing(unittest.TestCase):
    """測試 CDB 與 Sense Data 解碼邏輯"""

    def test_decode_cdb_standard(self):
        self.assertIn("TEST UNIT READY", decode_cdb([0x00] * 16))
        self.assertIn("INQUIRY", decode_cdb([0x12, 0x00, 0x00, 0x00, 0x24, 0x00]))
        self.assertIn("READ(10)", decode_cdb([0x28] + [0x00] * 15))
        self.assertIn("WRITE(10)", decode_cdb([0x2A] + [0x00] * 15))

    def test_decode_cdb_vuc_and_apkey(self):
        self.assertIn("CONFIG DATA-OUT", decode_cdb([0x06, 0xFE, 0xC0] + [0x00] * 13))
        self.assertIn("ACTION NO-DATA/OUT", decode_cdb([0x06, 0xFE, 0xC1] + [0x00] * 13))
        self.assertIn("ACTION DATA-IN", decode_cdb([0x06, 0xFE, 0xC2] + [0x00] * 13))
        self.assertIn("READ STATUS", decode_cdb([0x06, 0xFE, 0xC3] + [0x00] * 13))

    def test_decode_cdb_empty_and_unknown(self):
        self.assertEqual(decode_cdb([]), "[EMPTY COMMAND]")
        self.assertIn("UNKNOWN COMMAND", decode_cdb([0xEE]))

    def test_parse_sense_data_valid(self):
        # 構造標準 18-byte Sense Data (0x70 Current Error, SenseKey=0x05 ILLEGAL REQUEST, ASC=0x20, ASCQ=0x00)
        sense = [0x70, 0x00, 0x05, 0x00, 0x00, 0x00, 0x00, 0x0A,
                 0x00, 0x00, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00]
        parsed = parse_sense_data(sense)
        self.assertIn("ILLEGAL REQUEST", parsed)
        self.assertIn("0x05", parsed)
        self.assertIn("0x20", parsed)
        self.assertIn("0x00", parsed)

    def test_parse_sense_data_too_short(self):
        self.assertEqual(parse_sense_data([0x70, 0x00]), "無有效的 Sense Data")
        self.assertEqual(parse_sense_data([]), "無有效的 Sense Data")

    def test_parse_sense_data_invalid_response_code(self):
        sense = [0x50] + [0x00] * 15
        parsed = parse_sense_data(sense)
        self.assertIn("未知的 Response Code", parsed)


class TestHelpers(unittest.TestCase):
    """測試輔助函式 (hexdump, error message, drive enumeration)"""

    def test_hexdump_basic(self):
        data = b"\x00\x01\x02\x03ABCD"
        dump = hexdump(data, length=16)
        self.assertIn("0000", dump)
        self.assertIn("00 01 02 03 41 42 43 44", dump)
        self.assertIn("....ABCD", dump)

    def test_hexdump_empty(self):
        self.assertEqual(hexdump(b""), "")
        self.assertEqual(hexdump(None), "")

    def test_get_win_error_msg(self):
        msg = get_win_error_msg(5)  # ERROR_ACCESS_DENIED
        self.assertTrue(len(msg) > 0)
        self.assertNotEqual(msg, "Unknown error (5)")

    def test_get_base_dir(self):
        base_dir = get_base_dir()
        self.assertTrue(os.path.isdir(base_dir))

    @patch("subprocess.run")
    def test_get_physical_drives_success(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="1:::CT500MX500SSD1\n2:::INTEL SSDPEKNU512GZ\n0:::SATA SSD\n",
            stderr=""
        )
        drives = get_physical_drives()
        self.assertEqual(len(drives), 3)
        self.assertEqual(drives[0], "PhysicalDrive1 - CT500MX500SSD1")
        self.assertEqual(drives[1], "PhysicalDrive2 - INTEL SSDPEKNU512GZ")
        self.assertEqual(drives[2], "PhysicalDrive0 - SATA SSD")

    @patch("subprocess.run", side_effect=Exception("PowerShell failed"))
    def test_get_physical_drives_fallback(self, mock_run):
        drives = get_physical_drives()
        self.assertEqual(len(drives), 8)
        self.assertEqual(drives[0], "PhysicalDrive0")
        self.assertEqual(drives[7], "PhysicalDrive7")


class TestPacketLogger(unittest.TestCase):
    """測試 PacketLogger 核心功能"""

    def setUp(self):
        self.logger = PacketLogger()

    def test_enable_disable(self):
        self.assertFalse(self.logger.is_enabled)
        self.logger.enable()
        self.assertTrue(self.logger.is_enabled)
        self.logger.disable()
        self.assertFalse(self.logger.is_enabled)

    def test_record_when_disabled(self):
        self.logger.record(
            drive="PhysicalDrive0",
            cdb=[0x00] * 16,
            direction=SCSI_IOCTL_DATA_UNSPECIFIED,
            payload=[],
            scsi_status=0x00,
            sense=[],
            elapsed_ms=1.23,
        )
        self.assertEqual(len(self.logger.get_all()), 0)

    def test_record_when_enabled(self):
        self.logger.enable()
        self.logger.record(
            drive="PhysicalDrive1",
            cdb=[0x12, 0x00, 0x00, 0x00, 0x24, 0x00] + [0] * 10,
            direction=SCSI_IOCTL_DATA_IN,
            payload=[0x00, 0x80, 0x02],
            scsi_status=0x00,
            sense=[],
            elapsed_ms=2.45,
        )
        records = self.logger.get_all()
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec["index"], 1)
        self.assertEqual(rec["drive"], "PhysicalDrive1")
        self.assertEqual(rec["direction"], "IN")
        self.assertIn("INQUIRY", rec["cmd_name"])
        self.assertEqual(rec["data_len"], 3)
        self.assertEqual(rec["payload_hex"], "00 80 02")
        self.assertIn("0x00", rec["scsi_status"])
        self.assertEqual(rec["elapsed_ms"], "2.45")

    def test_callback_invoked(self):
        self.logger.enable()
        received = []
        self.logger.add_callback(lambda r: received.append(r))
        self.logger.record(
            drive="PhysicalDrive0",
            cdb=[0x00] * 16,
            direction=SCSI_IOCTL_DATA_UNSPECIFIED,
            payload=[],
            scsi_status=0x00,
            sense=[],
            elapsed_ms=0.5,
        )
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["index"], 1)

    def test_clear(self):
        self.logger.enable()
        self.logger.record(
            drive="PhysicalDrive0",
            cdb=[0x00] * 16,
            direction=SCSI_IOCTL_DATA_UNSPECIFIED,
            payload=[],
            scsi_status=0x00,
            sense=[],
            elapsed_ms=0.5,
        )
        self.assertEqual(len(self.logger.get_all()), 1)
        self.logger.clear()
        self.assertEqual(len(self.logger.get_all()), 0)

    def test_export_csv(self):
        self.logger.enable()
        self.logger.record(
            drive="PhysicalDrive1",
            cdb=[0x00] * 16,
            direction=SCSI_IOCTL_DATA_UNSPECIFIED,
            payload=[],
            scsi_status=0x00,
            sense=[],
            elapsed_ms=1.1,
        )
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp_path = tmp.name

        try:
            count = self.logger.export_csv(tmp_path)
            self.assertEqual(count, 1)
            with open(tmp_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["drive"], "PhysicalDrive1")
                self.assertEqual(rows[0]["direction"], "NONE")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class TestScsiIoControl(unittest.TestCase):
    """測試 SCSI 指令發送與磁碟鎖定邏輯 (Mock DeviceIoControl)"""

    @patch("ctypes.windll.kernel32.DeviceIoControl")
    def test_send_scsi_command_success(self, mock_ioctl):
        # 模擬 DeviceIoControl 成功 (回傳非零)
        mock_ioctl.return_value = 1

        cdb = [0x00] * 16
        status, data, sense = send_scsi_command(
            handle=1234,
            cdb_bytes=cdb,
            data_transfer_length=0,
            direction=SCSI_IOCTL_DATA_UNSPECIFIED,
            drive_label="PhysicalDrive0"
        )
        self.assertEqual(status, 0)
        self.assertEqual(data, b"")
        self.assertTrue(mock_ioctl.called)

    @patch("ctypes.windll.kernel32.DeviceIoControl")
    @patch("ctypes.windll.kernel32.GetLastError")
    def test_send_scsi_command_failure(self, mock_get_last_error, mock_ioctl):
        # 模擬 DeviceIoControl 失敗 (回傳 0)
        mock_ioctl.return_value = 0
        mock_get_last_error.return_value = 87  # ERROR_INVALID_PARAMETER

        with self.assertRaises(OSError) as ctx:
            send_scsi_command(
                handle=1234,
                cdb_bytes=[0x00] * 16,
                data_transfer_length=0,
                direction=SCSI_IOCTL_DATA_UNSPECIFIED,
            )
        self.assertIn("IOCTL Failed [87]", str(ctx.exception))

    @patch("ctypes.windll.kernel32.DeviceIoControl")
    def test_lock_and_unlock_drive(self, mock_ioctl):
        mock_ioctl.return_value = 1
        locked, err = lock_drive(1234)
        self.assertTrue(locked)
        self.assertEqual(err, 0)

        # unlock_drive 不應拋出異常
        unlock_drive(1234)


if __name__ == "__main__":
    unittest.main()
