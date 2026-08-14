import sys
import ctypes
from ctypes import wintypes
import subprocess
import os
import threading
import time
import csv
from datetime import datetime

# ===========================================================================
# backend_storage.py v2 — BusHound 後端儲存裝置存取模組
# 新增：PacketLogger — 記錄所有自發指令的完整 CDB + Payload + Sense + 時間戳記
# ===========================================================================

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Windows API 常數
# ---------------------------------------------------------------------------
GENERIC_READ           = 0x80000000
GENERIC_WRITE          = 0x40000000
OPEN_EXISTING          = 3
FILE_SHARE_READ        = 1
FILE_SHARE_WRITE       = 2
INVALID_HANDLE_VALUE   = ctypes.c_void_p(-1).value

IOCTL_SCSI_PASS_THROUGH_DIRECT = 0x4D014
SCSI_IOCTL_DATA_OUT            = 0
SCSI_IOCTL_DATA_IN             = 1
SCSI_IOCTL_DATA_UNSPECIFIED    = 2

FSCTL_LOCK_VOLUME   = 0x00090018
FSCTL_UNLOCK_VOLUME = 0x0009001C

MAX_TRANSFER_BYTES = 256 * 1024 * 1024

# ---------------------------------------------------------------------------
# 錯誤訊息
# ---------------------------------------------------------------------------
def get_win_error_msg(code):
    buf = ctypes.create_unicode_buffer(512)
    ctypes.windll.kernel32.FormatMessageW(
        0x00001000, None, code, 0, buf, 512, None)
    return buf.value.strip() or f"Unknown error ({code})"

# ---------------------------------------------------------------------------
# ctypes 結構體
# ---------------------------------------------------------------------------
class SCSI_PASS_THROUGH_DIRECT(ctypes.Structure):
    _fields_ = [
        ("Length",             wintypes.USHORT),
        ("ScsiStatus",         ctypes.c_ubyte),
        ("PathId",             ctypes.c_ubyte),
        ("TargetId",           ctypes.c_ubyte),
        ("Lun",                ctypes.c_ubyte),
        ("CdbLength",          ctypes.c_ubyte),
        ("SenseInfoLength",    ctypes.c_ubyte),
        ("DataIn",             ctypes.c_ubyte),
        ("DataTransferLength", wintypes.ULONG),
        ("TimeOutValue",       wintypes.ULONG),
        ("DataBuffer",         ctypes.c_void_p),
        ("SenseInfoOffset",    wintypes.ULONG),
        ("Cdb",                ctypes.c_ubyte * 16),
    ]

class SENSE_DATA_BUFFER(ctypes.Structure):
    _fields_ = [("data", ctypes.c_ubyte * 24)]

# ---------------------------------------------------------------------------
# 協定解析字典
# ---------------------------------------------------------------------------
SCSI_OPCODES = {
    0x00: "TEST UNIT READY",    0x03: "REQUEST SENSE",
    0x04: "FORMAT UNIT",        0x06: "VENDOR SPECIFIC (0x06)",
    0x12: "INQUIRY",            0x1A: "MODE SENSE(6)",
    0x1B: "START STOP UNIT",    0x25: "READ CAPACITY(10)",
    0x28: "READ(10)",           0x2A: "WRITE(10)",
    0x2F: "VERIFY(10)",         0x35: "SYNCHRONIZE CACHE(10)",
    0x5A: "MODE SENSE(10)",     0x85: "ATA PASS-THROUGH(16)",
    0x88: "READ(16)",           0x8A: "WRITE(16)",
    0x9E: "SERVICE ACTION IN(16)", 0x9F: "SERVICE ACTION OUT(16)",
}

SCSI_STATUS_DICT = {
    0x00: "GOOD",                0x02: "CHECK CONDITION (發生錯誤)",
    0x04: "CONDITION MET",       0x08: "BUSY (裝置忙碌)",
    0x18: "RESERVATION CONFLICT", 0x28: "TASK SET FULL",
}

SENSE_KEYS = {
    0x00: "NO SENSE",            0x01: "RECOVERED ERROR",
    0x02: "NOT READY",           0x03: "MEDIUM ERROR",
    0x04: "HARDWARE ERROR",      0x05: "ILLEGAL REQUEST",
    0x06: "UNIT ATTENTION",      0x07: "DATA PROTECT",
    0x08: "BLANK CHECK",         0x09: "VENDOR SPECIFIC",
    0x0B: "ABORTED COMMAND",
}

DIRECTION_NAMES = {
    SCSI_IOCTL_DATA_OUT: "OUT",
    SCSI_IOCTL_DATA_IN:  "IN",
    SCSI_IOCTL_DATA_UNSPECIFIED: "NONE",
}

