"""自定義 tkinter/ttk UI 元件。"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, List, Callable


class HexViewer(tk.Frame):
    """Hex Dump 檢視器元件。
    
    顯示格式化的十六進位資料，使用等寬字體。
    包含一個 Text widget 與 Scrollbar。
    """
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.scrollbar = ttk.Scrollbar(self)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.text = tk.Text(self, font=("Consolas", 10), yscrollcommand=self.scrollbar.set, state=tk.DISABLED)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.text.yview)
    
    def set_data(self, hex_text: str):
        """設定顯示的 Hex Dump 文字。"""
        self.text.config(state=tk.NORMAL)
        self.text.delete(1.0, tk.END)
        self.text.insert(tk.END, hex_text)
        self.text.config(state=tk.DISABLED)
    
    def clear(self):
        """清空顯示。"""
        self.text.config(state=tk.NORMAL)
        self.text.delete(1.0, tk.END)
        self.text.config(state=tk.DISABLED)


class ResultTable(tk.Frame):
    """測試結果表格元件。
    
    使用 ttk.Treeview 顯示批次執行結果。
    欄位: #, LID, Log Name, NUMD, Length, CDW10, Status, Latency, Result
    """
    
    def __init__(self, parent, on_select: Optional[Callable] = None, **kwargs):
        """on_select 回呼：選中某行時觸發，參數為 row index。"""
        super().__init__(parent, **kwargs)
        self.on_select = on_select
        
        columns = ("#", "LID", "Log Name", "NUMD", "Length", "CDW10", "Channel", "Status", "Latency", "Result")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=75, anchor=tk.CENTER)
        
        self.tree.column("#", width=35)
        self.tree.column("LID", width=55)
        self.tree.column("Log Name", width=160)
        self.tree.column("NUMD", width=65)
        self.tree.column("Length", width=65)
        self.tree.column("CDW10", width=95)
        self.tree.column("Channel", width=120)
        self.tree.column("Status", width=65)
        self.tree.column("Latency", width=75)
        self.tree.column("Result", width=65)
        
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=self.scrollbar.set)
        
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.tree.tag_configure('PASS', foreground='green')
        self.tree.tag_configure('FAIL', foreground='red')
        
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self._results = []

    def _on_tree_select(self, event):
        if not self.on_select:
            return
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            idx = int(item['values'][0]) - 1
            self.on_select(idx)
    
    def add_result(self, result: 'SingleResult'):
        """新增一筆結果到表格。"""
        result_text = "PASS" if result.success else "FAIL"
        tag = 'PASS' if result.success else 'FAIL'
        
        values = (
            result.index,
            f"0x{result.lid:02X}",
            result.lid_name,
            f"0x{result.numd:02X}",
            f"{result.length_bytes}B",
            f"0x{result.cdw10:08X}",
            result.channel or "N/A",
            f"0x{result.status_code:02X}" if result.status_code is not None and result.status_code >= 0 else "N/A",
            f"{result.latency_ms:.2f} ms" if result.latency_ms is not None else "N/A",
            result_text
        )
        self.tree.insert("", tk.END, values=values, tags=(tag,))
        self.tree.yview_moveto(1)
        self._results.append(result)
        
    def get_result(self, index: int) -> Optional['SingleResult']:
        if 0 <= index < len(self._results):
            return self._results[index]
        return None
    
    def clear(self):
        """清空表格。"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._results.clear()


class CsvPreviewTable(tk.Frame):
    """CSV 測試案例預覽表格。
    
    使用 ttk.Treeview 顯示載入的 CSV 內容。
    欄位: #, LID, Log Name, NUMD, Length, CDW10
    """
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        columns = ("#", "LID", "Log Name", "NUMD", "Length", "CDW10")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=75, anchor=tk.CENTER)
            
        self.tree.column("#", width=35)
        self.tree.column("LID", width=55)
        self.tree.column("Log Name", width=170)
        self.tree.column("NUMD", width=65)
        self.tree.column("Length", width=65)
        self.tree.column("CDW10", width=95)
        
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=self.scrollbar.set)
        
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    def load_cases(self, cases: list):
        """載入 CsvTestCase 列表到表格。"""
        self.clear()
        for case in cases:
            cmd = case.to_command()
            values = (
                case.index,
                f"0x{case.lid:02X}",
                case.lid_name,
                f"0x{case.numd:02X}",
                f"{case.length_bytes}B",
                f"0x{cmd.cdw10:08X}"
            )
            self.tree.insert("", tk.END, values=values)
    
    def clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
