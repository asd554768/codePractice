"""nvme_driver 模組單元測試。"""
import unittest
from unittest.mock import patch, MagicMock, call
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
    IOCTL_STORAGE_QUERY_PROPERTY,
    INVALID_HANDLE_VALUE,
    GENERIC_READ, GENERIC_WRITE,
    FILE_SHARE_READ, FILE_SHARE_WRITE, OPEN_EXISTING,
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
            # 請求 NUMD=0 (LID=0x02, 4 Bytes)
            cmd = GetLogPageCommand(lid=0x02, numd_val=0)
            data, status = driver.get_log_page(cmd)

        self.assertEqual(status, 0)
        self.assertEqual(data, b"\x12\x34\x56\x78")  # 4 Bytes
        
        # 驗證 SPC 結構中下發至設備的參數：
        # Offset 36: DataFromDeviceTransferLength 必須為精確的 4 (而不是 512)
        transfer_len_sent = struct.unpack_from("<I", captured_io_buffer.raw, 36)[0]
        self.assertEqual(transfer_len_sent, 4, f"DataFromDeviceTransferLength 應為 4，實際為 {transfer_len_sent}")
        
        # Offset 120: NVMe SQE CDW10 必須包含 NUMDL=0x00 (0x00000002)，絕不能被改成 0x007F0002
        cdw10_sent = struct.unpack_from("<I", captured_io_buffer.raw, 120)[0]
        self.assertEqual(cdw10_sent, 0x00000002, f"CDW10 應為 0x00000002，實際為 0x{cdw10_sent:08X}")

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


# =============================================================================
# Critical Bug 回歸測試：nvme_driver 缺少 Win32 常數 import
# 問題描述：_get_log_page_intel_miniport 用到 GENERIC_READ / GENERIC_WRITE /
#           FILE_SHARE_READ / FILE_SHARE_WRITE / OPEN_EXISTING，但原本 import
#           清單沒有包含這 5 個常數，導致 Scsi Port 開啟路徑 NameError 靜默失敗。
# =============================================================================

class TestWin32ConstantsImportRegression(unittest.TestCase):
    """驗證 GENERIC_READ 等 5 個 Win32 常數在 nvme_driver module scope 可正確存取。
    
    這是 Critical bug 的第一道防線：確認 import 本身不缺漏。
    無任何 side effect，不開啟任何 device handle。
    """

    def test_generic_read_accessible_in_nvme_driver_module(self):
        """GENERIC_READ 必須在 nvme_driver module scope 可存取。"""
        import core.nvme_driver as m
        self.assertTrue(
            hasattr(m, "GENERIC_READ"),
            "GENERIC_READ 在 nvme_driver module 中不可存取 — import 缺漏！"
        )
        self.assertEqual(m.GENERIC_READ, 0x80000000)

    def test_generic_write_accessible_in_nvme_driver_module(self):
        """GENERIC_WRITE 必須在 nvme_driver module scope 可存取。"""
        import core.nvme_driver as m
        self.assertTrue(hasattr(m, "GENERIC_WRITE"))
        self.assertEqual(m.GENERIC_WRITE, 0x40000000)

    def test_file_share_constants_accessible_in_nvme_driver_module(self):
        """FILE_SHARE_READ / WRITE / OPEN_EXISTING 必須在 nvme_driver module scope 可存取。"""
        import core.nvme_driver as m
        self.assertTrue(hasattr(m, "FILE_SHARE_READ"))
        self.assertTrue(hasattr(m, "FILE_SHARE_WRITE"))
        self.assertTrue(hasattr(m, "OPEN_EXISTING"))
        self.assertEqual(m.FILE_SHARE_READ, 0x00000001)
        self.assertEqual(m.FILE_SHARE_WRITE, 0x00000002)
        self.assertEqual(m.OPEN_EXISTING, 3)

    def test_all_five_win32_constants_match_win_ioctl_definitions(self):
        """5 個常數的值必須與 win_ioctl 定義完全一致 — 防止未來值被改壞。"""
        import core.nvme_driver as m
        pairs = [
            ("GENERIC_READ",    m.GENERIC_READ,    GENERIC_READ),
            ("GENERIC_WRITE",   m.GENERIC_WRITE,   GENERIC_WRITE),
            ("FILE_SHARE_READ", m.FILE_SHARE_READ, FILE_SHARE_READ),
            ("FILE_SHARE_WRITE",m.FILE_SHARE_WRITE,FILE_SHARE_WRITE),
            ("OPEN_EXISTING",   m.OPEN_EXISTING,   OPEN_EXISTING),
        ]
        for name, driver_val, ioctl_val in pairs:
            with self.subTest(constant=name):
                self.assertEqual(driver_val, ioctl_val,
                    f"{name} 在 nvme_driver ({driver_val:#x}) 與 win_ioctl ({ioctl_val:#x}) 不一致")


