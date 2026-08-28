"""GUI 主視窗。"""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


from config import APP_NAME, APP_VERSION
from core.device_scanner import scan_nvme_devices, NvmeDeviceInfo
from runner.csv_parser import parse_csv
from runner.batch_runner import BatchRunner, BatchConfig, ErrorPolicy
from core.parsers import format_hex_dump
from gui.widgets import HexViewer, ResultTable, CsvPreviewTable


class NvmeLogPageApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1000x700")
        
        self.devices = []
        self.test_cases = []
        self.runner = None
        self.output_dir = ""
        
        self._build_ui()
        self.refresh_devices()

    def _build_ui(self):
        # 頂部設定區
        settings_frame = ttk.LabelFrame(self.root, text="設定")
        settings_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 設備選擇
        ttk.Label(settings_frame, text="NVMe 設備:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(settings_frame, textvariable=self.device_var, state="readonly", width=50)
        self.device_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Button(settings_frame, text="重新整理", command=self.refresh_devices).grid(row=0, column=2, padx=5, pady=5)
        
        # CSV 檔案
        ttk.Label(settings_frame, text="CSV 腳本:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.csv_var = tk.StringVar()
        ttk.Entry(settings_frame, textvariable=self.csv_var, width=53).grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Button(settings_frame, text="瀏覽...", command=self.browse_csv).grid(row=1, column=2, padx=5, pady=5)
        
        # 參數
        params_frame = ttk.Frame(settings_frame)
        params_frame.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        ttk.Label(params_frame, text="間隔 (ms):").pack(side=tk.LEFT, padx=5)
        self.delay_var = tk.IntVar(value=100)
        ttk.Spinbox(params_frame, from_=0, to=1000, textvariable=self.delay_var, width=8).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(params_frame, text="錯誤策略:").pack(side=tk.LEFT, padx=5)
        self.error_policy_var = tk.StringVar(value=ErrorPolicy.CONTINUE.value)
        ttk.Combobox(params_frame, textvariable=self.error_policy_var, values=[e.value for e in ErrorPolicy], state="readonly", width=12).pack(side=tk.LEFT, padx=5)

        ttk.Label(params_frame, text="通道路徑:").pack(side=tk.LEFT, padx=5)
        self.channel_var = tk.StringVar(value="強制 Direct-MMIO (Ring0)")
        self.channel_combo = ttk.Combobox(
            params_frame,
            textvariable=self.channel_var,
            values=["強制 Direct-MMIO (Ring0)", "自動 (Auto)", "微軟 Pass-Through", "微軟 Protocol-Query"],
            state="readonly",
            width=22
        )
        self.channel_combo.pack(side=tk.LEFT, padx=5)
        
        # 控制區
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.btn_start = ttk.Button(control_frame, text="開始執行", command=self.start_execution)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        
        self.btn_stop = ttk.Button(control_frame, text="停止", command=self.stop_execution, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(control_frame, variable=self.progress_var, maximum=100)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.progress_text = tk.StringVar(value="0/0")
        ttk.Label(control_frame, textvariable=self.progress_text).pack(side=tk.LEFT, padx=5)
        
        # 結果區 (PanedWindow)
        paned = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.result_table = ResultTable(paned, on_select=self.on_result_select)
        paned.add(self.result_table, weight=1)
        
        self.hex_viewer = HexViewer(paned)
        paned.add(self.hex_viewer, weight=1)
        
        # 底部狀態列
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.status_var = tk.StringVar(value="就緒")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT)
        
        ttk.Button(status_frame, text="開啟輸出目錄", command=self.open_output_dir).pack(side=tk.RIGHT)

    def refresh_devices(self):
        try:
            self.devices = scan_nvme_devices()
            device_names = [d.display_name for d in self.devices]
            self.device_combo['values'] = device_names
            if device_names:
                self.device_combo.current(0)
            else:
                self.device_combo.set("")
        except Exception as e:
            messagebox.showerror("掃描失敗", str(e))
            
    def browse_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
        if file_path:
            self.csv_var.set(file_path)
            try:
                cases = parse_csv(file_path)
                self.test_cases = cases
                self.status_var.set(f"已載入 CSV: 共 {len(cases)} 筆測試案例")
            except Exception as e:
                self.status_var.set(f"CSV 解析錯誤: {e}")
            
    def open_output_dir(self):
        if self.output_dir and os.path.exists(self.output_dir):
            os.startfile(self.output_dir)
        else:
            messagebox.showinfo("提示", "目前沒有輸出目錄")

    def on_result_select(self, row_idx: int):
        result = self.result_table.get_result(row_idx)
        if result and result.data:
            hex_dump = format_hex_dump(result.data)
            self.hex_viewer.set_data(hex_dump)
        elif result and result.error_message:
            self.hex_viewer.set_data(f"Error: {result.error_message}")
        else:
            self.hex_viewer.clear()

    def start_execution(self):
        device_idx = self.device_combo.current()
        if device_idx < 0:
            messagebox.showerror("錯誤", "請選擇設備")
            return
            
        csv_path = self.csv_var.get()
        if not csv_path or not os.path.exists(csv_path):
            messagebox.showerror("錯誤", "請選擇有效的 CSV 檔案")
            return
            
        try:
            self.test_cases = parse_csv(csv_path)
        except Exception as e:
            messagebox.showerror("解析 CSV 失敗", str(e))
            return
            
        if not self.test_cases:
            messagebox.showwarning("警告", "CSV 沒有測試案例")
            return

        device = self.devices[device_idx]
        delay_ms = self.delay_var.get()
        error_policy = ErrorPolicy(self.error_policy_var.get())
        
        channel_str = self.channel_var.get()
        forced_channel = None
        if "Direct-MMIO" in channel_str:
            forced_channel = "Direct-MMIO"
        elif "Pass-Through" in channel_str:
            forced_channel = "Pass-Through"
        elif "Protocol-Query" in channel_str:
            forced_channel = "Protocol-Query"
        
        self.output_dir = os.path.join(os.getcwd(), "results")
        os.makedirs(self.output_dir, exist_ok=True)
        
        config = BatchConfig(
            device_number=device.drive_number,
            test_cases=self.test_cases,
            delay_ms=delay_ms,
            error_policy=error_policy,
            output_dir=self.output_dir,
            forced_channel=forced_channel
        )
        
        self.runner = BatchRunner(config)
        self.runner.on_progress = lambda c, t: self.root.after(0, self.update_progress, c, t)
        self.runner.on_result = lambda r: self.root.after(0, self.add_result, r)
        self.runner.on_complete = lambda rs: self.root.after(0, self.execution_complete, rs)
        self.runner.on_error = lambda e: self.root.after(0, self.execution_error, e)
        
        self.result_table.clear()
        self.hex_viewer.clear()
        
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.status_var.set("執行中...")
        
        self.runner.start()

    def stop_execution(self):
        if self.runner and self.runner.is_running:
            self.runner.stop()
            self.status_var.set("正在停止...")

    def update_progress(self, current: int, total: int):
        self.progress_var.set((current / total) * 100)
        self.progress_text.set(f"{current}/{total}")

    def add_result(self, result):
        self.result_table.add_result(result)

    def execution_complete(self, results):
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        if self.runner:
            self.output_dir = self.runner.output_dir
        self.status_var.set(f"執行完成 - 輸出: {self.output_dir}")
        messagebox.showinfo("完成", f"測試完成，共執行 {len(results)} 筆\n輸出目錄: {self.output_dir}")

    def execution_error(self, err_msg):
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.status_var.set(f"錯誤: {err_msg}")
        messagebox.showerror("執行錯誤", err_msg)
        
    def run(self):
        self.root.mainloop()
