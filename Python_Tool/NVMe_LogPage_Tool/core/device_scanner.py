"""NVMe 磁碟掃描器。"""
import ctypes
import ctypes.wintypes as wintypes
import struct
from dataclasses import dataclass
from typing import List
from .win_ioctl import (
    open_device_query, close_device, device_io_control,
    IOCTL_STORAGE_QUERY_PROPERTY, IOCTL_DISK_GET_DRIVE_GEOMETRY
)


@dataclass
class NvmeDeviceInfo:
    drive_number: int       # PhysicalDrive 編號
    model: str              # 型號
    serial: str             # 序號
    firmware_rev: str       # 韌體版本
    size_gb: float          # 容量 (GB)
    bus_type: int = 17      # 匯流排類型 (17=NVMe)
    
    @property
    def display_name(self) -> str:
        bus_str = "NVMe" if self.bus_type == 17 else f"BusType_{self.bus_type}"
        size_str = f"{self.size_gb:.0f}GB" if self.size_gb > 0 else "Unknown Size"
        return f"PhysicalDrive{self.drive_number}: [{bus_str}] {self.model} ({size_str}, S/N: {self.serial})"


def scan_nvme_devices() -> List[NvmeDeviceInfo]:
    """掃描系統中所有 NVMe 磁碟。"""
    import sys
    if sys.platform != "win32":
        print("警告: 磁碟掃描功能僅支援 Windows 平臺")
        return []
        
    nvme_devices = []
    all_devices = []
    
    for drive_num in range(32):
        try:
            handle = open_device_query(drive_num)
        except OSError:
            continue
            
        try:
            # 1. 查詢 StorageDeviceProperty
            query = (ctypes.c_uint * 3)(0, 0, 0)  # PropertyId=0 (DeviceProperty), QueryType=0 (Standard)
            buf = ctypes.create_string_buffer(1024)
            
            res, bytes_returned = device_io_control(
                handle,
                IOCTL_STORAGE_QUERY_PROPERTY,
                query,
                12,
                buf,
                1024
            )
            
            if res and bytes_returned >= 32:
                raw = buf.raw[:bytes_returned]
                # 解析 STORAGE_DEVICE_DESCRIPTOR:
                # Version(4), Size(4), DeviceType(1), DeviceTypeModifier(1), RemovableMedia(1), CommandQueueing(1),
                # VendorIdOffset(4), ProductIdOffset(4), ProductRevisionOffset(4), SerialNumberOffset(4), BusType(4)
                ver, size, devtype, devtypemod, rem, cq, vid_off, pid_off, rev_off, sn_off, bustype = struct.unpack_from(
                    '<IIBBBBIIIII', raw, 0
                )
                
                def extract_string(offset: int) -> str:
                    if offset == 0 or offset >= len(raw):
                        return ""
                    end = raw.find(b'\x00', offset)
                    if end == -1:
                        end = len(raw)
                    return raw[offset:end].decode('ascii', errors='ignore').strip()
                
                vendor = extract_string(vid_off)
                product = extract_string(pid_off)
                model = f"{vendor} {product}".strip() if vendor else product
                if not model:
                    model = f"Disk {drive_num}"
                    
                serial = extract_string(sn_off)
                fw = extract_string(rev_off)
                
                # 2. 取得容量 (IOCTL_DISK_GET_DRIVE_GEOMETRY = 0x00070000)
                size_gb = 0.0
                geom_buf = (ctypes.c_byte * 24)()
                geom_res, geom_bytes = device_io_control(
                    handle,
                    IOCTL_DISK_GET_DRIVE_GEOMETRY,
                    None,
                    0,
                    geom_buf,
                    24
                )
                
                if geom_res and geom_bytes >= 24:
                    cyl, med, tpc, spt, bps = struct.unpack('<qiIII', bytes(geom_buf))
                    size_bytes = cyl * tpc * spt * bps
                    size_gb = size_bytes / (1024 ** 3)
                
                dev_info = NvmeDeviceInfo(
                    drive_number=drive_num,
                    model=model,
                    serial=serial,
                    firmware_rev=fw,
                    size_gb=size_gb,
                    bus_type=bustype
                )
                
                all_devices.append(dev_info)
                # BusType 17 = BusTypeNvme，或型號中包含 NVMe
                if bustype == 17 or "NVME" in model.upper():
                    nvme_devices.append(dev_info)
                    
        except Exception:
            pass
        finally:
            close_device(handle)
            
    # 若有識別到 NVMe 設備則返回 NVMe 清單，若無則返回全部實體磁碟供使用者選擇
    return nvme_devices if nvme_devices else all_devices