# ---------------------------------------------------------------------------
# 協定解析函式
# ---------------------------------------------------------------------------
def decode_cdb(cdb_bytes):
    if not cdb_bytes: return "[EMPTY COMMAND]"
    opcode = cdb_bytes[0]
    if opcode == 0x06 and len(cdb_bytes) >= 3 and cdb_bytes[1] == 0xFE:
        b2 = cdb_bytes[2]
        if b2 == 0xC0: return "[VUC / AP_KEY: CONFIG DATA-OUT (0x06)]"
        if b2 == 0xC1: return "[VUC / AP_KEY: ACTION NO-DATA/OUT (0x06)]"
        if b2 == 0xC2: return "[VUC: ACTION DATA-IN (0x06)]"
        if b2 == 0xC3: return "[VUC / AP_KEY: READ STATUS (0x06)]"
    name = SCSI_OPCODES.get(opcode, "UNKNOWN COMMAND")
    return f"[{name} (0x{opcode:02X})]"

def parse_sense_data(sense_bytes):
    if not sense_bytes or len(sense_bytes) < 14:
        return "無有效的 Sense Data"
    resp_code = sense_bytes[0] & 0x7F
    if resp_code not in (0x70, 0x71, 0x72, 0x73):
        return f"未知的 Response Code: 0x{resp_code:02X}"
    sense_key = sense_bytes[2] & 0x0F
    asc  = sense_bytes[12]
    ascq = sense_bytes[13]
    sk_str = SENSE_KEYS.get(sense_key, "UNKNOWN")
    return f"Sense Key: {sk_str} (0x{sense_key:02X}) | ASC: 0x{asc:02X} | ASCQ: 0x{ascq:02X}"

# ---------------------------------------------------------------------------
# 輔助函式
# ---------------------------------------------------------------------------
def get_physical_drives():
    drives = []
    try:
        cmd = ['powershell', '-NoProfile', '-Command',
               "Get-CimInstance Win32_DiskDrive | ForEach-Object { '{0}:::{1}' -f $_.Index, $_.Model }"]
        result = subprocess.run(cmd, capture_output=True, text=True, creationflags=0x08000000)
        for line in result.stdout.splitlines():
            if ":::" in line:
                idx, model = line.split(":::", 1)
                drives.append(f"PhysicalDrive{idx.strip()} - {model.strip()}")
    except Exception:
        pass
    return drives if drives else [f"PhysicalDrive{i}" for i in range(8)]

def hexdump(src, length=16):
    if not src: return ""
    result = []
    for i in range(0, len(src), length):
        chunk   = src[i:i + length]
        hex_str = ' '.join(f'{b:02X}' for b in chunk)
        asc_str = ''.join(chr(b) if 0x20 <= b < 0x7F else '.' for b in chunk)
        result.append(f"{i:04X}   {hex_str:<{length * 3}}   {asc_str}")
    return '\n'.join(result)

# ---------------------------------------------------------------------------
# PacketLogger — 記錄自發指令的完整封包
# ---------------------------------------------------------------------------
class PacketLogger:
    """
    Thread-safe 封包記錄器。
    每次呼叫 send_scsi_command() 後自動插入一筆記錄。
    欄位：index, timestamp, drive, direction, cdb_hex, cmd_name,
          data_len, payload_hex, scsi_status, sense_str, elapsed_ms
    """
    def __init__(self):
        self._lock    = threading.Lock()
        self._records = []          # list of dict
        self._seq     = 0
        self._enabled = False
        self._callbacks = []        # GUI callback(record) 函式清單

    def enable(self):
        with self._lock:
            self._enabled = True

    def disable(self):
        with self._lock:
            self._enabled = False

    @property
    def is_enabled(self):
        return self._enabled

    def add_callback(self, fn):
        """註冊 GUI callback，每插入一筆記錄就呼叫 fn(record)。"""
        self._callbacks.append(fn)

    def record(self, *, drive, cdb, direction, payload, scsi_status, sense, elapsed_ms):
        with self._lock:
            if not self._enabled:
                return
            self._seq += 1
            cdb_bytes  = list(cdb) if cdb else []
            pay_bytes  = list(payload) if payload else []
            sense_bytes= list(sense) if sense else []
            rec = {
                "index":       self._seq,
                "timestamp":   datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "drive":       drive,
                "direction":   DIRECTION_NAMES.get(direction, "?"),
                "cdb_hex":     " ".join(f"{b:02X}" for b in cdb_bytes),
                "cmd_name":    decode_cdb(cdb_bytes),
                "data_len":    len(pay_bytes),
                "payload_hex": " ".join(f"{b:02X}" for b in pay_bytes) if pay_bytes else "(none)",
                "scsi_status": f"0x{scsi_status:02X} - {SCSI_STATUS_DICT.get(scsi_status, 'UNKNOWN')}",
                "sense_str":   parse_sense_data(sense_bytes) if sense_bytes else "(none)",
                "elapsed_ms":  f"{elapsed_ms:.2f}",
            }
            self._records.append(rec)
        # callback 在 lock 外呼叫
        for cb in self._callbacks:
            try:
                cb(rec)
            except Exception:
                pass

    def get_all(self):
        with self._lock:
            return list(self._records)

    def clear(self):
        with self._lock:
            self._records.clear()
            self._seq = 0

    def export_csv(self, filepath):
        records = self.get_all()
        if not records:
            return 0
        fields = ["index","timestamp","drive","direction","cdb_hex","cmd_name",
                  "data_len","payload_hex","scsi_status","sense_str","elapsed_ms"]
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(records)
        return len(records)

