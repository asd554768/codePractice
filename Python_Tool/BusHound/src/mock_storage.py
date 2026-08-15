"""
mock_storage.py — 虛擬儲存裝置 (Virtual Storage Device Emulator)
為 BusHound 提供完整的 SCSI / VUC 指令模擬環境，支援：
1. 標準 SCSI 協定 (INQUIRY, TUR, READ10, WRITE10, READ CAPACITY 等)
2. 特權認證 AP_KEY 3-Step 解鎖協定
3. 64-Byte VUC (Vendor Unique Command) 3-Phase 通訊協議
4. 故障注入 (Fault Injection) 與 Sense Data 產生
5. 虛擬磁區 (Virtual LBA Sector Buffer) 讀寫
6. Windows IOCTL / SPTD / 磁碟鎖定攔截模擬器 (Mock Driver)
"""

import struct
import time
import os
from ctypes import Structure, sizeof, byref


class MockStorageDevice:
    """虛擬實體磁碟模擬核心 (Virtual PhysicalDrive Emulator)"""

    def __init__(self, drive_index=0, model="BusHound Virtual NVMe SSD", size_mb=16):
        self.drive_index = drive_index
        self.model = model
        self.size_bytes = size_mb * 1024 * 1024
        self.sector_size = 512
        self.total_sectors = self.size_bytes // self.sector_size

        # 虛擬磁區資料 (In-Memory LBA Buffer)
        self.lba_storage = bytearray(self.size_bytes)

        # 狀態暫存器
        self.is_locked = False
        self.is_ap_key_unlocked = False
        self.ap_key_buffer = bytearray(512)
        self.vuc_config_payload = bytearray(512)
        self.vuc_last_status = 0x00

        # Sense Data 暫存器 (最後一次錯誤)
        self.last_sense_key = 0x00
        self.last_asc = 0x00
        self.last_ascq = 0x00

        # 故障注入開關
        self.fault_inject_status = None   # 若設定則強制回傳特定 SCSI Status (如 0x02)
        self.fault_inject_sense = None    # (sense_key, asc, ascq)

    def set_fault(self, scsi_status=0x02, sense_key=0x05, asc=0x20, ascq=0x00):
        """注入故障 (Fault Injection)"""
        self.fault_inject_status = scsi_status
        self.fault_inject_sense = (sense_key, asc, ascq)

    def clear_fault(self):
        """清除故障注入"""
        self.fault_inject_status = None
        self.fault_inject_sense = None

    def _generate_sense_data(self, sense_key, asc, ascq):
        """生成標準 18-Byte Fixed Format Sense Data"""
        sense = bytearray(18)
        sense[0] = 0x70          # Current error, fixed format
        sense[2] = sense_key & 0x0F
        sense[7] = 0x0A          # Additional sense length = 10 (total 18)
        sense[12] = asc
        sense[13] = ascq
        return bytes(sense)

    def execute_scsi(self, cdb_bytes, data_in_len, out_payload=None):
        """
        模擬處理 SCSI 指令
        回傳: (scsi_status: int, returned_data: bytes, sense_data: bytes)
        """
        if not cdb_bytes:
            return 0x02, b"", self._generate_sense_data(0x05, 0x24, 0x00)

        opcode = cdb_bytes[0]

        # 1. 檢查是否觸發故障注入
        if self.fault_inject_status is not None:
            sk, asc, ascq = self.fault_inject_sense or (0x04, 0x00, 0x00)
            return self.fault_inject_status, b"", self._generate_sense_data(sk, asc, ascq)

        # 2. 特權 VUC / AP_KEY 系列指令 (0x06 0xFE)
        if opcode == 0x06 and len(cdb_bytes) >= 3 and cdb_bytes[1] == 0xFE:
            return self._handle_vendor_command(cdb_bytes, data_in_len, out_payload)

        # 3. 標準 SCSI 指令處理
        # 0x00: TEST UNIT READY
        if opcode == 0x00:
            return 0x00, b"", bytes(18)

        # 0x12: INQUIRY
        elif opcode == 0x12:
            alloc_len = cdb_bytes[4] if len(cdb_bytes) > 4 else 36
            alloc_len = min(alloc_len, data_in_len) if data_in_len > 0 else 36
            resp = bytearray(alloc_len)
            resp[0] = 0x00  # Direct access block device
            resp[1] = 0x80  # RMB = 1 / Connected
            resp[2] = 0x02  # SCSI-2 / SPC compliance
            resp[3] = 0x02  # Response data format
            resp[4] = max(0, alloc_len - 5)  # Additional length
            
            # Vendor (8 bytes)
            vendor_bytes = b"MOCKDEV "
            resp[8:16] = vendor_bytes[:8]
            # Product ID (16 bytes)
            model_bytes = self.model.encode('ascii', 'replace').ljust(16)[:16]
            resp[16:32] = model_bytes
            # Revision (4 bytes)
            resp[32:36] = b"v2.0"
            return 0x00, bytes(resp), bytes(18)

        # 0x25: READ CAPACITY (10)
        elif opcode == 0x25:
            last_lba = self.total_sectors - 1
            block_size = self.sector_size
            resp = struct.pack(">II", last_lba, block_size)
            return 0x00, resp, bytes(18)

        # 0x28: READ (10)
        elif opcode == 0x28:
            if len(cdb_bytes) < 10:
                return 0x02, b"", self._generate_sense_data(0x05, 0x24, 0x00)
            lba = (cdb_bytes[2] << 24) | (cdb_bytes[3] << 16) | (cdb_bytes[4] << 8) | cdb_bytes[5]
            transfer_blocks = (cdb_bytes[7] << 8) | cdb_bytes[8]
            
            if lba + transfer_blocks > self.total_sectors:
                # LBA Out of Range
                return 0x02, b"", self._generate_sense_data(0x05, 0x21, 0x00)
            
            start_pos = lba * self.sector_size
            end_pos = start_pos + (transfer_blocks * self.sector_size)
            read_bytes = self.lba_storage[start_pos:end_pos]
            return 0x00, bytes(read_bytes), bytes(18)

        # 0x2A: WRITE (10)
        elif opcode == 0x2A:
            if len(cdb_bytes) < 10:
                return 0x02, b"", self._generate_sense_data(0x05, 0x24, 0x00)
            lba = (cdb_bytes[2] << 24) | (cdb_bytes[3] << 16) | (cdb_bytes[4] << 8) | cdb_bytes[5]
            transfer_blocks = (cdb_bytes[7] << 8) | cdb_bytes[8]
            
            if lba + transfer_blocks > self.total_sectors:
                return 0x02, b"", self._generate_sense_data(0x05, 0x21, 0x00)

            write_data = bytes(out_payload or [])
            expected_len = transfer_blocks * self.sector_size
            if len(write_data) < expected_len:
                write_data = write_data.ljust(expected_len, b'\x00')

            start_pos = lba * self.sector_size
            end_pos = start_pos + expected_len
            self.lba_storage[start_pos:end_pos] = write_data[:expected_len]
            return 0x00, b"", bytes(18)

        # 0x03: REQUEST SENSE
        elif opcode == 0x03:
            sense = self._generate_sense_data(self.last_sense_key, self.last_asc, self.last_ascq)
            return 0x00, sense, bytes(18)

        # 未支援/未知指令
        else:
            return 0x02, b"", self._generate_sense_data(0x05, 0x20, 0x00)  # Invalid Command Operation Code

    def _handle_vendor_command(self, cdb_bytes, data_in_len, out_payload):
        """處理 0x06 0xFE 廠商特定特權序列"""
        action = cdb_bytes[2]

        # 0xC0: CONFIG DATA-OUT (送 AP_Key 或 64-Byte VUC 配置)
        if action == 0xC0:
            payload = bytes(out_payload or []).ljust(512, b'\x00')
            # 判斷是 AP_Key 還是 VUC Payload
            if not self.is_ap_key_unlocked:
                self.ap_key_buffer = bytearray(payload)
            else:
                self.vuc_config_payload = bytearray(payload[:64])
            return 0x00, b"", bytes(18)

        # 0xC1: ACTION NO-DATA / DATA-OUT (解鎖動作觸發 或 VUC 寫入)
        elif action == 0xC1:
            if not self.is_ap_key_unlocked:
                # 執行 AP_Key 驗證觸發
                self.is_ap_key_unlocked = True
                self.vuc_last_status = 0x00
                return 0x00, b"", bytes(18)
            else:
                # VUC Data-Out 寫入執行
                return 0x00, b"", bytes(18)

        # 0xC2: ACTION DATA-IN (VUC 資料讀取)
        elif action == 0xC2:
            if not self.is_ap_key_unlocked:
                # 未解鎖不可執行特權 VUC
                return 0x02, b"", self._generate_sense_data(0x05, 0x20, 0x00)

            # 產生模擬回應資料 (由 VUC 矩陣首 Byte 決定模擬資料特徵)
            cmd_type = self.vuc_config_payload[0] if len(self.vuc_config_payload) > 0 else 0
            resp = bytearray(data_in_len)
            for i in range(data_in_len):
                resp[i] = (cmd_type + i) % 256
            return 0x00, bytes(resp), bytes(18)

        # 0xC3: READ STATUS (讀取 AP_Key 解鎖狀態 或 VUC 執行狀態)
        elif action == 0xC3:
            resp = bytearray(512)
            if self.is_ap_key_unlocked:
                resp[0] = 0x00  # Status OK / Unlocked
                resp[1] = 0x55  # Magic Verified
                resp[2] = 0xAA
            else:
                resp[0] = 0x01  # Locked
            return 0x00, bytes(resp), bytes(18)

        return 0x02, b"", self._generate_sense_data(0x05, 0x24, 0x00)


