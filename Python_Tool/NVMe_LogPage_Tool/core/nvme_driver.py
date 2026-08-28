"""NVMe Pass-Through 驅動封裝。"""
import ctypes
import ctypes.wintypes as wintypes
import struct
from typing import Tuple, Optional
from .win_ioctl import (
    open_device, close_device, device_io_control,
    STORAGE_PROTOCOL_COMMAND, IOCTL_STORAGE_PROTOCOL_COMMAND,
    IOCTL_STORAGE_QUERY_PROPERTY, PROTOCOL_TYPE_NVME,
    STORAGE_PROTOCOL_SPECIFIC_NVME_ADMIN_COMMAND,
    STORAGE_PROTOCOL_COMMAND_FLAG_ADAPTER_REQUEST,
    STORAGE_PROTOCOL_STRUCTURE_VERSION, INVALID_HANDLE_VALUE,
    IOCTL_SCSI_MINIPORT, NVME_PASS_THROUGH_SRB_IO_CODE,
    NVME_PASS_THROUGH_IOCTL, SRB_IO_CONTROL,
    GENERIC_READ, GENERIC_WRITE,
    FILE_SHARE_READ, FILE_SHARE_WRITE, OPEN_EXISTING,
)
from .commands import GetLogPageCommand
from config import OPCODE_GET_LOG_PAGE