class TestScsiPortHandlingRegression(unittest.TestCase):
    """驗證 _get_log_page_intel_miniport 的 Scsi port 開啟路徑行為。
    
    重點：確保 CreateFileW 呼叫使用正確的常數、handle 不洩漏、
    NameError 不再靜默吞噬 Scsi port 開啟失敗。
    
    所有 mock 均不真正開啟 device，無任何 side effect。
    """

    @patch("core.nvme_driver.device_io_control")
    @patch("core.nvme_driver.open_device")
    @patch("ctypes.windll.kernel32.CloseHandle")
    @patch("ctypes.windll.kernel32.CreateFileW")
    def test_scsi_port_opened_with_correct_win32_constants(
        self, mock_create, mock_close, mock_open, mock_ioctl
    ):
        """CreateFileW 必須以正確的 GENERIC_READ|WRITE, FILE_SHARE_READ|WRITE, OPEN_EXISTING 呼叫。"""
        mock_open.return_value = 100
        fake_scsi_handle = 999

        # 第一次呼叫 (Scsi0:) 回傳有效 handle；其餘回傳 INVALID
        mock_create.side_effect = (
            [fake_scsi_handle] + [INVALID_HANDLE_VALUE] * 3
        )

        # IOCTL 永遠失敗，讓方法最終拋 OSError
        mock_ioctl.return_value = (False, 0)

        with NvmeDriver(1) as driver:
            with self.assertRaises(OSError):
                cmd = GetLogPageCommand(lid=0x02, length_bytes=512)
                driver._get_log_page_intel_miniport(cmd)

        # 確認 CreateFileW 被呼叫，且第一個 Scsi0: 的參數正確
        scsi0_call = mock_create.call_args_list[0]
        args = scsi0_call[0]  # positional args
        self.assertIn("Scsi0:", args[0])
        self.assertEqual(args[1], GENERIC_READ | GENERIC_WRITE,
                         "DesiredAccess 應為 GENERIC_READ | GENERIC_WRITE")
        self.assertEqual(args[2], FILE_SHARE_READ | FILE_SHARE_WRITE,
                         "ShareMode 應為 FILE_SHARE_READ | FILE_SHARE_WRITE")
        self.assertEqual(args[4], OPEN_EXISTING,
                         "CreationDisposition 應為 OPEN_EXISTING")

    @patch("core.nvme_driver.device_io_control")
    @patch("core.nvme_driver.open_device")
    @patch("ctypes.windll.kernel32.CloseHandle")
    @patch("ctypes.windll.kernel32.CreateFileW")
    def test_scsi_port_handles_released_on_ioctl_failure(
        self, mock_create, mock_close, mock_open, mock_ioctl
    ):
        """即使 IOCTL 失敗，已開啟的 Scsi port handle 必須被 CloseHandle 釋放（無 handle leak）。"""
        mock_open.return_value = 100
        fake_handles = [501, 502]  # Scsi0:, Scsi1: 成功開啟

        call_idx = [0]
        def create_side_effect(*args, **kwargs):
            path = args[0] if args else ""
            if "Scsi0:" in path:
                return fake_handles[0]
            if "Scsi1:" in path:
                return fake_handles[1]
            return INVALID_HANDLE_VALUE
        mock_create.side_effect = create_side_effect

        mock_ioctl.return_value = (False, 0)

        with NvmeDriver(1) as driver:
            with self.assertRaises(OSError):
                cmd = GetLogPageCommand(lid=0x02, length_bytes=512)
                driver._get_log_page_intel_miniport(cmd)

        # 確認兩個 extra handle 都被 CloseHandle 釋放
        closed = [c[0][0] for c in mock_close.call_args_list]
        self.assertIn(501, closed, "Scsi0: handle (501) 未被 CloseHandle 釋放 — handle leak！")
        self.assertIn(502, closed, "Scsi1: handle (502) 未被 CloseHandle 釋放 — handle leak！")

    @patch("core.nvme_driver.device_io_control")
    @patch("core.nvme_driver.open_device")
    @patch("ctypes.windll.kernel32.CloseHandle")
    @patch("ctypes.windll.kernel32.CreateFileW")
    def test_scsi_port_handles_released_on_ioctl_success(
        self, mock_create, mock_close, mock_open, mock_ioctl
    ):
        """IOCTL 成功時，extra Scsi handle 也必須被 CloseHandle 釋放。"""
        mock_open.return_value = 100
        fake_scsi_handle = 777
        mock_create.side_effect = (
            [fake_scsi_handle] + [INVALID_HANDLE_VALUE] * 3
        )

        def fake_ioctl(handle, ioctl_code, in_b, in_s, out_b, out_s):
            from core.win_ioctl import IOCTL_SCSI_MINIPORT
            if ioctl_code == IOCTL_SCSI_MINIPORT and handle == fake_scsi_handle:
                out_b.header.SrbIoCtrl.ReturnCode = 0
                ctypes.memmove(ctypes.byref(out_b.buffer), b"\xCC" * 512, 512)
                return True, out_s
            return False, 0

        mock_ioctl.side_effect = fake_ioctl

        with NvmeDriver(1) as driver:
            cmd = GetLogPageCommand(lid=0x02, length_bytes=512)
            data, status = driver._get_log_page_intel_miniport(cmd)

        self.assertEqual(status, 0)
        self.assertEqual(data[:4], b"\xCC\xCC\xCC\xCC")

        # 確認 extra handle 被釋放
        closed = [c[0][0] for c in mock_close.call_args_list]
        self.assertIn(fake_scsi_handle, closed,
                      "IOCTL 成功後 Scsi handle 仍未被 CloseHandle 釋放 — handle leak！")

    @patch("core.nvme_driver.device_io_control")
    @patch("core.nvme_driver.open_device")
    @patch("ctypes.windll.kernel32.CreateFileW")
    def test_all_scsi_ports_invalid_uses_only_self_handle(
        self, mock_create, mock_open, mock_ioctl
    ):
        """當所有 Scsi port 都回傳 INVALID_HANDLE_VALUE 時，IOCTL 只應使用 self.handle (100)，不額外開任何 handle。"""
        mock_open.return_value = 100
        mock_create.return_value = INVALID_HANDLE_VALUE  # 所有 Scsi port 均拒絕

        handles_seen = set()
        def track_ioctl(handle, ioctl_code, in_b, in_s, out_b, out_s):
            handles_seen.add(handle)
            return False, 0
        mock_ioctl.side_effect = track_ioctl

        with NvmeDriver(1) as driver:
            with self.assertRaises(OSError):
                cmd = GetLogPageCommand(lid=0x02, length_bytes=512)
                driver._get_log_page_intel_miniport(cmd)

        # IOCTL 只用過 self.handle (100)，沒有其他 handle
        self.assertEqual(handles_seen, {100},
                         f"IOCTL 用了非預期的 handle: {handles_seen - {100}}")

    @patch("core.nvme_driver.device_io_control")
    @patch("core.nvme_driver.open_device")
    @patch("ctypes.windll.kernel32.CloseHandle")
    @patch("ctypes.windll.kernel32.CreateFileW")
    def test_createfilew_name_error_would_fail_silently_without_fix(
        self, mock_create, mock_close, mock_open, mock_ioctl
    ):
        """回歸測試：模擬 GENERIC_READ 不存在時的情境 (NameError)。

        在修復前，NameError 被 except Exception: pass 吃掉，
        導致 Scsi port handle 永遠無法開啟，Miniport fallback 只用 self.handle。
        修復後，常數已 import，CreateFileW 可以正確被呼叫。

        此測試驗證修復後 CreateFileW 確實被呼叫（即常數不再是 NameError）。
        """
        mock_open.return_value = 100
        mock_create.return_value = INVALID_HANDLE_VALUE  # 全部拒絕，但 CreateFileW 應被呼叫到
        mock_ioctl.return_value = (False, 0)

        with NvmeDriver(1) as driver:
            with self.assertRaises(OSError):
                cmd = GetLogPageCommand(lid=0x02, length_bytes=512)
                driver._get_log_page_intel_miniport(cmd)

        # 如果 GENERIC_READ 是 NameError，CreateFileW 就不會被呼叫
        # 修復後，它應該被呼叫恰好 4 次 (Scsi0: ~ Scsi3:)
        self.assertEqual(
            mock_create.call_count, 4,
            f"CreateFileW 應被呼叫 4 次 (Scsi0~3)，實際呼叫 {mock_create.call_count} 次 — "
            "若為 0 次代表 GENERIC_READ 等常數仍有 NameError 問題！"
        )


if __name__ == "__main__":
    unittest.main()