class MockWin32Driver:
    """
    Windows Win32 API 模擬器
    模擬 CreateFileW, CloseHandle, DeviceIoControl (IOCTL_SCSI_PASS_THROUGH_DIRECT / FSCTL_LOCK)
    """

    def __init__(self, device_count=3):
        self.devices = {
            i: MockStorageDevice(
                drive_index=i,
                model=f"Virtual SCSI Drive #{i} (500GB)",
                size_mb=16
            ) for i in range(device_count)
        }
        self.open_handles = {}  # handle_id -> device_index
        self._next_handle = 1000

    def mock_CreateFileW(self, lpFileName, dwDesiredAccess, dwShareMode, lpSecurityAttributes, dwCreationDisposition, dwFlagsAndAttributes, hTemplateFile):
        drive_str = str(lpFileName)
        if "PhysicalDrive" in drive_str:
            try:
                num_str = drive_str.split("PhysicalDrive")[-1]
                drive_num = int("".join(c for c in num_str if c.isdigit()))
                if drive_num in self.devices:
                    self._next_handle += 1
                    h = self._next_handle
                    self.open_handles[h] = drive_num
                    return h
            except Exception:
                pass
        # 找不到則回傳 -1 (INVALID_HANDLE_VALUE)
        return -1

    def mock_CloseHandle(self, hObject):
        if hObject in self.open_handles:
            del self.open_handles[hObject]
            return 1
        return 0

    def mock_DeviceIoControl(self, hDevice, dwIoControlCode, lpInBuffer, nInBufferSize, lpOutBuffer, nOutBufferSize, lpBytesReturned, lpOverlapped):
        if hDevice not in self.open_handles:
            return 0

        drive_num = self.open_handles[hDevice]
        dev = self.devices[drive_num]

        # 1. FSCTL_LOCK_VOLUME (0x00090018)
        if dwIoControlCode == 0x00090018:
            dev.is_locked = True
            return 1

        # 2. FSCTL_UNLOCK_VOLUME (0x0009001C)
        elif dwIoControlCode == 0x0009001C:
            dev.is_locked = False
            return 1

        # 3. IOCTL_SCSI_PASS_THROUGH_DIRECT (0x4D014)
        elif dwIoControlCode == 0x4D014:
            sptd_with_sense = lpInBuffer._obj if hasattr(lpInBuffer, '_obj') else lpInBuffer
            sptd = sptd_with_sense.sptd
            sense_buf = sptd_with_sense.sense

            cdb_len = sptd.CdbLength
            cdb_bytes = list(sptd.Cdb[:cdb_len])
            data_dir = sptd.DataIn
            data_len = sptd.DataTransferLength

            out_data = None
            if data_dir == 0 and sptd.DataBuffer:  # Data-Out
                # 從 DataBuffer 讀出資料
                buf_type = (type(sptd.DataBuffer))
                raw_bytes = bytes((ctypes_c_ubyte_p(sptd.DataBuffer, data_len))) if data_len > 0 else b""
                out_data = raw_bytes

            # 轉交虛擬裝置執行
            scsi_st, in_data, sense_data = dev.execute_scsi(cdb_bytes, data_len if data_dir == 1 else 0, out_data)

            sptd.ScsiStatus = scsi_st

            # 回填 Data-In
            if data_dir == 1 and sptd.DataBuffer and in_data:
                ctypes_write_buffer(sptd.DataBuffer, in_data[:data_len])

            # 回填 Sense Data
            if sense_data:
                for i, b in enumerate(sense_data[:sizeof(sense_buf)]):
                    sense_buf.data[i] = b

            return 1

        return 0


def ctypes_c_ubyte_p(ptr_val, length):
    """輔助函式：從 void* 指標讀取 bytes"""
    import ctypes
    if not ptr_val or length <= 0:
        return b""
    return bytes((ctypes.c_ubyte * length).from_address(ptr_val))


def ctypes_write_buffer(ptr_val, data_bytes):
    """輔助函式：寫入 bytes 到 void* 指標"""
    import ctypes
    if not ptr_val or not data_bytes:
        return
    arr = (ctypes.c_ubyte * len(data_bytes)).from_address(ptr_val)
    for i, b in enumerate(data_bytes):
        arr[i] = b
