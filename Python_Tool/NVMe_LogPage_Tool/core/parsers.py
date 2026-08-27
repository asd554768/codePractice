"""NVMe 記錄頁解析與工具。"""
from typing import Optional, Dict, Any
from config import SMART_FIELDS

def parse_smart_log(data: bytes) -> Dict[str, Any]:
    """根據 config.SMART_FIELDS 解析 SMART Log 二進位資料。"""
    result = {}
    for offset, size, field_name, desc in SMART_FIELDS:
        if offset + size > len(data):
            continue
        
        chunk = data[offset:offset+size]
        value = int.from_bytes(chunk, byteorder='little')
        
        # 處理溫度欄位 (Kelvin 轉 Celsius)
        if "temperature" in field_name and value > 0 and size in (2, 4):
            value -= 273
            
        result[field_name] = value
    return result

def format_hex_dump(data: bytes, bytes_per_line: int = 16) -> str:
    """格式化為帶 Offset 與 ASCII 的 Hex Dump 文字。"""
    lines = []
    for i in range(0, len(data), bytes_per_line):
        chunk = data[i:i+bytes_per_line]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        hex_part = hex_part.ljust(bytes_per_line * 3 - 1)
        
        ascii_part = "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in chunk)
        lines.append(f"{i:08X}: {hex_part} | {ascii_part}")
        
    return "\n".join(lines)

def parse_log_data(lid: int, data: bytes) -> Optional[Dict[str, Any]]:
    """根據 LID 自動選擇解析器，若無已知解析器回傳 None。"""
    if lid == 0x02:
        return parse_smart_log(data)
    return None
