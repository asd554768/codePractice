"""Windows WinRing0 Kernel Driver Service Manager & Direct Physical Memory Access.

提供免外部 DLL、純 Python 核心服務載入與實體記憶體讀寫。
"""
import ctypes
from ctypes import wintypes
import os
import struct
import sys
from typing import Optional, Tuple

# Win32 SC Manager Constants
SC_MANAGER_ALL_ACCESS = 0xF003F
SERVICE_ALL_ACCESS = 0xF01FF
SERVICE_KERNEL_DRIVER = 0x00000001
SERVICE_DEMAND_START = 0x00000003
SERVICE_ERROR_NORMAL = 0x00000001
SERVICE_CONTROL_STOP = 0x00000001

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
INVALID_HANDLE_VALUE = -1

# IOCTLs
IOCTL_OLS_READ_MEMORY = 0x9C406104
IOCTL_OLS_WRITE_MEMORY = 0x9C40A108

DRIVER_ID = "WinRing0_1_2_0"
DEVICE_NAME = r"\\.\WinRing0_1_2_0"


class WinRing0Driver:
    """WinRing0 核心驅動服務與通訊封裝。"""

    def __init__(self, sys_path: Optional[str] = None):
        if sys.platform != "win32":
            raise RuntimeError("此模組僅支援 Windows 平臺")

        self.sys_path = self._locate_sys_file(sys_path)
        self.device_handle = INVALID_HANDLE_VALUE
        self._installed = False
        self._start_and_open()

    def _locate_sys_file(self, custom_path: Optional[str]) -> str:
        meipass = getattr(sys, "_MEIPASS", "")
        exe_dir = os.path.dirname(os.path.abspath(sys.executable)) if hasattr(sys, "executable") else ""
        candidates = [
            custom_path,
            os.path.join(meipass, "WinRing0x64.sys") if meipass else None,
            os.path.join(exe_dir, "WinRing0x64.sys") if exe_dir else None,
            os.path.join(os.getcwd(), "WinRing0x64.sys"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "WinRing0x64.sys"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "WinRing0x64.sys"),
            os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "System32", "drivers", "WinRing0x64.sys"),
        ]
        for p in candidates:
            if p and os.path.exists(p):
                return os.path.abspath(p)
        return os.path.abspath("WinRing0x64.sys")

    def _start_and_open(self):
        # 1. 嘗試直接開啟既有裝置
        self.device_handle = ctypes.windll.kernel32.CreateFileW(
            DEVICE_NAME,
            GENERIC_READ | GENERIC_WRITE,
            0,
            None,
            OPEN_EXISTING,
            0,
            None
        )
        if self.device_handle != INVALID_HANDLE_VALUE:
            return

        # 2. 若未載入，透過 Service Control Manager 註冊並啟動服務
        if not os.path.exists(self.sys_path):
            raise FileNotFoundError(f"找不到 WinRing0x64.sys 驅動檔案: {self.sys_path}")

        advapi32 = ctypes.windll.advapi32
        schSCManager = advapi32.OpenSCManagerW(None, None, SC_MANAGER_ALL_ACCESS)
        if not schSCManager:
            raise PermissionError(f"無法開啟 Service Control Manager (LastError={ctypes.GetLastError()})，請以管理員身分執行")

        try:
            schService = advapi32.CreateServiceW(
                schSCManager,
                DRIVER_ID,
                DRIVER_ID,
                SERVICE_ALL_ACCESS,
                SERVICE_KERNEL_DRIVER,
                SERVICE_DEMAND_START,
                SERVICE_ERROR_NORMAL,
                self.sys_path,
                None,
                None,
                None,
                None,
                None
            )
            if not schService:
                err = ctypes.GetLastError()
                if err == 1073:  # ERROR_SERVICE_EXISTS
                    schService = advapi32.OpenServiceW(schSCManager, DRIVER_ID, SERVICE_ALL_ACCESS)
                else:
                    raise OSError(f"建立驅動服務失敗 (LastError={err})")

            # 啟動服務
            start_ok = advapi32.StartServiceW(schService, 0, None)
            if not start_ok:
                start_err = ctypes.GetLastError()
                # 1056 = ERROR_SERVICE_ALREADY_RUNNING
                if start_err != 1056:
                    advapi32.CloseServiceHandle(schService)
                    if start_err == 1275:
                        raise OSError("WinRing0x64.sys 驅動被系統封鎖 (Error 1275: ERROR_DRIVER_BLOCKED)。請檢查 Windows 易受攻擊驅動程式封鎖清單。")
                    elif start_err == 577:
                        raise OSError("WinRing0x64.sys 數位簽章未通過 Windows 驗證 (Error 577)。")
                    else:
                        raise OSError(f"啟動 WinRing0 驅動服務失敗 (LastError={start_err})")

            advapi32.CloseServiceHandle(schService)
            self._installed = True
        finally:
            advapi32.CloseServiceHandle(schSCManager)

        # 3. 重新開啟裝置 Handle
        self.device_handle = ctypes.windll.kernel32.CreateFileW(
            DEVICE_NAME,
            GENERIC_READ | GENERIC_WRITE,
            0,
            None,
            OPEN_EXISTING,
            0,
            None
        )
        if self.device_handle == INVALID_HANDLE_VALUE:
            err = ctypes.GetLastError()
            raise OSError(f"無法開啟 WinRing0 驅動裝置 \\\\.\\WinRing0_1_2_0 (LastError={err})")

    def read_physical_memory(self, phys_addr: int, size_bytes: int, unit_size: int = 1) -> bytes:
        """讀取實體記憶體。
        
        Args:
            phys_addr: 64-bit 實體位址
            size_bytes: 總長度
            unit_size: 單位大小 (1, 2, 4)
        """
        count = size_bytes // unit_size
        in_buf = struct.pack("<QII", phys_addr, unit_size, count)
        out_buf = ctypes.create_string_buffer(size_bytes)
        bytes_returned = wintypes.DWORD()

        res = ctypes.windll.kernel32.DeviceIoControl(
            self.device_handle,
            IOCTL_OLS_READ_MEMORY,
            in_buf,
            len(in_buf),
            out_buf,
            size_bytes,
            ctypes.byref(bytes_returned),
            None
        )
        if not res:
            raise OSError(f"ReadPhysicalMemory 失敗 (Addr=0x{phys_addr:X}, LastError={ctypes.GetLastError()})")
        return out_buf.raw[:size_bytes]

    def write_physical_memory(self, phys_addr: int, data: bytes, unit_size: int = 1) -> bool:
        """寫入實體記憶體。
        
        Args:
            phys_addr: 64-bit 實體位址
            data: 要寫入的二進位資料
            unit_size: 單位大小 (1, 2, 4)
        """
        size_bytes = len(data)
        count = size_bytes // unit_size
        header = struct.pack("<QII", phys_addr, unit_size, count)
        in_buf = header + data
        bytes_returned = wintypes.DWORD()

        res = ctypes.windll.kernel32.DeviceIoControl(
            self.device_handle,
            IOCTL_OLS_WRITE_MEMORY,
            in_buf,
            len(in_buf),
            None,
            0,
            ctypes.byref(bytes_returned),
            None
        )
        if not res:
            raise OSError(f"WritePhysicalMemory 失敗 (Addr=0x{phys_addr:X}, LastError={ctypes.GetLastError()})")
        return True

    def close(self):
        """關閉裝置 Handle。"""
        if self.device_handle != INVALID_HANDLE_VALUE:
            ctypes.windll.kernel32.CloseHandle(self.device_handle)
            self.device_handle = INVALID_HANDLE_VALUE

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
