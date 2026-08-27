"""Windows IOCTL ctypes 結構定義。"""
import ctypes
import ctypes.wintypes as wintypes
from typing import Tuple

# Windows 常數
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = -1

IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
IOCTL_STORAGE_PROTOCOL_COMMAND = 0x002DD3C0
IOCTL_DISK_GET_DRIVE_GEOMETRY = 0x00070000
IOCTL_SCSI_MINIPORT = 0x0004D008
NVME_PASS_THROUGH_SRB_IO_CODE = 0xE0002000

# Storage Protocol Structure Version
STORAGE_PROTOCOL_STRUCTURE_VERSION = 1

# Protocol & Data Type (Windows SDK ntddstor.h)
PROTOCOL_TYPE_NVME = 3
STORAGE_PROTOCOL_SPECIFIC_NVME_ADMIN_COMMAND = 1
STORAGE_PROTOCOL_SPECIFIC_NVME_NVM_COMMAND = 2
STORAGE_PROTOCOL_COMMAND_FLAG_ADAPTER_REQUEST = 0x80000000
STORAGE_PROTOCOL_STATUS_SUCCESS = 0
NVME_DATA_TYPE_LOG_PAGE = 2
BUS_TYPE_NVME = 17

class STORAGE_PROTOCOL_SPECIFIC_DATA(ctypes.Structure):
    _fields_ = [
        ("ProtocolType", wintypes.DWORD),
        ("DataType", wintypes.DWORD),
        ("ProtocolDataRequestValue", wintypes.DWORD),
        ("ProtocolDataRequestSubValue", wintypes.DWORD),
        ("ProtocolDataOffset", wintypes.DWORD),
        ("ProtocolDataLength", wintypes.DWORD),
        ("FixedProtocolReturnData", wintypes.DWORD),
        ("ProtocolDataRequestSubValue2", wintypes.DWORD),
        ("ProtocolDataRequestSubValue3", wintypes.DWORD),
        ("Reserved", wintypes.DWORD),
    ]

class STORAGE_PROPERTY_QUERY(ctypes.Structure):
    _fields_ = [
        ("PropertyId", wintypes.DWORD),
        ("QueryType", wintypes.DWORD),
        ("AdditionalParameters", wintypes.BYTE * 1),
    ]

class STORAGE_DEVICE_DESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ("Version", wintypes.DWORD),
        ("Size", wintypes.DWORD),
        ("DeviceType", wintypes.BYTE),
        ("DeviceTypeModifier", wintypes.BYTE),
        ("RemovableMedia", wintypes.BOOLEAN),
        ("CommandQueueing", wintypes.BOOLEAN),
        ("VendorIdOffset", wintypes.DWORD),
        ("ProductIdOffset", wintypes.DWORD),
        ("ProductRevisionOffset", wintypes.DWORD),
        ("SerialNumberOffset", wintypes.DWORD),
        ("BusType", wintypes.DWORD),
        ("RawPropertiesLength", wintypes.DWORD),
        ("RawDeviceProperties", wintypes.BYTE * 1),
    ]

class STORAGE_PROTOCOL_COMMAND(ctypes.Structure):
    """Windows SDK ntddstor.h 標準 STORAGE_PROTOCOL_COMMAND 結構 (144 Bytes)。"""
    _fields_ = [
        ("Version", wintypes.DWORD),                      # STORAGE_PROTOCOL_STRUCTURE_VERSION (1)
        ("Length", wintypes.DWORD),                       # sizeof(STORAGE_PROTOCOL_COMMAND)
        ("ProtocolType", wintypes.DWORD),                 # ProtocolTypeNvme (1)
        ("Flags", wintypes.DWORD),                        # STORAGE_PROTOCOL_COMMAND_FLAG_ADAPTER_REQUEST (0x80000000)
        ("ReturnStatus", wintypes.DWORD),                 # return value from driver
        ("ErrorCode", wintypes.DWORD),                    # return error code
        ("CommandLength", wintypes.DWORD),                # 64
        ("ErrorInfoLength", wintypes.DWORD),              # 0
        ("DataToDeviceTransferLength", wintypes.DWORD),   # 0 for read
        ("DataFromDeviceTransferLength", wintypes.DWORD), # aligned bytes to read
        ("TimeOutValue", wintypes.DWORD),                 # seconds
        ("ErrorInfoOffset", wintypes.DWORD),              # 0
        ("DataToDeviceBufferOffset", wintypes.DWORD),     # 0
        ("DataFromDeviceBufferOffset", wintypes.DWORD),   # offset from beginning of struct
        ("CommandSpecific", wintypes.DWORD),              # STORAGE_PROTOCOL_SPECIFIC_NVME_ADMIN_COMMAND (1)
        ("Reserved0", wintypes.DWORD),
        ("FixedProtocolReturnData", wintypes.DWORD),      # NVMe CQE DW0
        ("FixedProtocolReturnDataSub", wintypes.DWORD),   # NVMe CQE DW1
        ("Reserved1", wintypes.DWORD * 2),
        ("Command", wintypes.BYTE * 64),                  # NVMe SQE (64 bytes)
    ]