class NvmeDriver:
    """NVMe 驅動類別，封裝 Windows NVMe Pass-Through 與 Protocol Query 機制。"""

    def __init__(self, physical_drive_number: int):
        """開啟指定的 PhysicalDrive。"""
        import sys
        if sys.platform != "win32":
            raise RuntimeError("此模組僅支援 Windows 平臺")
        self.drive_number = physical_drive_number
        self.handle = open_device(physical_drive_number)

    def get_log_page(self, cmd: GetLogPageCommand) -> Tuple[bytes, int]:
        """執行 Get Log Page 指令。
        
        三重通道降級策略：
        1. Protocol-Query (IOCTL_STORAGE_QUERY_PROPERTY - 微軟原生存取)
        2. Standard Pass-Through (IOCTL_STORAGE_PROTOCOL_COMMAND - 通用 Windows 10/11)
        3. Intel/OEM Miniport Pass-Through (IOCTL_SCSI_MINIPORT - Intel RST/VMD/專用驅動)
        """
        # 優先走 Standard Pass-Through，以確保精確下發使用者自定義之 CDW10 / NUMD
        methods = [
            ("Pass-Through", self._get_log_page_passthrough),
            ("Protocol-Query", self._get_log_page_query_property),
            ("Miniport-Pass-Through", self._get_log_page_intel_miniport),
        ]

        errors = []
        for name, method in methods:
            try:
                return method(cmd)
            except Exception as e:
                errors.append(f"{name} 錯誤: {e}")

        # 所有通道皆失敗
        err_msg = "\n".join(errors)
        raise OSError(f"Get Log Page (LID=0x{cmd.lid:02X}) 執行失敗。\n{err_msg}")

    def _get_log_page_passthrough(self, cmd: GetLogPageCommand) -> Tuple[bytes, int]:
        """透過 IOCTL_STORAGE_PROTOCOL_COMMAND 執行 NVMe SQE 下發。"""
        # 精確傳輸長度與記憶體配置長度：
        # exact_transfer_len: 精確依照使用者指定的 NUMD 計算 (4 Bytes ~ 4096 Bytes)
        # alloc_len: 緩衝區大小至少 512B，確保 Windows DMA 核心記憶體足夠
        exact_transfer_len = cmd.aligned_length
        alloc_len = max(exact_transfer_len, 512)
        
        cdw10_exact = cmd.cdw10
        numd_aligned = (alloc_len // 4) - 1
        cdw10_aligned = (numd_aligned << 16) | ((cmd.rae & 1) << 15) | ((cmd.lsp & 0xF) << 8) | (cmd.lid & 0xFF)

        # 多重佈局與參數策略：
        # 優先使用 exact_transfer_len 與 cdw10_exact，確保 DataFromDeviceTransferLength 與 CDW10 NUMDL 完全一致！
        strategies = [
            # 策略 1: 微軟標準規範 (Length 84, Flags Adapter, ErrorInfo 64 @ 144, Data @ 208, 精確傳輸長度與 CDW10)
            {"layout": "with_err", "length": 84, "flags": 0x80000000, "nsid": cmd.nsid, "cdw10": cdw10_exact, "transfer_len": exact_transfer_len},
            # 策略 2: Length 80, Flags Adapter (精確傳輸長度)
            {"layout": "with_err", "length": 80, "flags": 0x80000000, "nsid": cmd.nsid, "cdw10": cdw10_exact, "transfer_len": exact_transfer_len},
            # 策略 3: Length 144, Flags Adapter (精確傳輸長度)
            {"layout": "with_err", "length": 144, "flags": 0x80000000, "nsid": cmd.nsid, "cdw10": cdw10_exact, "transfer_len": exact_transfer_len},
            # 策略 4: Flags 0 (Device Request, 精確傳輸長度)
            {"layout": "with_err", "length": 84, "flags": 0x00000000, "nsid": cmd.nsid, "cdw10": cdw10_exact, "transfer_len": exact_transfer_len},
            {"layout": "with_err", "length": 84, "flags": 0x00000000, "nsid": 0, "cdw10": cdw10_exact, "transfer_len": exact_transfer_len},
            # 策略 5: 直接佈局 (無 ErrorInfo, Data @ 144, 精確傳輸長度)
            {"layout": "no_err", "length": 84, "flags": 0x80000000, "nsid": cmd.nsid, "cdw10": cdw10_exact, "transfer_len": exact_transfer_len},
            {"layout": "no_err", "length": 80, "flags": 0x80000000, "nsid": cmd.nsid, "cdw10": cdw10_exact, "transfer_len": exact_transfer_len},
            {"layout": "no_err", "length": 144, "flags": 0x80000000, "nsid": cmd.nsid, "cdw10": cdw10_exact, "transfer_len": exact_transfer_len},
            {"layout": "no_err", "length": 84, "flags": 0x00000000, "nsid": cmd.nsid, "cdw10": cdw10_exact, "transfer_len": exact_transfer_len},
            # 策略 6 (相容降級): 512B 對齊長度 (僅當控制器或驅動拒絕小於 512B 傳輸時)
            {"layout": "with_err", "length": 84, "flags": 0x80000000, "nsid": cmd.nsid, "cdw10": cdw10_aligned, "transfer_len": alloc_len},
            {"layout": "no_err", "length": 84, "flags": 0x80000000, "nsid": cmd.nsid, "cdw10": cdw10_aligned, "transfer_len": alloc_len},
        ]
        
        last_error_code = None
        for strat in strategies:
            if strat["layout"] == "with_err":
                error_info_len = 64
                error_info_offset = 144
                data_buffer_offset = 208
            else:
                error_info_len = 0
                error_info_offset = 0
                data_buffer_offset = 144
                
            total_size = data_buffer_offset + alloc_len
            buf = ctypes.create_string_buffer(total_size)
            
            # 填寫 STORAGE_PROTOCOL_COMMAND (offset 0..79)
            struct.pack_into("<I", buf, 0, 1)                           # Version = 1
            struct.pack_into("<I", buf, 4, strat["length"])             # Length
            struct.pack_into("<I", buf, 8, PROTOCOL_TYPE_NVME)          # ProtocolType = 3
            struct.pack_into("<I", buf, 12, strat["flags"])             # Flags
            struct.pack_into("<I", buf, 16, 0)                          # ReturnStatus
            struct.pack_into("<I", buf, 20, 0)                          # ErrorCode
            struct.pack_into("<I", buf, 24, 64)                         # CommandLength = 64
            struct.pack_into("<I", buf, 28, error_info_len)             # ErrorInfoLength
            struct.pack_into("<I", buf, 32, 0)                          # DataToDeviceTransferLength = 0
            struct.pack_into("<I", buf, 36, strat["transfer_len"])      # DataFromDeviceTransferLength (精確長度)
            struct.pack_into("<I", buf, 40, 10)                         # TimeOutValue = 10
            struct.pack_into("<I", buf, 44, error_info_offset)          # ErrorInfoOffset
            struct.pack_into("<I", buf, 48, 0)                          # DataToDeviceBufferOffset = 0
            struct.pack_into("<I", buf, 52, data_buffer_offset)         # DataFromDeviceBufferOffset
            struct.pack_into("<I", buf, 56, 1)                          # CommandSpecific = 1 (Admin)

            # 填寫 NVMe SQE (offset 80..143)
            struct.pack_into("<B", buf, 80, OPCODE_GET_LOG_PAGE)        # Opcode 0x02
            struct.pack_into("<I", buf, 84, strat["nsid"])              # NSID
            struct.pack_into("<I", buf, 120, strat["cdw10"])            # CDW10 (精確 NUMDL)
            struct.pack_into("<I", buf, 124, cmd.cdw11)                 # CDW11
            struct.pack_into("<I", buf, 128, cmd.cdw12)                 # CDW12
            struct.pack_into("<I", buf, 132, cmd.cdw13)                 # CDW13

            res, bytes_returned = device_io_control(
                self.handle,
                IOCTL_STORAGE_PROTOCOL_COMMAND,
                buf,
                total_size,
                buf,
                total_size
            )
            
            if res:
                return_status = struct.unpack_from("<I", buf.raw, 16)[0]
                error_code = struct.unpack_from("<I", buf.raw, 20)[0]
                nvme_status_code = return_status if return_status != 0 else error_code
                
                if nvme_status_code == 0:
                    data = buf.raw[data_buffer_offset : data_buffer_offset + cmd.length_bytes]
                    return data, 0
                else:
                    last_error_code = nvme_status_code
                    continue
            else:
                last_error_code = ctypes.GetLastError()
                if last_error_code == 87:
                    continue
                else:
                    break
                    
        raise OSError(f"DeviceIoControl (Pass-Through) failed with Windows error {last_error_code}")

    def _get_log_page_query_property(self, cmd: GetLogPageCommand) -> Tuple[bytes, int]:
        """透過 IOCTL_STORAGE_QUERY_PROPERTY 查詢 Protocol Specific Log Page。"""
        query_data_len = 512 if cmd.aligned_length <= 512 else cmd.aligned_length
        header_size = 48  # 8 (STORAGE_PROPERTY_QUERY) + 40 (STORAGE_PROTOCOL_SPECIFIC_DATA)
        out_size = header_size + query_data_len

        last_error = None
        # 測試組合：(PropertyId, SubValue, in_size)
        attempts = [
            (50, 0, 48),                                # StorageDeviceProtocolSpecificProperty (微軟標準 Device Handle)
            (49, 0, 48),                                # StorageAdapterProtocolSpecificProperty (Adapter Handle)
            (50, cmd.lpo & 0xFFFFFFFF, 48),
            (49, cmd.lpo & 0xFFFFFFFF, 48),
            (50, 0, out_size),                          # 相容模式 (input 同 output 大小)
            (49, 0, out_size),
        ]
        
        for prop_id, sub_val, in_len in attempts:
            in_buf = ctypes.create_string_buffer(in_len)
            out_buf = ctypes.create_string_buffer(out_size)

            # STORAGE_PROPERTY_QUERY (offset 0..7):
            struct.pack_into("<I", in_buf, 0, prop_id)                   # PropertyId
            struct.pack_into("<I", in_buf, 4, 0)                         # QueryType = PropertyStandardQuery (0)

            # STORAGE_PROTOCOL_SPECIFIC_DATA (offset 8..47):
            struct.pack_into("<I", in_buf, 8, PROTOCOL_TYPE_NVME)        # ProtocolType = 1 (NVMe)
            struct.pack_into("<I", in_buf, 12, 2)                        # DataType = 2 (NVMeDataTypeLogPage)
            struct.pack_into("<I", in_buf, 16, cmd.lid)                  # ProtocolDataRequestValue = LID
            struct.pack_into("<I", in_buf, 20, sub_val)                  # ProtocolDataRequestSubValue
            struct.pack_into("<I", in_buf, 24, 40)                       # ProtocolDataOffset = 40
            struct.pack_into("<I", in_buf, 28, query_data_len)           # ProtocolDataLength >= 512
            struct.pack_into("<I", in_buf, 32, 0)                        # FixedProtocolReturnData = 0
            struct.pack_into("<I", in_buf, 36, (cmd.lpo >> 32) & 0xFFFFFFFF) # SubValue2 (LPO upper)
            struct.pack_into("<I", in_buf, 40, ((cmd.rae & 1) << 16) | (cmd.lsp & 0xFFFF)) # SubValue3 (RAE/LSP)
            struct.pack_into("<I", in_buf, 44, 0)                        # Reserved

            res, bytes_returned = device_io_control(
                self.handle,
                IOCTL_STORAGE_QUERY_PROPERTY,
                in_buf,
                in_len,
                out_buf,
                out_size
            )

            if res and bytes_returned >= 48:
                # 輸出結構為 STORAGE_PROTOCOL_DATA_DESCRIPTOR (48 Bytes header)
                data_offset = struct.unpack_from("<I", out_buf.raw, 24)[0]
                if data_offset == 0 or data_offset < 40:
                    data_offset = 40
                
                # 實際資料在緩衝區中的位置：8 + data_offset
                abs_offset = 8 + data_offset
                if abs_offset + cmd.length_bytes <= len(out_buf.raw):
                    data = out_buf.raw[abs_offset : abs_offset + cmd.length_bytes]
                    return data, 0
                else:
                    data = out_buf.raw[48 : 48 + cmd.length_bytes]
                    return data, 0

            last_error = ctypes.GetLastError()

        raise OSError(f"DeviceIoControl (Protocol-Query) failed with Windows error {last_error}")

    def _get_log_page_intel_miniport(self, cmd: GetLogPageCommand) -> Tuple[bytes, int]:
        """透過 Intel / Samsung / OEM NVMe Miniport Pass-Through (IOCTL_SCSI_MINIPORT) 下發。"""
        transfer_len = max(cmd.aligned_length, 512)
        
        class MINIPORT_BUFFER(ctypes.Structure):
            _pack_ = 1
            _fields_ = [
                ("header", NVME_PASS_THROUGH_IOCTL),
                ("buffer", ctypes.c_byte * transfer_len)
            ]
            
        numd = (transfer_len // 4) - 1
        cdw10 = (numd << 16) | ((cmd.rae & 1) << 15) | ((cmd.lsp & 0xF) << 8) | (cmd.lid & 0xFF)
        
        signatures = [b"NvmeMini", b"IntelNvm", b"SecNvme\0"]
        
        # 測試 Handle 清單：包含當前 Device Handle 以及 Scsi Port Handle
        handles_to_try = [self.handle]
        extra_handles = []
        for port in range(4):
            try:
                h = ctypes.windll.kernel32.CreateFileW(
                    f"\\\\.\\Scsi{port}:",
                    GENERIC_READ | GENERIC_WRITE,
                    FILE_SHARE_READ | FILE_SHARE_WRITE,
                    None,
                    OPEN_EXISTING,
                    0,
                    None
                )
                if h != INVALID_HANDLE_VALUE:
                    handles_to_try.append(h)
                    extra_handles.append(h)
            except Exception:
                pass
                
        last_error = None
        try:
            for h in handles_to_try:
                for sig in signatures:
                    io_buf = MINIPORT_BUFFER()
                    hdr_size = ctypes.sizeof(NVME_PASS_THROUGH_IOCTL)
                    srb_size = ctypes.sizeof(SRB_IO_CONTROL)
                    total_size = ctypes.sizeof(MINIPORT_BUFFER)
                    
                    io_buf.header.SrbIoCtrl.HeaderLength = srb_size
                    io_buf.header.SrbIoCtrl.Signature = sig
                    io_buf.header.SrbIoCtrl.Timeout = 10
                    io_buf.header.SrbIoCtrl.ControlCode = NVME_PASS_THROUGH_SRB_IO_CODE
                    io_buf.header.SrbIoCtrl.Length = (hdr_size - srb_size) + transfer_len
                    
                    io_buf.header.Direction = 2  # Data In
                    io_buf.header.QueueId = 0    # Admin Queue
                    io_buf.header.DataBufferLen = transfer_len
                    io_buf.header.ReturnBufferLen = hdr_size + transfer_len
                    
                    # NVMe Command SQE
                    io_buf.header.NVMeCmd[0] = OPCODE_GET_LOG_PAGE | ((cmd.numd & 0xFFFF) << 16)
                    io_buf.header.NVMeCmd[1] = cmd.nsid
                    io_buf.header.NVMeCmd[10] = cmd.cdw10
                    io_buf.header.NVMeCmd[11] = cmd.cdw11
                    io_buf.header.NVMeCmd[12] = cmd.cdw12
                    io_buf.header.NVMeCmd[13] = cmd.cdw13
                    
                    res, bytes_returned = device_io_control(
                        h,
                        IOCTL_SCSI_MINIPORT,
                        io_buf,
                        total_size,
                        io_buf,
                        total_size
                    )
                    
                    if res:
                        srb_return = io_buf.header.SrbIoCtrl.ReturnCode
                        cpl_status = (io_buf.header.CplEntry[3] >> 17) & 0x7FF
                        status_code = srb_return if srb_return != 0 else cpl_status
                        if status_code == 0:
                            data = bytes(io_buf.buffer)[:cmd.length_bytes]
                            return data, 0
                    last_error = ctypes.GetLastError()
        finally:
            for h in extra_handles:
                ctypes.windll.kernel32.CloseHandle(h)
            
        raise OSError(f"DeviceIoControl (Miniport-Pass-Through) failed with Windows error {last_error}")

    def close(self):
        """關閉裝置 handle。"""
        if hasattr(self, 'handle') and self.handle != INVALID_HANDLE_VALUE:
            close_device(self.handle)
            self.handle = INVALID_HANDLE_VALUE

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
