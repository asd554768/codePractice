"""執行結果歸檔管理模組。"""
import os
import csv
import json
from datetime import datetime
from typing import Optional, List

from core.parsers import parse_log_data, format_hex_dump


class Reporter:
    """執行結果歸檔管理。
    
    自動建立輸出目錄結構：
    results/Run_YYYYMMDD_HHMMSS/
    ├── summary.csv
    └── dump/
        ├── 001_LID_0x02_SMART_Health_Information_512B.bin
        ├── 001_LID_0x02_SMART_Health_Information_512B.hex
        ├── 001_LID_0x02_SMART_Health_Information_512B.json  (若有解析器)
        ├── 002_LID_0x01_Error_Information_1024B.bin
        ...
    """
    
    def __init__(self, base_dir: str = ""):
        """初始化 Reporter，建立輸出目錄。
        
        Args:
            base_dir: 基礎目錄。若為空則在當前目錄下建立 results/Run_... 目錄
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if not base_dir:
            self._output_dir = os.path.join("results", f"Run_{timestamp}")
        else:
            self._output_dir = os.path.join(base_dir, f"Run_{timestamp}")
            
        self._dump_dir = os.path.join(self._output_dir, "dump")
        os.makedirs(self._dump_dir, exist_ok=True)
    
    def save_single_result(self, result: 'SingleResult') -> None:
        """儲存單筆結果的 .bin 與 .hex 檔案。
        
        檔名格式: {index:03d}_LID_0x{lid:02X}_{lid_name}_{length}B.{ext}
        """
        if not result.data:
            return
            
        safe_name = result.lid_name.replace(" ", "_").replace("/", "_")
        base_filename = f"{result.index:03d}_LID_0x{result.lid:02X}_CDW10_0x{result.cdw10:08X}_{safe_name}_{result.length_bytes}B"
        base_path = os.path.join(self._dump_dir, base_filename)
        
        # 寫入 .bin 檔案
        with open(f"{base_path}.bin", "wb") as f:
            f.write(result.data)
            
        # 寫入 .hex 檔案
        hex_data = format_hex_dump(result.data)
        with open(f"{base_path}.hex", "w", encoding="utf-8") as f:
            f.write(hex_data)
            
        # 解析並寫入 .json 檔案
        parsed_data = parse_log_data(result.lid, result.data)
        if parsed_data is not None:
            with open(f"{base_path}.json", "w", encoding="utf-8") as f:
                json.dump(parsed_data, f, indent=4, ensure_ascii=False)
    
    def write_summary(self, results: list) -> str:
        """寫入 summary.csv 彙整報告。
        
        欄位: Index, LID, LID_Name, NUMD, Length_Bytes, CDW10, Status_Code, Latency_ms, Result, Error_Message
        
        Returns:
            summary.csv 的完整路徑
        """
        summary_path = os.path.join(self._output_dir, "summary.csv")
        
        total_count = len(results)
        pass_count = sum(1 for r in results if r.success)
        fail_count = total_count - pass_count
        
        with open(summary_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Index", "LID", "LID_Name", "NUMD", "Length_Bytes", "CDW10", "Status_Code", "Latency_ms", "Result", "Error_Message"])
            
            for r in results:
                writer.writerow([
                    r.index,
                    f"0x{r.lid:02X}",
                    r.lid_name,
                    f"0x{r.numd:02X}",
                    r.length_bytes,
                    f"0x{r.cdw10:08X}",
                    f"0x{r.status_code:X}" if r.status_code >= 0 else str(r.status_code),
                    f"{r.latency_ms:.2f}",
                    "PASS" if r.success else "FAIL",
                    r.error_message
                ])
                
            writer.writerow([])
            writer.writerow(["Total", total_count])
            writer.writerow(["Pass", pass_count])
            writer.writerow(["Fail", fail_count])
            
        return summary_path
    
    @property
    def output_dir(self) -> str:
        """回傳輸出目錄路徑。"""
        return self._output_dir