class SRB_IO_CONTROL(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("HeaderLength", wintypes.DWORD),  # sizeof(SRB_IO_CONTROL) = 28
        ("Signature", ctypes.c_char * 8), # b"NvmeMini"
        ("Timeout", wintypes.DWORD),       # 10
        ("ControlCode", wintypes.DWORD),   # 0xE0002000
        ("ReturnCode", wintypes.DWORD),
        ("Length", wintypes.DWORD),
    ]


class NVME_PASS_THROUGH_IOCTL(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("SrbIoCtrl", SRB_IO_CONTROL),
        ("VendorSpecific", wintypes.DWORD * 6),
        ("NVMeCmd", wintypes.DWORD * 16),
        ("CplEntry", wintypes.DWORD * 4),
        ("Direction", wintypes.DWORD),      # 0=No, 1=Out, 2=In, 3=I/O
        ("QueueId", wintypes.DWORD),        # 0=AdminQ
        ("DataBufferLen", wintypes.DWORD),  # buffer len
        ("MetaDataLen", wintypes.DWORD),
        ("ReturnBufferLen", wintypes.DWORD),
    ]


IOCTL_DISK_GET_DRIVE_GEOMETRY = 0x00070000


def open_device_query(physical_drive_number: int) -> int:
    r"""以最低權限 (DesiredAccess=0) 開啟 \\.\PhysicalDriveN 僅供屬性查詢，無需管理員寫入權限即可列舉設備。"""
    import sys
    if sys.platform != "win32":
        raise RuntimeError("此功能僅支援 Windows 平臺")
        
    path = f"\\\\.\\PhysicalDrive{physical_drive_number}"
    handle = ctypes.windll.kernel32.CreateFileW(
        path,
        0,  # FILE_READ_ATTRIBUTES
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None
    )
    if handle == INVALID_HANDLE_VALUE:
        raise OSError(f"無法開啟 {path}，錯誤碼: {ctypes.GetLastError()}")
    return handle


def open_device(physical_drive_number: int) -> int:
    r"""開啟 \\.\PhysicalDriveN 進行 NVMe 指令下發 (需 GENERIC_READ | GENERIC_WRITE 管理員權限)。"""
    import sys
    if sys.platform != "win32":
        raise RuntimeError("此功能僅支援 Windows 平臺")
        
    path = f"\\\\.\\PhysicalDrive{physical_drive_number}"
    handle = ctypes.windll.kernel32.CreateFileW(
        path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None
    )
    if handle == INVALID_HANDLE_VALUE:
        err = ctypes.GetLastError()
        if err == 5:  # ERROR_ACCESS_DENIED
            raise PermissionError(
                f"無法存取 {path} (錯誤碼 5: 存取被拒)。\n"
                "下發 NVMe Pass-Through 指令必須具備系統管理員權限，請右鍵點擊程式選擇「以系統管理員身分執行」。"
            )
        raise OSError(f"無法開啟 {path}，Windows 錯誤碼: {err}")
    return handle

def close_device(handle: int) -> None:
    """關閉 handle"""
    if handle and handle != INVALID_HANDLE_VALUE:
        ctypes.windll.kernel32.CloseHandle(handle)

def device_io_control(handle: int, ioctl_code: int, in_buffer: ctypes.Structure, in_size: int, out_buffer: ctypes.Structure, out_size: int) -> Tuple[bool, int]:
    """執行 DeviceIoControl"""
    bytes_returned = wintypes.DWORD()
    result = ctypes.windll.kernel32.DeviceIoControl(
        handle,
        ioctl_code,
        ctypes.byref(in_buffer) if in_buffer else None,
        in_size,
        ctypes.byref(out_buffer) if out_buffer else None,
        out_size,
        ctypes.byref(bytes_returned),
        None
    )
    return bool(result), bytes_returned.value
