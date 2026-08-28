"""CSV 解析器模組。"""
import csv
import re
import os
from dataclasses import dataclass
from typing import List, Optional

from config import get_lid_name
from core.commands import GetLogPageCommand


import math


@dataclass
class CsvTestCase:
    """CSV 單筆測試案例。"""
    index: int              # 序號 (1-based)
    lid: int                # Log Page Identifier
    numd: int = 0           # Number of Dwords (0-based, 例如 0x7F)
    length_bytes: int = 4   # 資料長度 (Bytes) = (numd + 1) * 4
    lid_name: str = ""      # 自動查表取得的名稱
    
    def __post_init__(self):
        if self.numd == 0 and self.length_bytes > 4:
            self.numd = math.ceil(self.length_bytes / 4) - 1
        elif self.numd > 0 and self.length_bytes == 4:
            self.length_bytes = (self.numd + 1) * 4
        if not self.lid_name:
            self.lid_name = get_lid_name(self.lid)
            
    def to_command(self) -> GetLogPageCommand:
        """轉換為 GetLogPageCommand 物件。"""
        return GetLogPageCommand(lid=self.lid, numd_val=self.numd, length_bytes=self.length_bytes)


def parse_numd_or_length(val_str: str) -> tuple[int, int]:
    """解析 CSV 第二欄位 (NUMD 或長度)。
    
    解析優先順序：
    1. 0x 前綴 Hex NUMD：'0x7F', '0x0B', '0x00' -> NUMD 直接使用（最明確）
    2. 帶單位長度：'512B', '4KB', '64K', '1MB'（含 B/KB/MB/K/M 結尾）
    3. 純 Hex 字串（含 A-F，且整體都是合法 Hex digit，無後綴）：'7F', 'FF', 'AB'
    4. 純十進位 NUMD：'0', '1', '127', '255'
    
    ⚠️ 注意：'0B', '1B'...'9B' 會被當作 Bytes 單位（0~9 Bytes）。
              若要表達 Hex NUMD=0x0B..0x9B，請用 0x 前綴：'0x0B'。
    
    Returns:
        (numd, length_bytes)
    """
    s = val_str.strip()
    
    # 1. 0x 前綴 Hex (最優先，最明確)
    if s.lower().startswith('0x'):
        numd = int(s, 16)
        return numd, (numd + 1) * 4

    # 2. 帶單位長度 (B / KB / MB / K / M)
    #    統一用 regex：數字 + 可選空白 + 單位
    m_unit = re.match(r'^(\d+)\s*(KB|MB|K|M|B)$', s, re.IGNORECASE)
    if m_unit:
        num = int(m_unit.group(1))
        unit = m_unit.group(2).upper()
        if unit in ('KB', 'K'):
            bytes_val = num * 1024
        elif unit in ('MB', 'M'):
            bytes_val = num * 1024 * 1024
        else:  # 'B'
            bytes_val = num
        bytes_val = max(1, bytes_val)
        numd = math.ceil(bytes_val / 4) - 1
        return numd, bytes_val

    # 3. 純 Hex 字串（整體都是 Hex digit 且含至少一個 A-F）
    #    例如 '7F', 'FF', 'AB', '1A', 'DEAD' -> Hex NUMD
    #    排除：數字+單位已在 step 2 處理，不會走到這裡
    if re.match(r'^[0-9A-Fa-f]+$', s) and re.search(r'[A-Fa-f]', s):
        numd = int(s, 16)
        return numd, (numd + 1) * 4

    # 4. 純十進位整數
    numd = int(s)
    return numd, (numd + 1) * 4


def parse_csv(file_path: str) -> List[CsvTestCase]:
    """解析極簡 CSV 檔案 (僅需 LID 與 NUMD 兩欄)。
    
    容錯特性：
    - 第二欄支援 NUMD (0x7F, 7F, 0x01, 127, 0) 或帶單位長度 (512B, 4KB)
    - 支援行首與行尾註解 (# 或 // 開頭或行內註解)
    - 支援 HEX (0x02) 與 DEC (2) 自動識別
    - Header 自動識別 (大小寫不拘)
    - 支援逗號 (,)、分號 (;) 與 Tab 鍵分隔符
    - 支援可選的第三欄 Log Name
    - 自動去除 BOM 與空白字符
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到檔案: {file_path}")

    test_cases: List[CsvTestCase] = []

    with open(file_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
        content = f.read()

    lines = content.splitlines()
    index = 1

    for line in lines:
        # 1. 移除行內註解 (# 與 //)
        line_clean = line.split('#')[0].split('//')[0].strip()
        if not line_clean:
            continue

        # 2. 分割欄位 (支援逗號、分號、Tab)
        parts = [p.strip() for p in re.split(r'[,;\t]+', line_clean) if p.strip()]
        if len(parts) < 2:
            continue

        # 3. 檢查是否為 Header (首欄包含英文字母且非十六進位 0x 開頭)
        if re.search(r'[a-zA-Z]', parts[0]) and not parts[0].lower().startswith('0x'):
            continue

        # 4. 解析 LID
        m_lid = re.search(r'0x[0-9a-fA-F]+|\d+', parts[0])
        if not m_lid:
            continue
        lid_str = m_lid.group(0)
        try:
            lid = int(lid_str, 16) if lid_str.lower().startswith('0x') else int(lid_str)
        except ValueError:
            continue

        # 5. 解析 NUMD / Length (支援 7F, 0x7F, 01, 127, 4KB 等)
        try:
            numd, length = parse_numd_or_length(parts[1])
        except Exception:
            continue

        # 6. 解析 Log Name (若 CSV 有提供第 3 欄則使用，否則查表)
        if len(parts) >= 3 and parts[2]:
            lid_name = parts[2]
        else:
            lid_name = get_lid_name(lid)

        test_cases.append(CsvTestCase(
            index=index,
            lid=lid,
            numd=numd,
            length_bytes=length,
            lid_name=lid_name
        ))
        index += 1

    return test_cases

