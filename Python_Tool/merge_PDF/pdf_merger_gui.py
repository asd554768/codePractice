import os
import re
import sys
import time
import threading
import subprocess
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText

import pypdf
from pypdf import PdfReader, PdfWriter

def natural_sort_key(s):
    """自然排序鍵值：支援檔名中帶有數字的正確順序 (例如 1, 2, 10 而非 1, 10, 2)"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]

def format_file_size(size_bytes):
    """格式化檔案大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"

def parse_page_range(range_str, total_pages):
    """
    解析頁面範圍字串，例如 '1-5', '1, 3, 5-8', 'all', ''
    回傳 0-indexed 的頁面 index 列表
    """
    range_str = str(range_str).strip()
    if not range_str or range_str.lower() in ("all", "全部", "*"):
        return list(range(total_pages))
    
    pages = set()
    parts = range_str.split(',')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            seg = part.split('-', 1)
            start_s, end_s = seg[0].strip(), seg[1].strip()
            start = int(start_s) if start_s.isdigit() else 1
            end = int(end_s) if end_s.isdigit() else total_pages
            start = max(1, min(start, total_pages))
            end = max(1, min(end, total_pages))
            if start <= end:
                pages.update(range(start - 1, end))
            else:
                pages.update(range(end - 1, start))
        elif part.isdigit():
            p = int(part)
            if 1 <= p <= total_pages:
                pages.add(p - 1)
    
    res = sorted(list(pages))
    return res if res else list(range(total_pages))


class PDFMergerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF 智慧合併工具 (PDF Merger Pro)")
        self.root.geometry("960x700")
        self.root.minsize(800, 560)

        # 資料儲存列表：每個元素為 dict
        # {'path': str, 'name': str, 'pages': int, 'range': str, 'size': int, 'size_str': str}
        self.pdf_items = []
        self.is_merging = False
        self.last_output_path = ""

        self.setup_ui()

    def setup_ui(self):
        # 設定整體風格
        style = ttk.Style()
        try:
            style.theme_use('winnative')
        except Exception:
            pass

        style.configure("Treeview.Heading", font=("Microsoft JhengHei UI", 10, "bold"))
        style.configure("Treeview", font=("Microsoft JhengHei UI", 9), rowheight=26)
        style.configure("Action.TButton", font=("Microsoft JhengHei UI", 9))
        style.configure("Primary.TButton", font=("Microsoft JhengHei UI", 11, "bold"))

        # --- 頂部按鈕列 ---
        top_frame = ttk.Frame(self.root, padding="10 10 10 5")
        top_frame.pack(fill=tk.X)

        btn_add_files = ttk.Button(top_frame, text="📄 選擇多個檔案加入", style="Action.TButton", command=self.add_files)
        btn_add_files.pack(side=tk.LEFT, padx=(0, 6))

        btn_add_folder = ttk.Button(top_frame, text="📁 指定資料夾批次加入", style="Action.TButton", command=self.add_folder)
        btn_add_folder.pack(side=tk.LEFT, padx=6)

        btn_clear = ttk.Button(top_frame, text="🧹 清空清單", style="Action.TButton", command=self.clear_all)
        btn_clear.pack(side=tk.LEFT, padx=6)

        # 總結提示標籤
        self.lbl_summary = ttk.Label(top_frame, text="尚未載入任何 PDF 檔案", font=("Microsoft JhengHei UI", 9, "bold"), foreground="#0066CC")
        self.lbl_summary.pack(side=tk.RIGHT, padx=10)

        # --- 主要清單與操作區塊 ---
        mid_paned = ttk.Frame(self.root, padding="10 5 10 5")
        mid_paned.pack(fill=tk.BOTH, expand=True)

        # 左側 Treeview 列表
        list_frame = ttk.LabelFrame(mid_paned, text="待合併 PDF 檔案清單 (可多選進行順序調整或刪除)", padding="5")
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        columns = ("order", "filename", "pages", "page_range", "size", "path")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="extended")
        
        self.tree.heading("order", text="#", anchor=tk.CENTER)
        self.tree.heading("filename", text="檔案名稱", anchor=tk.W)
        self.tree.heading("pages", text="總頁數", anchor=tk.CENTER)
        self.tree.heading("page_range", text="合併頁面範圍", anchor=tk.CENTER)
        self.tree.heading("size", text="檔案大小", anchor=tk.E)
        self.tree.heading("path", text="完整路徑", anchor=tk.W)

        self.tree.column("order", width=45, minwidth=40, anchor=tk.CENTER)
        self.tree.column("filename", width=220, minwidth=150)
        self.tree.column("pages", width=65, minwidth=55, anchor=tk.CENTER)
        self.tree.column("page_range", width=110, minwidth=90, anchor=tk.CENTER)
        self.tree.column("size", width=85, minwidth=70, anchor=tk.E)
        self.tree.column("path", width=280, minwidth=150)

        tree_scroll_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        tree_scroll_x = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x.grid(row=1, column=0, sticky="ew")

        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self.on_item_double_click)

        # 右側順序/操作按鈕列
        side_btn_frame = ttk.Frame(mid_paned, padding="5 0 0 0")
        side_btn_frame.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Button(side_btn_frame, text="⬆ 項目上移", width=12, command=self.move_up).pack(pady=3)
        ttk.Button(side_btn_frame, text="⬇ 項目下移", width=12, command=self.move_down).pack(pady=3)
        ttk.Button(side_btn_frame, text="⏫ 移至頂部", width=12, command=self.move_top).pack(pady=3)
        ttk.Button(side_btn_frame, text="⏬ 移至底部", width=12, command=self.move_bottom).pack(pady=3)
        
        ttk.Separator(side_btn_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        
        ttk.Button(side_btn_frame, text="🔀 自然排序", width=12, command=self.sort_natural).pack(pady=3)
        ttk.Button(side_btn_frame, text="🔤 字典排序", width=12, command=self.sort_alphabetical).pack(pady=3)
        ttk.Button(side_btn_frame, text="🔄 反轉順序", width=12, command=self.reverse_list).pack(pady=3)
        
        ttk.Separator(side_btn_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        ttk.Button(side_btn_frame, text="✏ 設定頁面", width=12, command=self.set_page_range_dialog).pack(pady=3)
        ttk.Button(side_btn_frame, text="❌ 刪除選取", width=12, command=self.remove_selected).pack(pady=3)

        # --- 設定與輸出區塊 ---
        settings_frame = ttk.LabelFrame(self.root, text="合併設定與輸出路徑", padding="10 8 10 8")
        settings_frame.pack(fill=tk.X, padx=10, pady=5)

        # 輸出路徑
        out_row = ttk.Frame(settings_frame)
        out_row.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(out_row, text="輸出目標 PDF 路徑:", font=("Microsoft JhengHei UI", 9, "bold")).pack(side=tk.LEFT)
        self.output_path_var = tk.StringVar()
        self.entry_output = ttk.Entry(out_row, textvariable=self.output_path_var)
        self.entry_output.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)

        btn_browse_out = ttk.Button(out_row, text="瀏覽...", width=8, command=self.browse_output)
        btn_browse_out.pack(side=tk.RIGHT)

        # 進階選項
        opts_row = ttk.Frame(settings_frame)
        opts_row.pack(fill=tk.X)

        self.opt_bookmark = tk.BooleanVar(value=True)
        chk_bm = ttk.Checkbutton(opts_row, text="📌 依原檔名自動建立目錄書籤 (Bookmarks)", variable=self.opt_bookmark)
        chk_bm.pack(side=tk.LEFT, padx=(0, 15))

        self.opt_keep_sub_bm = tk.BooleanVar(value=True)
        chk_sub_bm = ttk.Checkbutton(opts_row, text="📑 保留各 PDF 原始內部書籤", variable=self.opt_keep_sub_bm)
        chk_sub_bm.pack(side=tk.LEFT, padx=10)

        # --- 執行與日誌區塊 ---
        action_frame = ttk.Frame(self.root, padding="10 5 10 10")
        action_frame.pack(fill=tk.BOTH, expand=False)

        # 執行按鈕與進度條
        exec_top = ttk.Frame(action_frame)
        exec_top.pack(fill=tk.X, pady=(0, 5))

        self.btn_start = tk.Button(
            exec_top, 
            text="🚀 開始合併 PDF", 
            font=("Microsoft JhengHei UI", 12, "bold"), 
            bg="#0078D7", 
            fg="white", 
            activebackground="#005A9E", 
            activeforeground="white",
            relief="raised",
            cursor="hand2",
            height=1,
            command=self.start_merge_thread
        )
        self.btn_start.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.btn_open_folder = ttk.Button(exec_top, text="📂 開啟輸出資料夾", state=tk.DISABLED, command=self.open_output_folder)
        self.btn_open_folder.pack(side=tk.RIGHT, padx=(5, 0))

        self.btn_open_pdf = ttk.Button(exec_top, text="📖 開啟合併後 PDF", state=tk.DISABLED, command=self.open_output_pdf)
        self.btn_open_pdf.pack(side=tk.RIGHT, padx=5)

        # 進度條與狀態文字
        prog_frame = ttk.Frame(action_frame)
        prog_frame.pack(fill=tk.X, pady=(0, 5))

        self.progress_bar = ttk.Progressbar(prog_frame, orient=tk.HORIZONTAL, mode='determinate')
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.lbl_status = ttk.Label(prog_frame, text="就緒", width=25, anchor=tk.E, font=("Microsoft JhengHei UI", 9))
        self.lbl_status.pack(side=tk.RIGHT)

        # 日誌視窗
        log_frame = ttk.LabelFrame(action_frame, text="執行日誌 (Log)", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.txt_log = ScrolledText(log_frame, height=5, font=("Consolas", 9), wrap=tk.WORD)
        self.txt_log.pack(fill=tk.BOTH, expand=True)
        self.txt_log.tag_config("INFO", foreground="#000000")
        self.txt_log.tag_config("SUCCESS", foreground="#008000", font=("Consolas", 9, "bold"))
        self.txt_log.tag_config("WARN", foreground="#D97706")
        self.txt_log.tag_config("ERROR", foreground="#DC2626", font=("Consolas", 9, "bold"))

        self.log("PDF 智慧合併工具已就緒。可點選上方按鈕加入檔案或直接選擇資料夾。")

    # --- 日誌輔助函式 ---
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.txt_log.insert(tk.END, f"[{timestamp}] ", "INFO")
        self.txt_log.insert(tk.END, f"{message}\n", level)
        self.txt_log.see(tk.END)

    # --- 檔案讀取與清單維護 ---
    def inspect_pdf(self, file_path):
        """讀取 PDF 資訊 (頁數、大小)"""
        try:
            file_size = os.path.getsize(file_path)
            reader = PdfReader(file_path)
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:
                    pass
            page_count = len(reader.pages)
            return {
                'path': os.path.abspath(file_path),
                'name': os.path.basename(file_path),
                'pages': page_count,
                'range': "全部",
                'size': file_size,
                'size_str': format_file_size(file_size)
            }
        except Exception as e:
            self.log(f"讀取 PDF 失敗 [{os.path.basename(file_path)}]: {e}", "WARN")
            return None

    def add_files(self):
        """選擇多個檔案加入"""
        files = filedialog.askopenfilenames(
            title="選擇要合併的 PDF 檔案",
            filetypes=[("PDF 檔案", "*.pdf"), ("所有檔案", "*.*")]
        )
        if not files:
            return

        added_count = 0
        existing_paths = {item['path'] for item in self.pdf_items}

        for f in files:
            abs_path = os.path.abspath(f)
            if abs_path in existing_paths:
                continue
            item = self.inspect_pdf(abs_path)
            if item:
                self.pdf_items.append(item)
                existing_paths.add(abs_path)
                added_count += 1

        self.refresh_treeview()
        self.suggest_output_path()
        self.log(f"成功加入 {added_count} 個 PDF 檔案。")

    def add_folder(self):
        """選擇資料夾批次加入"""
        folder = filedialog.askdirectory(title="選擇包含 PDF 的資料夾")
        if not folder:
            return

        # 詢問是否包含子資料夾
        include_sub = messagebox.askyesno("資料夾掃描選項", "是否一併搜尋子資料夾內的 PDF 檔案？\n\n[是]：包含所有子資料夾\n[否]：僅搜尋此資料夾")

        found_files = []
        if include_sub:
            for root_dir, _, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith(".pdf"):
                        found_files.append(os.path.join(root_dir, f))
        else:
            for f in os.listdir(folder):
                full_p = os.path.join(folder, f)
                if os.path.isfile(full_p) and f.lower().endswith(".pdf"):
                    found_files.append(full_p)

        if not found_files:
            messagebox.showinfo("提示", f"在資料夾 '{folder}' 中未找到任何 .pdf 檔案。")
            return

        # 預設套用自然排序
        found_files.sort(key=lambda p: natural_sort_key(os.path.basename(p)))

        added_count = 0
        existing_paths = {item['path'] for item in self.pdf_items}

        for f in found_files:
            abs_path = os.path.abspath(f)
            if abs_path in existing_paths:
                continue
            item = self.inspect_pdf(abs_path)
            if item:
                self.pdf_items.append(item)
                existing_paths.add(abs_path)
                added_count += 1

        self.refresh_treeview()
        self.suggest_output_path(base_folder=folder)
        self.log(f"從資料夾載入完成，共加入 {added_count} 個 PDF 檔案 (已預先套用自然排序)。")

    def suggest_output_path(self, base_folder=None):
        """依據載入的第一個檔案或所選資料夾，自動設定合理的預設輸出路徑"""
        if self.output_path_var.get().strip():
            return

        if base_folder and os.path.isdir(base_folder):
            default_out = os.path.join(base_folder, "merged_output.pdf")
        elif self.pdf_items:
            first_dir = os.path.dirname(self.pdf_items[0]['path'])
            default_out = os.path.join(first_dir, "merged_output.pdf")
        else:
            default_out = os.path.join(os.path.expanduser("~"), "Desktop", "merged_output.pdf")

        self.output_path_var.set(default_out)

    def browse_output(self):
        """選擇輸出檔案位置"""
        initial_dir = ""
        initial_file = "merged_output.pdf"
        current_val = self.output_path_var.get().strip()
        if current_val:
            initial_dir = os.path.dirname(current_val)
            initial_file = os.path.basename(current_val)

        file_path = filedialog.asksaveasfilename(
            title="儲存合併後的 PDF 檔案",
            initialdir=initial_dir if os.path.isdir(initial_dir) else None,
            initialfile=initial_file,
            defaultextension=".pdf",
            filetypes=[("PDF 檔案", "*.pdf")]
        )
        if file_path:
            self.output_path_var.set(os.path.abspath(file_path))

    def refresh_treeview(self):
        """重新整理 Treeview 顯示"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        total_pages = 0
        total_size = 0

        for idx, item in enumerate(self.pdf_items, start=1):
            total_pages += item['pages']
            total_size += item['size']
            self.tree.insert(
                "",
                tk.END,
                iid=str(idx - 1),
                values=(idx, item['name'], item['pages'], item['range'], item['size_str'], item['path'])
            )

        if self.pdf_items:
            self.lbl_summary.config(
                text=f"共 {len(self.pdf_items)} 個檔案 | 合計 {total_pages} 頁 | 總大小 {format_file_size(total_size)}"
            )
        else:
            self.lbl_summary.config(text="尚未載入任何 PDF 檔案")

    def clear_all(self):
        """清空所有檔案"""
        if not self.pdf_items:
            return
        if messagebox.askyesno("確認清空", "確定要清空目前的待合併清單嗎？"):
            self.pdf_items.clear()
            self.refresh_treeview()
            self.log("已清空待合併檔案清單。")

    def remove_selected(self):
        """刪除選取的項目"""
        selected_iids = self.tree.selection()
        if not selected_iids:
            messagebox.showinfo("提示", "請先點選欲刪除的檔案項目。")
            return

        indices_to_remove = sorted([int(iid) for iid in selected_iids], reverse=True)
        for idx in indices_to_remove:
            del self.pdf_items[idx]

        self.refresh_treeview()
        self.log(f"已移除 {len(indices_to_remove)} 個選取項目。")

    # --- 順序調整操作 ---
    def move_up(self):
        selected_iids = sorted([int(x) for x in self.tree.selection()])
        if not selected_iids or selected_iids[0] == 0:
            return

        for idx in selected_iids:
            self.pdf_items[idx - 1], self.pdf_items[idx] = self.pdf_items[idx], self.pdf_items[idx - 1]

        self.refresh_treeview()
        new_selection = [str(x - 1) for x in selected_iids]
        self.tree.selection_set(new_selection)

    def move_down(self):
        selected_iids = sorted([int(x) for x in self.tree.selection()], reverse=True)
        if not selected_iids or selected_iids[0] >= len(self.pdf_items) - 1:
            return

        for idx in selected_iids:
            self.pdf_items[idx + 1], self.pdf_items[idx] = self.pdf_items[idx], self.pdf_items[idx + 1]

        self.refresh_treeview()
        new_selection = [str(x + 1) for x in selected_iids]
        self.tree.selection_set(new_selection)

    def move_top(self):
        selected_iids = sorted([int(x) for x in self.tree.selection()])
        if not selected_iids:
            return

        selected_items = [self.pdf_items[i] for i in selected_iids]
        remaining_items = [self.pdf_items[i] for i in range(len(self.pdf_items)) if i not in selected_iids]
        self.pdf_items = selected_items + remaining_items

        self.refresh_treeview()
        new_selection = [str(i) for i in range(len(selected_items))]
        self.tree.selection_set(new_selection)

    def move_bottom(self):
        selected_iids = sorted([int(x) for x in self.tree.selection()])
        if not selected_iids:
            return

        selected_items = [self.pdf_items[i] for i in selected_iids]
        remaining_items = [self.pdf_items[i] for i in range(len(self.pdf_items)) if i not in selected_iids]
        self.pdf_items = remaining_items + selected_items

        self.refresh_treeview()
        start_idx = len(remaining_items)
        new_selection = [str(start_idx + i) for i in range(len(selected_items))]
        self.tree.selection_set(new_selection)

    def sort_natural(self):
        """按自然數值排序檔名"""
        self.pdf_items.sort(key=lambda item: natural_sort_key(item['name']))
        self.refresh_treeview()
        self.log("已按「檔名自然排序 (1, 2, 10...)」重整順序。")

    def sort_alphabetical(self):
        """按字典順序排序檔名"""
        self.pdf_items.sort(key=lambda item: item['name'].lower())
        self.refresh_treeview()
        self.log("已按「檔名字典順序 (A-Z)」重整順序。")

    def reverse_list(self):
        """反轉清單順序"""
        self.pdf_items.reverse()
        self.refresh_treeview()
        self.log("已將檔案清單順序完全反轉。")

    # --- 頁面範圍設定 ---
    def on_item_double_click(self, event):
        self.set_page_range_dialog()

    def set_page_range_dialog(self):
        selected_iids = self.tree.selection()
        if not selected_iids:
            messagebox.showinfo("提示", "請先選擇要設定頁面範圍的檔案。")
            return

        idx = int(selected_iids[0])
        item = self.pdf_items[idx]

        prompt_msg = (
            f"設定 [{item['name']}] 的合併頁面範圍：\n"
            f"該檔案總頁數：{item['pages']} 頁\n\n"
            "格式範例：\n"
            " • 全部頁面：填寫 '全部' 或 'all'\n"
            " • 前 5 頁：1-5\n"
            " • 指定頁面：1, 3, 5-8"
        )

        curr_val = item['range'] if item['range'] != "全部" else ""
        res = simpledialog.askstring("頁面範圍設定", prompt_msg, initialvalue=curr_val, parent=self.root)
        if res is not None:
            res_clean = res.strip()
            if not res_clean or res_clean.lower() in ("all", "全部", "*"):
                item['range'] = "全部"
            else:
                parsed = parse_page_range(res_clean, item['pages'])
                item['range'] = res_clean
                self.log(f"已更新 [{item['name']}] 頁面範圍為: {res_clean} (共擷取 {len(parsed)} 頁)")
            self.refresh_treeview()

    # --- PDF 合併執行邏輯 ---
    def start_merge_thread(self):
        if self.is_merging:
            return

        if not self.pdf_items:
            messagebox.showwarning("警告", "尚未加入任何待合併的 PDF 檔案！")
            return

        out_path = self.output_path_var.get().strip()
        if not out_path:
            messagebox.showwarning("警告", "請指定輸出 PDF 檔案路徑！")
            return

        if not out_path.lower().endswith(".pdf"):
            out_path += ".pdf"
            self.output_path_var.set(out_path)

        out_dir = os.path.dirname(out_path)
        if out_dir and not os.path.exists(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("錯誤", f"無法建立輸出目錄: {e}")
                return

        # 鎖定 UI 按鈕
        self.is_merging = True
        self.btn_start.config(state=tk.DISABLED, text="⏳ 正在合併中...")
        self.btn_open_folder.config(state=tk.DISABLED)
        self.btn_open_pdf.config(state=tk.DISABLED)
        self.progress_bar['value'] = 0

        thread = threading.Thread(target=self._merge_worker, args=(out_path,), daemon=True)
        thread.start()

    def _merge_worker(self, out_path):
        start_time = time.time()
        total_files = len(self.pdf_items)
        writer = PdfWriter()
        total_merged_pages = 0

        self.log("=" * 50)
        self.log(f"開始執行 PDF 合併作業，共 {total_files} 個檔案...")
        self.log(f"輸出目標: {out_path}")

        try:
            for idx, item in enumerate(self.pdf_items, start=1):
                f_path = item['path']
                f_name = item['name']
                range_str = item['range']

                self.root.after(0, self._update_status, idx, total_files, f"正在處理 ({idx}/{total_files}): {f_name}")

                if not os.path.exists(f_path):
                    self.log(f"⚠️ 檔案不存在，跳過: {f_path}", "WARN")
                    continue

                reader = PdfReader(f_path)
                if reader.is_encrypted:
                    try:
                        reader.decrypt("")
                    except Exception:
                        pass
                    if reader.is_encrypted:
                        self.log(f"🔒 檔案有密碼保護 [{f_name}]，嘗試跳過或需手動解密", "WARN")

                file_page_count = len(reader.pages)
                page_indices = parse_page_range(range_str, file_page_count)

                # 書籤名稱
                bookmark_title = os.path.splitext(f_name)[0] if self.opt_bookmark.get() else None
                import_outline = self.opt_keep_sub_bm.get()

                # 將頁面加入 writer
                writer.append(
                    fileobj=f_path,
                    outline_item=bookmark_title,
                    pages=page_indices,
                    import_outline=import_outline
                )

                total_merged_pages += len(page_indices)
                self.log(f"[{idx}/{total_files}] 已合併: {f_name} (加入 {len(page_indices)} 頁)")

                # 更新進度條
                progress = int((idx / total_files) * 100)
                self.root.after(0, self._set_progress, progress)

            # 寫入目標檔案
            self.root.after(0, self._update_status_text, "正在寫入最終 PDF 檔案...")
            with open(out_path, "wb") as f_out:
                writer.write(f_out)
            writer.close()

            elapsed = time.time() - start_time
            out_size = os.path.getsize(out_path)
            self.last_output_path = out_path

            self.log(f"🎉 合併完成！總計 {total_merged_pages} 頁，檔案大小: {format_file_size(out_size)} (耗時 {elapsed:.2f} 秒)", "SUCCESS")
            self.root.after(0, self._on_merge_success, out_path, total_merged_pages, elapsed)

        except PermissionError:
            self.log(f"❌ 寫入失敗: 檔案正在被其他程式開啟或無寫入權限！請關閉目標 PDF 後重試。", "ERROR")
            self.root.after(0, lambda: messagebox.showerror("存取權限錯誤", f"無法寫入檔案：\n{out_path}\n\n該檔案可能正被 Acrobat 或瀏覽器開啟，請先關閉後重試。"))
        except Exception as e:
            self.log(f"❌ 合併過程發生未預期錯誤: {e}", "ERROR")
            self.root.after(0, lambda: messagebox.showerror("合併失敗", f"發生錯誤：\n{e}"))
        finally:
            self.root.after(0, self._reset_ui)

    def _update_status(self, current, total, text):
        self.lbl_status.config(text=f"處理中 {current}/{total}")
        self.log(text)

    def _update_status_text(self, text):
        self.lbl_status.config(text=text)

    def _set_progress(self, val):
        self.progress_bar['value'] = val

    def _on_merge_success(self, out_path, total_pages, elapsed):
        self.lbl_status.config(text="合併成功！")
        self.btn_open_folder.config(state=tk.NORMAL)
        self.btn_open_pdf.config(state=tk.NORMAL)
        msg = f"PDF 合併成功！\n\n• 合併檔案數：{len(self.pdf_items)} 個\n• 總頁數：{total_pages} 頁\n• 耗時：{elapsed:.2f} 秒\n• 儲存位置：\n{out_path}"
        messagebox.showinfo("完成", msg)

    def _reset_ui(self):
        self.is_merging = False
        self.btn_start.config(state=tk.NORMAL, text="🚀 開始合併 PDF")

    def open_output_folder(self):
        """開啟輸出檔案所在的資料夾"""
        target = self.last_output_path or self.output_path_var.get().strip()
        if target and os.path.exists(target):
            folder = os.path.dirname(os.path.abspath(target))
            if sys.platform == "win32":
                os.startfile(folder)
            else:
                subprocess.Popen(["xdg-open", folder])
        else:
            folder = os.path.dirname(os.path.abspath(target)) if target else ""
            if folder and os.path.exists(folder):
                os.startfile(folder)
            else:
                messagebox.showwarning("提示", "輸出檔案或目錄尚不存在。")

    def open_output_pdf(self):
        """直接開啟合併後的 PDF"""
        target = self.last_output_path or self.output_path_var.get().strip()
        if target and os.path.exists(target):
            if sys.platform == "win32":
                os.startfile(target)
            else:
                subprocess.Popen(["xdg-open", target])
        else:
            messagebox.showwarning("提示", "輸出檔案尚未生成或已被移動。")


def main():
    root = tk.Tk()
    # 支援高 DPI 縮放 (Windows)
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = PDFMergerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
