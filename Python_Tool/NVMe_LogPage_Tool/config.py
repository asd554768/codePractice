"""NVMe Get Log Page 工具 - 全域設定與常數定義。"""
import enum
from typing import Dict, Tuple

# === NVMe Admin Opcodes ===
OPCODE_GET_LOG_PAGE = 0x02
OPCODE_IDENTIFY = 0x06

# === Windows IOCTL 常數 (Windows SDK ntddstor.h) ===
# IOCTL_STORAGE_PROTOCOL_COMMAND = CTL_CODE(0x2D, 0x04F0, METHOD_BUFFERED, FILE_READ_ACCESS | FILE_WRITE_ACCESS) = 0x002DD3C0
IOCTL_STORAGE_PROTOCOL_COMMAND = 0x002DD3C0
IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
IOCTL_DISK_GET_DRIVE_GEOMETRY = 0x00070000

# Storage Protocol Structure Version
STORAGE_PROTOCOL_STRUCTURE_VERSION = 1

# Storage Protocol Type (Windows SDK ntddstor.h: ProtocolTypeUnknown=0, ProtocolTypeScsi=1, ProtocolTypeAta=2, ProtocolTypeNvme=3)
PROTOCOL_TYPE_NVME = 3

# Storage Protocol Specific Command Types
STORAGE_PROTOCOL_SPECIFIC_NVME_ADMIN_COMMAND = 1
STORAGE_PROTOCOL_SPECIFIC_NVME_NVM_COMMAND = 2

# Storage Protocol Command Flags
STORAGE_PROTOCOL_COMMAND_FLAG_ADAPTER_REQUEST = 0x80000000

# Storage Protocol Return Status
STORAGE_PROTOCOL_STATUS_SUCCESS = 0

# Storage Protocol NVMe Data Type (For Query Property)
NVME_DATA_TYPE_LOG_PAGE = 2

# Bus Type
BUS_TYPE_NVME = 17

# === NVMe 預設參數 ===
DEFAULT_NSID = 0xFFFFFFFF
DEFAULT_RAE = 0
DEFAULT_LSP = 0
DEFAULT_LPO = 0

# === LID 名稱映射表 (NVMe 1.4 / 2.0 Spec) ===
LID_NAME_MAP: Dict[int, str] = {
    0x01: "Error_Information",
    0x02: "SMART_Health_Information",
    0x03: "Firmware_Slot_Information",
    0x04: "Changed_Namespace_List",
    0x05: "Commands_Supported_and_Effects",
    0x06: "Device_Self_Test",
    0x07: "Telemetry_Host_Initiated",
    0x08: "Telemetry_Controller_Initiated",
    0x09: "Endurance_Group_Information",
    0x0A: "Predictable_Latency_Per_NVM_Set",
    0x0B: "Predictable_Latency_Event_Aggregate",
    0x0C: "Asymmetric_Namespace_Access",
    0x0D: "Persistent_Event_Log",
    0x0E: "LBA_Status_Information",
    0x0F: "Endurance_Group_Event_Aggregate",
    0x10: "Media_Unit_Status",
    0x11: "Supported_Capacity_Configuration_List",
    0x12: "Feature_Identifiers_Supported_and_Effects",
    0x13: "NVMe_MI_Commands_Supported_and_Effects",
    0x14: "Command_and_Feature_Lockdown",
    0x15: "Boot_Partition",
    0x16: "Rotational_Media_Information",
    0x80: "Reservation_Notification",
    0x81: "Sanitize_Status",
}


def get_lid_name(lid: int) -> str:
    """取得 LID 對應的 Log Page 名稱。
    
    Args:
        lid: Log Page Identifier (0x00~0xFF)
    
    Returns:
        Log Page 名稱字串
    """
    if lid in LID_NAME_MAP:
        return LID_NAME_MAP[lid]
    if 0xC0 <= lid <= 0xFF:
        return f"Vendor_Specific_0x{lid:02X}"
    return f"Unknown_LID_0x{lid:02X}"


# === SMART / Health Information Log (LID 0x02) 欄位定義 ===
# (offset_bytes, size_bytes, field_name, description)
SMART_FIELDS: list[Tuple[int, int, str, str]] = [
    (0, 1, "critical_warning", "Critical Warning"),
    (1, 2, "composite_temperature", "Composite Temperature (Kelvin)"),
    (3, 1, "available_spare", "Available Spare (%)"),
    (4, 1, "available_spare_threshold", "Available Spare Threshold (%)"),
    (5, 1, "percentage_used", "Percentage Used (%)"),
    (6, 1, "endurance_group_critical_warning_summary", "Endurance Group Critical Warning Summary"),
    (32, 16, "data_units_read", "Data Units Read"),
    (48, 16, "data_units_written", "Data Units Written"),
    (64, 16, "host_read_commands", "Host Read Commands"),
    (80, 16, "host_write_commands", "Host Write Commands"),
    (96, 16, "controller_busy_time", "Controller Busy Time (minutes)"),
    (112, 16, "power_cycles", "Power Cycles"),
    (128, 16, "power_on_hours", "Power On Hours"),
    (144, 16, "unsafe_shutdowns", "Unsafe Shutdowns"),
    (160, 16, "media_and_data_integrity_errors", "Media and Data Integrity Errors"),
    (176, 16, "number_of_error_information_log_entries", "Number of Error Information Log Entries"),
    (192, 4, "warning_composite_temperature_time", "Warning Composite Temperature Time (minutes)"),
    (196, 4, "critical_composite_temperature_time", "Critical Composite Temperature Time (minutes)"),
    (200, 2, "temperature_sensor_1", "Temperature Sensor 1 (Kelvin)"),
    (202, 2, "temperature_sensor_2", "Temperature Sensor 2 (Kelvin)"),
    (204, 2, "temperature_sensor_3", "Temperature Sensor 3 (Kelvin)"),
    (206, 2, "temperature_sensor_4", "Temperature Sensor 4 (Kelvin)"),
    (208, 2, "temperature_sensor_5", "Temperature Sensor 5 (Kelvin)"),
    (210, 2, "temperature_sensor_6", "Temperature Sensor 6 (Kelvin)"),
    (212, 2, "temperature_sensor_7", "Temperature Sensor 7 (Kelvin)"),
    (214, 2, "temperature_sensor_8", "Temperature Sensor 8 (Kelvin)"),
    (216, 4, "thermal_management_temperature_1_transition_count", "TMT1 Transition Count"),
    (220, 4, "thermal_management_temperature_2_transition_count", "TMT2 Transition Count"),
    (224, 4, "total_time_for_thermal_management_temperature_1", "Total Time for TMT1"),
    (228, 4, "total_time_for_thermal_management_temperature_2", "Total Time for TMT2"),
]

# === 應用程式版本 ===
APP_NAME = "NVMe Get Log Page Batch Tool"
APP_VERSION = "1.0.0"
