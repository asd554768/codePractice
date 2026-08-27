"""CSV 解析器模組。"""
import csv
import re
import os
from dataclasses import dataclass
from typing import List, Optional

from config import get_lid_name
from core.commands import GetLogPageCommand


@dataclass
class CsvTestCase:
    """CSV 單筆測試案例。"""
    index: int              # 序號 (1-based)
    lid: int                # Log Page Identifier
    length_bytes: int       # 請求長度 (Bytes)
    lid_name: str           # 自動查表取得的名稱
    
    def to_command(self) -> GetLogPageCommand:
        """轉換為 GetLogPageCommand 物件。"""
        return GetLogPageCommand(lid=self.lid, length_bytes=self.length_bytes)


def parse_csv(file_path: str) -> List[CsvTestCase]:
    """解析極簡 CSV 檔案 (僅需 LID 與 Length 兩欄)。
    
    容錯特性：
    - 支援行首與行尾註解 (# 或 // 開頭或行內註解)
    - 支援 HEX (0x02) 與 DEC (2) 自動識別
    - Length 支援純數字 (512) 或帶單位 (4KB, 64K, 1MB, 1)
    - Header 自動識別 (無論位於第幾行、大小寫不拘)
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

        # 5. 解析 Length (支援 10 進位、16 進位 0x200、帶單位 1KB/64B)
        len_str = parts[1].strip()
        if len_str.lower().startswith('0x'):
            try:
                length = int(len_str, 16)
            except ValueError:
                continue
        else:
            m_len = re.search(r'(\d+)\s*(KB|MB|K|M|B)?', len_str, re.IGNORECASE)
            if not m_len:
                continue
            num = int(m_len.group(1))
            unit = (m_len.group(2) or '').upper()
            if unit in ('KB', 'K'):
                length = num * 1024
            elif unit in ('MB', 'M'):
                length = num * 1024 * 1024
            else:
                length = num
        length = max(1, length)

        # 6. 解析 Log Name (若 CSV 有提供第 3 欄則使用，否則查表)
        if len(parts) >= 3 and parts[2]:
            lid_name = parts[2]
        else:
            lid_name = get_lid_name(lid)

        test_cases.append(CsvTestCase(
            index=index,
            lid=lid,
            length_bytes=length,
            lid_name=lid_name
        ))
        index += 1

    return test_cases