# 全域 logger 單例，GUI 與 backend 共用
packet_logger = PacketLogger()

# ---------------------------------------------------------------------------
# 裝置控制
# ---------------------------------------------------------------------------
def open_drive(physical_drive_num):
    drive_path = f"\\\\.\\PhysicalDrive{physical_drive_num}"
    kernel32   = ctypes.windll.kernel32
    handle = kernel32.CreateFileW(
        drive_path, GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
    if handle == INVALID_HANDLE_VALUE or handle is None:
        code = kernel32.GetLastError()
        raise PermissionError(f"Open Failed [{code}]: {get_win_error_msg(code)}")
    return handle

def close_drive(handle):
    ctypes.windll.kernel32.CloseHandle(handle)

def lock_drive(handle):
    bytes_returned = wintypes.DWORD()
    kernel32 = ctypes.windll.kernel32
    result = kernel32.DeviceIoControl(
        handle, FSCTL_LOCK_VOLUME, None, 0, None, 0,
        ctypes.byref(bytes_returned), None)
    err_code = kernel32.GetLastError() if not result else 0
    return result != 0, err_code

def unlock_drive(handle):
    bytes_returned = wintypes.DWORD()
    ctypes.windll.kernel32.DeviceIoControl(
        handle, FSCTL_UNLOCK_VOLUME, None, 0, None, 0,
        ctypes.byref(bytes_returned), None)

# ---------------------------------------------------------------------------
# 核心通訊：SCSI Pass-Through（整合 PacketLogger）
# ---------------------------------------------------------------------------
def send_scsi_command(handle, cdb_bytes, data_transfer_length, direction,
                      out_data_bytes=None, drive_label="?"):
    """
    發送 SCSI Pass-Through 指令。
    回傳 (ScsiStatus: int, data: bytes, sense: bytes)
    失敗拋出 OSError。
    若 packet_logger.is_enabled，自動記錄完整 CDB + Payload + Sense + elapsed_ms。
    """
    if direction == SCSI_IOCTL_DATA_UNSPECIFIED:
        data_transfer_length = 0
        data_buffer = None
    elif direction == SCSI_IOCTL_DATA_OUT and out_data_bytes:
        data_buffer = (ctypes.c_ubyte * data_transfer_length)(
            *(out_data_bytes[:data_transfer_length]))
    else:
        data_buffer = (ctypes.c_ubyte * data_transfer_length)()

    class SPTD_WITH_SENSE(ctypes.Structure):
        _fields_ = [("sptd", SCSI_PASS_THROUGH_DIRECT), ("sense", SENSE_DATA_BUFFER)]

    combined = SPTD_WITH_SENSE()
    combined.sptd.Length             = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT)
    combined.sptd.CdbLength          = len(cdb_bytes)
    combined.sptd.DataIn             = direction
    combined.sptd.DataTransferLength = data_transfer_length
    combined.sptd.TimeOutValue       = 10

    if data_transfer_length > 0 and data_buffer is not None:
        combined.sptd.DataBuffer = ctypes.cast(ctypes.pointer(data_buffer), ctypes.c_void_p)
    else:
        combined.sptd.DataBuffer = None

    combined.sptd.SenseInfoLength = ctypes.sizeof(SENSE_DATA_BUFFER())
    combined.sptd.SenseInfoOffset = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT)
    for i, b in enumerate(cdb_bytes):
        combined.sptd.Cdb[i] = b

    bytes_returned = wintypes.DWORD()
    kernel32 = ctypes.windll.kernel32

    t_start = time.perf_counter()
    result = kernel32.DeviceIoControl(
        handle, IOCTL_SCSI_PASS_THROUGH_DIRECT,
        ctypes.byref(combined), ctypes.sizeof(combined),
        ctypes.byref(combined), ctypes.sizeof(combined),
        ctypes.byref(bytes_returned), None)
    elapsed_ms = (time.perf_counter() - t_start) * 1000

    if not result:
        code = kernel32.GetLastError()
        raise OSError(f"IOCTL Failed [{code}]: {get_win_error_msg(code)}")

    returned_data = bytes(data_buffer) if data_buffer else b""
    sense_data    = bytes(combined.sense.data)

    # 自動記錄
    packet_logger.record(
        drive=drive_label,
        cdb=list(cdb_bytes),
        direction=direction,
        payload=list(returned_data) if direction == SCSI_IOCTL_DATA_IN else
                list(out_data_bytes[:data_transfer_length]) if out_data_bytes else [],
        scsi_status=combined.sptd.ScsiStatus,
        sense=list(sense_data),
        elapsed_ms=elapsed_ms,
    )

    return combined.sptd.ScsiStatus, returned_data, sense_data
