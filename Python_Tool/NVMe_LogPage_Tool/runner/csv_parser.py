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
    opcode: int = 0x02      # Admin Opcode (預設 0x02 Get Log Page)
    
    def __post_init__(self):
        if self.numd == 0 and self.length_bytes > 4:
            self.numd = math.ceil(self.length_bytes / 4) - 1
        elif self.numd > 0 and self.length_bytes == 4:
            self.length_bytes = (self.numd + 1) * 4
        if not self.lid_name:
            self.lid_name = get_lid_name(self.lid)
            
    def to_command(self) -> GetLogPageCommand:
        """轉換為 GetLogPageCommand 物件。"""
        return GetLogPageCommand(lid=self.lid, numd_val=self.numd, length_bytes=self.length_bytes, opcode=self.opcode)


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
    unit_pattern = r'^(\d+)\s*(KB|MB|K|M|B)$'
    match = re.match(unit_pattern, s, re.IGNORECASE)
    if match:
        val = int(match.group(1))
        unit = match.group(2).upper()
        if unit in ('KB', 'K'):
            length = val * 1024
        elif unit in ('MB', 'M'):
            length = val * 1024 * 1024
        else:  # 'B'
            length = val
        length = max(1, length)
        numd = math.ceil(length / 4) - 1
        return numd, length

    # 3. 純 Hex 字串（含 A-F，且整體都是合法 Hex digit）
    hex_letters_pattern = r'^[0-9a-fA-F]*[a-fA-F][0-9a-fA-F]*$'
    if re.match(hex_letters_pattern, s):
        try:
            numd = int(s, 16)
            return numd, (numd + 1) * 4
        except ValueError:
            pass

    # 4. 純十進位數字 (NUMD 模式)
    if s.isdigit():
        numd = int(s)
        return numd, (numd + 1) * 4

    raise ValueError(f"無法解析 NUMD 或長度格式: {val_str}")


def parse_csv(file_path: str) -> List[CsvTestCase]:
    """解析 CSV 檔案 (支援 LID,NUMD 或 OPCODE,LID,NUMD 格式)。
    
    容錯特性：
    - 支援 3 欄格式 (OPCODE,LID,NUMD) 或 2 欄格式 (LID,NUMD)
    - 第二欄支援 NUMD (0x7F, 7F, 0x01, 127, 0) 或帶單位長度 (512B, 4KB)
    - 支援行首與行尾註解 (# 或 // 開頭或行內註解)
    - 支援 HEX (0x02) 與 DEC (2) 自動識別
    - Header 自動識別 (大小寫不拘)
    - 支援逗號 (,)、分號 (;) 與 Tab 鍵分隔符
    - 支援可選的第 3/4 欄 Log Name
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

        # 3. 檢查是否為 Header
        if re.search(r'[a-zA-Z]', parts[0]) and not parts[0].lower().startswith('0x'):
            continue

        opcode = 0x02
        lid = 0
        numd = 0
        length = 4
        lid_name = ""

        if len(parts) >= 3:
            # 檢查第三欄是否也是數字/Hex (例如 0xC0, 0xF0, 0x00)
            is_p2_numeric = False
            try:
                if parts[2].lower().startswith('0x') or parts[2].isdigit() or re.match(r'^[0-9a-fA-F]+$', parts[2]):
                    parse_numd_or_length(parts[2])
                    is_p2_numeric = True
            except Exception:
                is_p2_numeric = False

            if is_p2_numeric:
                # 3 欄格式: OPCODE, LID, NUMD
                try:
                    opcode = int(parts[0], 16) if parts[0].lower().startswith('0x') else int(parts[0])
                    lid = int(parts[1], 16) if parts[1].lower().startswith('0x') else int(parts[1])
                    numd, length = parse_numd_or_length(parts[2])
                    if len(parts) >= 4:
                        lid_name = parts[3]
                    else:
                        lid_name = get_lid_name(lid)
                except Exception:
                    continue
            else:
                # 2 欄 + Name: LID, NUMD, Name
                try:
                    lid = int(parts[0], 16) if parts[0].lower().startswith('0x') else int(parts[0])
                    numd, length = parse_numd_or_length(parts[1])
                    lid_name = parts[2]
                except Exception:
                    continue
        else:
            # 2 欄格式: LID, NUMD
            try:
                lid = int(parts[0], 16) if parts[0].lower().startswith('0x') else int(parts[0])
                numd, length = parse_numd_or_length(parts[1])
                lid_name = get_lid_name(lid)
            except Exception:
                continue

        test_cases.append(CsvTestCase(
            index=index,
            lid=lid,
            numd=numd,
            length_bytes=length,
            lid_name=lid_name,
            opcode=opcode
        ))
        index += 1

    return test_cases

