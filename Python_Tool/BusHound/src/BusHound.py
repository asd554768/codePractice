import sys
import os

# 確保同目錄模組 (如 backend_storage) 能被正常載入
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess

from backend_storage import *  # 所有後端邏輯集中於 backend_storage.py
from firmware_updater import FirmwareUpdateEngine, natural_sort_key, CHUNK_SIZE, ADDR_INCREMENT


class ScsiToolGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Python Storage Debug Tool (Multi-Tab Edition)")
        self.root.geometry("1050x850") 
        
        self.create_global_header()
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.tab1 = ttk.Frame(self.notebook)
        self.tab2 = ttk.Frame(self.notebook)
        self.tab3 = ttk.Frame(self.notebook)
        self.tab4 = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab1, text=" SCSI Command (16-Byte) ")
        self.notebook.add(self.tab2, text=" Vendor/Ext Command (64-Byte VUC) ")
        self.notebook.add(self.tab3, text=" Packet Sniffer (即時封包監控) ")
        self.notebook.add(self.tab4, text=" MCU FW Update (韌體更新) ")
        
        self.init_tab1_scsi()
        self.init_tab2_64byte()
        self.init_tab3_sniffer()
        self.init_tab4_fw_update()

    def create_global_header(self):
        header_frame = tk.LabelFrame(self.root, text="Global Settings", padx=10, pady=5)
        header_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(header_frame, text="目標磁碟 (Target Drive):").pack(side=tk.LEFT)
        
        self.drive_combo = ttk.Combobox(header_frame, state="readonly", width=60)
        self.drive_combo.pack(side=tk.LEFT, padx=10)
        
        tk.Button(header_frame, text="🔄 Rescan", command=self.rescan_drives, bg="#E0E0E0", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.rescan_drives()

    def rescan_drives(self):
        current_selection = self.drive_combo.get()
        drives = get_physical_drives()
        self.drive_combo['values'] = drives
        
        if drives:
            if current_selection in drives:
                self.drive_combo.set(current_selection)
            else:
                self.drive_combo.current(0)
        else:
            self.drive_combo.set('')

    # ==========================================
    # Tab 1: 原本的 16-Byte SCSI 工具 
    # ==========================================
    def init_tab1_scsi(self):
        self.t1_dir_var = tk.IntVar(value=SCSI_IOCTL_DATA_IN)
        self.t1_loaded_data_bin = None
        self.t1_cdb_entries = []
        self.t1_last_in_data = None

        cfg_frame = tk.Frame(self.tab1, pady=5)
        cfg_frame.pack(fill=tk.X)
        
        tk.Radiobutton(cfg_frame, text="Data In (讀取)", variable=self.t1_dir_var, value=SCSI_IOCTL_DATA_IN).pack(side=tk.LEFT)
        tk.Radiobutton(cfg_frame, text="Data Out (寫入)", variable=self.t1_dir_var, value=SCSI_IOCTL_DATA_OUT).pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(cfg_frame, text="No Data", variable=self.t1_dir_var, value=SCSI_IOCTL_DATA_UNSPECIFIED).pack(side=tk.LEFT)

        cdb_frame = tk.LabelFrame(self.tab1, text="CDB (16-Byte)", padx=10, pady=5)
        cdb_frame.pack(fill=tk.X, pady=5)
        
        btn_f = tk.Frame(cdb_frame)
        btn_f.pack(fill=tk.X)
        tk.Button(btn_f, text="載入 CDB .bin", command=self.t1_load_cdb, bg="#E1F5FE").pack(side=tk.LEFT)
        tk.Button(btn_f, text="清空", command=self.t1_clear_cdb).pack(side=tk.LEFT, padx=5)

        matrix = tk.Frame(cdb_frame)
        matrix.pack(pady=5)
        for i in range(16):
            r, c = i // 8, i % 8
            cf = tk.Frame(matrix, padx=2, pady=2)
            cf.grid(row=r, column=c)
            tk.Label(cf, text=f"{i:02d}", font=("Arial", 7), fg="gray").pack()
            e = tk.Entry(cf, width=4, font=("Consolas", 12, "bold"), justify='center')
            e.insert(0, "00")
            e.pack()
            self.t1_cdb_entries.append(e)

        buf_frame = tk.LabelFrame(self.tab1, text="Data Buffer", padx=10, pady=5)
        buf_frame.pack(fill=tk.X, pady=5)
        tk.Label(buf_frame, text="傳輸長度 (Bytes):").pack(side=tk.LEFT)
        self.t1_len_entry = tk.Entry(buf_frame, width=15)
        self.t1_len_entry.insert(0, "36")
        self.t1_len_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(buf_frame, text="載入 Data Out .bin", command=self.t1_load_data).pack(side=tk.LEFT, padx=10)
        self.t1_data_lbl = tk.Label(buf_frame, text="未選擇檔案", fg="gray")
        self.t1_data_lbl.pack(side=tk.LEFT)

        act_f = tk.Frame(self.tab1, pady=5)
        act_f.pack(fill=tk.X)
        tk.Button(act_f, text="EXECUTE SCSI CMD", command=self.t1_execute, bg="#2E7D32", fg="white", font=("Arial", 11, "bold"), width=25).pack(side=tk.LEFT)
        tk.Button(act_f, text="儲存 Data In (.bin)", command=self.t1_save_data, bg="#FF9800", fg="white", font=("Arial", 10, "bold")).pack(side=tk.RIGHT)

        out_f = tk.Frame(self.tab1)
        out_f.pack(fill=tk.BOTH, expand=True)
        sb_y = tk.Scrollbar(out_f, orient=tk.VERTICAL)
        sb_x = tk.Scrollbar(out_f, orient=tk.HORIZONTAL)
        self.t1_out = tk.Text(
            out_f, font=("Consolas", 10), bg="#1E1E1E", fg="#D4D4D4",
            wrap=tk.NONE, yscrollcommand=sb_y.set, xscrollcommand=sb_x.set
        )
        self.t1_out.grid(row=0, column=0, sticky="nsew")
        sb_y.grid(row=0, column=1, sticky="ns")
        sb_x.grid(row=1, column=0, sticky="ew")
        out_f.grid_rowconfigure(0, weight=1)
        out_f.grid_columnconfigure(0, weight=1)
        sb_y.config(command=self.t1_out.yview)
        sb_x.config(command=self.t1_out.xview)

    # Tab 1 Methods 
    def t1_load_cdb(self):
        p = filedialog.askopenfilename()
        if p:
            with open(p, "rb") as f:
                d = f.read(32)
                for i, b in enumerate(d[:16]):
                    self.t1_cdb_entries[i].delete(0, tk.END); self.t1_cdb_entries[i].insert(0, f"{b:02X}")
                if self.t1_dir_var.get() == SCSI_IOCTL_DATA_IN and len(d) > 16:
                    l = int.from_bytes(d[16:32], 'little')
                    self.t1_len_entry.delete(0, tk.END); self.t1_len_entry.insert(0, str(l))
                    
    def t1_clear_cdb(self):
        for e in self.t1_cdb_entries: e.delete(0, tk.END); e.insert(0, "00")
        
    def t1_load_data(self):
        p = filedialog.askopenfilename()
        if p:
            with open(p, "rb") as f: self.t1_loaded_data_bin = f.read()
            self.t1_data_lbl.config(text=f"已載入: {os.path.basename(p)}", fg="green")
            self.t1_len_entry.delete(0, tk.END); self.t1_len_entry.insert(0, str(len(self.t1_loaded_data_bin)))
            self.t1_dir_var.set(SCSI_IOCTL_DATA_OUT)
            
    def t1_save_data(self):
        if not self.t1_last_in_data: return messagebox.showwarning("警告", "無 Data In 可存！")
        p = filedialog.asksaveasfilename(defaultextension=".bin")
        if p:
            with open(p, "wb") as f: f.write(self.t1_last_in_data)
            
    def t1_log(self, m):
        self.t1_out.insert(tk.END, m + "\n"); self.t1_out.see(tk.END)
        
    def t1_execute(self):
        self.t1_out.delete(1.0, tk.END); self.t1_last_in_data = None
        handle = None
        try:
            dnum = int(self.drive_combo.get().split(" ")[0].replace("PhysicalDrive", ""))
            cdb = [int(e.get() or "00", 16) for e in self.t1_cdb_entries]
            length = int(self.t1_len_entry.get() or "0") if self.t1_dir_var.get() != SCSI_IOCTL_DATA_UNSPECIFIED else 0
            out_b = list(self.t1_loaded_data_bin) if self.t1_loaded_data_bin else [0]*length
            
            handle = open_drive(dnum)
            
            # --- 解析並顯示指令 ---
            decoded_cmd = decode_cdb(cdb)
            self.t1_log(f">>> 發送指令: {decoded_cmd}")
            self.t1_log(f"    (Length: {length} Bytes)")
            
            st, data, sense = send_scsi_command(handle, cdb, length, self.t1_dir_var.get(), out_b, drive_label=f"PhysicalDrive{dnum}")
            
            # --- 解析並顯示狀態與錯誤 ---
            st_str = SCSI_STATUS_DICT.get(st, "UNKNOWN STATUS")
            self.t1_log(f"\n[返回狀態] {st_str} (0x{st:02X})")
            
            if st == 0x02: # CHECK CONDITION
                self.t1_log(f" ⚠️ [錯誤解析] {parse_sense_data(sense)}")
                self.t1_log(f"    [Raw Sense] {hexdump(sense, 16)}")
                
            if self.t1_dir_var.get() == SCSI_IOCTL_DATA_IN and length > 0 and st == 0:
                self.t1_last_in_data = data
                self.t1_log("\n--- 接收資料 (Data In) ---")
                self.t1_log(hexdump(data))
                
        except Exception as e: 
            self.t1_log(f"Error: {e}")
        finally:
            if handle: close_drive(handle)

    # ==========================================
    # Tab 2: VUC 64-Byte 工具區塊
    # ==========================================
    def init_tab2_64byte(self):
        self.t2_dir_var = tk.IntVar(value=SCSI_IOCTL_DATA_IN)
        self.t2_entries = []
        self.t2_ap_key_var = tk.BooleanVar(value=True)
        self.t2_lock_var = tk.BooleanVar(value=True)
        self.t2_keep_lock_var = tk.BooleanVar(value=False)  # BUG-3 fix: 純解鎖模式後是否保持磁碟鎖定
        self.t2_last_in_data = None
        self.t2_loaded_data_bin = None

        ctrl_frame = tk.Frame(self.tab2, pady=10)
        ctrl_frame.pack(fill=tk.X, padx=10)

        tk.Checkbutton(ctrl_frame, text="AP_KEY (解鎖)", variable=self.t2_ap_key_var, font=("Arial", 10, "bold"), fg="#D32F2F").pack(side=tk.LEFT, padx=10)
        
        tk.Checkbutton(ctrl_frame, text="Lock Device (防干擾鎖定)", variable=self.t2_lock_var, font=("Arial", 10, "bold"), fg="#E65100").pack(side=tk.LEFT, padx=5)
        # BUG-3 fix: 讓使用者選擇純解鎖模式後是否持續保持磁碟獨佔鎖定
        tk.Checkbutton(ctrl_frame, text="Keep Lock (純解鎖後維持鎖定)", variable=self.t2_keep_lock_var, font=("Arial", 9), fg="#5D4037").pack(side=tk.LEFT, padx=5)

        ttk.Separator(ctrl_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        tk.Radiobutton(ctrl_frame, text="Data In", variable=self.t2_dir_var, value=SCSI_IOCTL_DATA_IN).pack(side=tk.LEFT)
        tk.Radiobutton(ctrl_frame, text="Data Out", variable=self.t2_dir_var, value=SCSI_IOCTL_DATA_OUT).pack(side=tk.LEFT)
        tk.Radiobutton(ctrl_frame, text="No Data", variable=self.t2_dir_var, value=SCSI_IOCTL_DATA_UNSPECIFIED).pack(side=tk.LEFT)
        
        ttk.Separator(ctrl_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        tk.Label(ctrl_frame, text="Length (Bytes):").pack(side=tk.LEFT)
        self.t2_len_entry = tk.Entry(ctrl_frame, width=12)
        self.t2_len_entry.insert(0, "0")
        self.t2_len_entry.pack(side=tk.LEFT, padx=5)

        tk.Button(ctrl_frame, text="載入 Data Out .bin", command=self.t2_load_data_file).pack(side=tk.LEFT, padx=5)
        self.t2_data_lbl = tk.Label(ctrl_frame, text="", fg="gray")
        self.t2_data_lbl.pack(side=tk.LEFT)

        grid_frame = tk.LabelFrame(self.tab2, text="Command Bytes (64-Byte Payload / VUC)", padx=10, pady=10)
        grid_frame.pack(fill=tk.X, padx=10, pady=5)

        btn_box = tk.Frame(grid_frame)
        btn_box.pack(fill=tk.X, pady=5)
        tk.Button(btn_box, text="載入 64-Byte .bin", command=self.t2_load_64b_bin, bg="#E8EAF6").pack(side=tk.LEFT)
        tk.Button(btn_box, text="清空矩陣", command=self.t2_clear_grid).pack(side=tk.LEFT, padx=5)

        matrix = tk.Frame(grid_frame)
        matrix.pack()
        
        for col in range(16):
            tk.Label(matrix, text=f"{col:02X}", fg="#3F51B5", font=("Arial", 8, "bold")).grid(row=0, column=col+1)
            
        for row in range(4):
            tk.Label(matrix, text=f"{row*16:02X}:", fg="#3F51B5", font=("Arial", 8, "bold")).grid(row=row+1, column=0, padx=5)
            for col in range(16):
                idx = row * 16 + col
                e = tk.Entry(matrix, width=3, font=("Consolas", 12), justify='center')
                e.insert(0, "00")
                e.grid(row=row+1, column=col+1, padx=2, pady=2)
                self.t2_entries.append(e)

        act_f = tk.Frame(self.tab2, padx=10, pady=5)
        act_f.pack(fill=tk.X)
        tk.Button(act_f, text="EXECUTE 64-BYTE VUC", command=self.t2_execute, bg="#1976D2", fg="white", font=("Arial", 11, "bold"), width=30).pack(side=tk.LEFT)
        tk.Button(act_f, text="儲存 Data In (.bin)", command=self.t2_save_data, bg="#FF9800", fg="white", font=("Arial", 10, "bold")).pack(side=tk.RIGHT)

        out_f = tk.Frame(self.tab2, padx=10, pady=5)
        out_f.pack(fill=tk.BOTH, expand=True)
        sb_y = tk.Scrollbar(out_f, orient=tk.VERTICAL)
        sb_x = tk.Scrollbar(out_f, orient=tk.HORIZONTAL)
        self.t2_out = tk.Text(
            out_f, font=("Consolas", 10), bg="#000000", fg="#00FF00",
            wrap=tk.NONE, yscrollcommand=sb_y.set, xscrollcommand=sb_x.set
        )
        self.t2_out.grid(row=0, column=0, sticky="nsew")
        sb_y.grid(row=0, column=1, sticky="ns")
        sb_x.grid(row=1, column=0, sticky="ew")
        out_f.grid_rowconfigure(0, weight=1)
        out_f.grid_columnconfigure(0, weight=1)
        sb_y.config(command=self.t2_out.yview)
        sb_x.config(command=self.t2_out.xview)

    def t2_log(self, msg):
        self.t2_out.insert(tk.END, msg + "\n")
        self.t2_out.see(tk.END)
        
    def t2_log_error(self, step_name, status, sense):
        """專門處理錯誤解析與顯示的輔助函式"""
        st_str = SCSI_STATUS_DICT.get(status, "UNKNOWN STATUS")
        self.t2_log(f"   [Error] {step_name} 失敗！Status: {st_str} (0x{status:02X})")
        if status == 0x02:
            self.t2_log(f"   ⚠️ [錯誤解析] {parse_sense_data(sense)}")

    def t2_clear_grid(self):
        for e in self.t2_entries:
            e.delete(0, tk.END); e.insert(0, "00")

    def t2_load_64b_bin(self):
        path = filedialog.askopenfilename(title="選擇 64-Byte Bin 檔案")
        if path:
            with open(path, "rb") as f:
                data = f.read(64)
                for i, byte in enumerate(data):
                    if i < 64:
                        self.t2_entries[i].delete(0, tk.END)
                        self.t2_entries[i].insert(0, f"{byte:02X}")
                
                # BUG-4 fix: 加上限保護 + 讓使用者確認自動解析值
                if len(data) >= 44:
                    length_bytes = data[40:44]
                    raw_val = int.from_bytes(length_bytes, byteorder='little')
                    transfer_length = raw_val * 4
                    if transfer_length > MAX_TRANSFER_BYTES:
                        self.t2_log(f"[Auto-Parse] ⚠️ 解析長度 {transfer_length} Bytes 超出安全上限 ({MAX_TRANSFER_BYTES // 1024 // 1024}MB)，已略過自動填入")
                    elif transfer_length > 0:
                        ok = messagebox.askyesno(
                            "確認自動解析長度",
                            f"從 Offset 40-43 解析出：\n"
                            f"  Raw value: 0x{raw_val:08X} (×4 = {transfer_length} Bytes)\n\n"
                            f"是否套用此長度？"
                        )
                        if ok:
                            self.t2_len_entry.delete(0, tk.END)
                            self.t2_len_entry.insert(0, str(transfer_length))
                            self.t2_log(f"[Auto-Parse] 已套用長度: {transfer_length} Bytes (raw=0x{raw_val:08X})")
                        else:
                            self.t2_log(f"[Auto-Parse] 使用者略過自動長度填入")

    def t2_load_data_file(self):
        path = filedialog.askopenfilename(title="選擇 Data Out Bin 檔案")
        if path:
            with open(path, "rb") as f: self.t2_loaded_data_bin = f.read()
            self.t2_data_lbl.config(text=f"已載入: {os.path.basename(path)}", fg="green")
            self.t2_len_entry.delete(0, tk.END)
            self.t2_len_entry.insert(0, str(len(self.t2_loaded_data_bin)))
            self.t2_dir_var.set(SCSI_IOCTL_DATA_OUT)

    def t2_save_data(self):
        if not self.t2_last_in_data:
            return messagebox.showwarning("無法儲存", "目前沒有可用的 Data In 資料！")
        path = filedialog.asksaveasfilename(defaultextension=".bin")
        if path:
            with open(path, "wb") as f: f.write(self.t2_last_in_data)
            self.t2_log(f"[存檔成功] 已儲存 {len(self.t2_last_in_data)} Bytes 到 {os.path.basename(path)}")

    def t2_execute(self):
        self.t2_out.delete(1.0, tk.END)
        self.t2_last_in_data = None
        handle = None
        lock_enabled = False  # BUG-2 fix: 確保 finally 安全，防止賦值前 crash 導致 NameError
        
        try:
            drive_num = int(self.drive_combo.get().split(" ")[0].replace("PhysicalDrive", ""))
            
            cmd_64_bytes = []
            for entry in self.t2_entries:
                val = entry.get().strip()
                cmd_64_bytes.append(int(val if val else "00", 16))
                
            length = int(self.t2_len_entry.get().strip() or "0")
            direction = self.t2_dir_var.get()
            ap_key_enabled = self.t2_ap_key_var.get()
            lock_enabled = self.t2_lock_var.get()

            is_matrix_empty = all(b == 0 for b in cmd_64_bytes)

            handle = open_drive(drive_num)
            
            if lock_enabled:
                self.t2_log("================= LOCK STATUS ================")
                is_locked, err_code = lock_drive(handle)
                if is_locked:
                    self.t2_log("[ O K ] 實體磁碟已成功獨佔鎖定 (FSCTL_LOCK_VOLUME)")
                else:
                    self.t2_log(f"[WARNING] 鎖定失敗！(Error Code: {err_code}) - 請注意背景干擾")
                self.t2_log("==============================================\n")

            # ==========================================
            # 1. AP_KEY 解鎖序列
            # ==========================================
            if ap_key_enabled:
                self.t2_log("==========================================")
                self.t2_log("[AP_KEY Auth] 開始執行特權解鎖序列 (3 cmds)...")
                
                # BUG-5 fix: 多路徑搜尋 AP_Key，找不到則讓使用者手動選擇
                # Packaging fix: 使用 get_base_dir() 支援 PyInstaller EXE 模式
                base_dir = get_base_dir()
                search_dirs = [
                    base_dir,                              # EXE旁邊 (frozen) 或腳本目錄
                    os.getcwd(),                           # 當前工作目錄
                    os.path.dirname(base_dir),             # 上一層目錄
                ]
                ap_key_path = None
                for d in search_dirs:
                    candidate = os.path.join(d, "AP_Key", "ap_key.bin")
                    if os.path.exists(candidate):
                        ap_key_path = candidate
                        self.t2_log(f"[AP_KEY] 找到金鑰: {candidate}")
                        break
                
                if ap_key_path is None:
                    self.t2_log("[AP_KEY] 自動搜尋未找到 AP_Key\\ap_key.bin，請手動選擇...")
                    ap_key_path = filedialog.askopenfilename(
                        title="選擇 AP Key 檔案 (ap_key.bin)",
                        filetypes=[("Binary files", "*.bin"), ("All files", "*.*")]
                    )
                    if not ap_key_path:
                        self.t2_log("[Error] 使用者取消選擇，中止執行。")
                        return
                
                with open(ap_key_path, "rb") as f:
                    ap_key_data = f.read(512)
                if len(ap_key_data) < 512:
                    ap_key_data = ap_key_data.ljust(512, b'\x00')

                cdb1 = [0x06, 0xfe, 0xc0, 0x00, 0x01, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
                self.t2_log(f" -> [AP_KEY 1/3] {decode_cdb(cdb1)}")
                st1, _, sense1 = send_scsi_command(handle, cdb1, 512, SCSI_IOCTL_DATA_OUT, list(ap_key_data), drive_label=f"PhysicalDrive{drive_num}")
                if st1 != 0: return self.t2_log_error("序列 1", st1, sense1)

                cdb2 = [0x06, 0xfe, 0xc1, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
                self.t2_log(f" -> [AP_KEY 2/3] {decode_cdb(cdb2)}")
                st2, _, sense2 = send_scsi_command(handle, cdb2, 0, SCSI_IOCTL_DATA_UNSPECIFIED, None, drive_label=f"PhysicalDrive{drive_num}")
                if st2 != 0: return self.t2_log_error("序列 2", st2, sense2)

                cdb3 = [0x06, 0xfe, 0xc3, 0x00, 0x01, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
                self.t2_log(f" -> [AP_KEY 3/3] {decode_cdb(cdb3)}")
                st3, _, sense3 = send_scsi_command(handle, cdb3, 512, SCSI_IOCTL_DATA_IN, None, drive_label=f"PhysicalDrive{drive_num}")
                if st3 != 0: return self.t2_log_error("序列 3", st3, sense3)

                self.t2_log("[AP_KEY Auth] 解鎖成功，硬碟進入特權模式！")
                self.t2_log("==========================================\n")
            
            if ap_key_enabled and is_matrix_empty:
                self.t2_log("[系統提示] 偵測到 64-Byte 矩陣全為 0 => 純解鎖模式，跳過 VUC 指令。")
                # BUG-3 fix: 若使用者勾選「Keep Lock」，純解鎖模式結束後不解鎖磁碟
                if lock_enabled and self.t2_keep_lock_var.get():
                    self.t2_log("[Keep Lock] 保持磁碟獨佔鎖定狀態（請記得手動關閉程式以解鎖）")
                    lock_enabled = False  # 讓 finally 跳過 unlock_drive
                return

            # ==========================================
            # 2. VUC 主體指令序列
            # ==========================================
            self.t2_log("==========================================")
            self.t2_log(f"[VUC Sequence] 背景執行 64-Byte VUC 配置序列...")
            
            vuc_cdb1 = [0x06, 0xfe, 0xc0, 0x00, 0x01, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
            vuc1_payload = cmd_64_bytes.copy()
            if len(vuc1_payload) < 512:
                vuc1_payload += [0] * (512 - len(vuc1_payload))
                
            st_vuc1, _, sense_vuc1 = send_scsi_command(handle, vuc_cdb1, 512, SCSI_IOCTL_DATA_OUT, vuc1_payload, drive_label=f"PhysicalDrive{drive_num}")
            if st_vuc1 != 0: return self.t2_log_error("VUC 1 (配置指令)", st_vuc1, sense_vuc1)

            sectors = (length + 511) // 512 if length > 0 else 0
            b3 = (sectors >> 8) & 0xFF
            b4 = sectors & 0xFF
            
            bytes_len = length
            b5 = (bytes_len >> 24) & 0xFF
            b6 = (bytes_len >> 16) & 0xFF
            b7 = (bytes_len >> 8) & 0xFF
            b8 = bytes_len & 0xFF

            if direction == SCSI_IOCTL_DATA_IN:
                b2 = 0xc2
            else:
                b2 = 0xc1
                
            vuc_cdb2 = [0x06, 0xfe, b2, b3, b4, b5, b6, b7, b8, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
            
            self.t2_log(f" -> 發送主要指令: {decode_cdb(vuc_cdb2)}")
            self.t2_log(f"    (Sectors: 0x{sectors:04X} -> Byte3: 0x{b3:02X}, Byte4: 0x{b4:02X})")
            self.t2_log(f"    (Bytes Length: 0x{bytes_len:08X} -> Byte5~8: 0x{b5:02X} 0x{b6:02X} 0x{b7:02X} 0x{b8:02X})")
            
            out_b = None
            if direction == SCSI_IOCTL_DATA_OUT:
                out_b = list(self.t2_loaded_data_bin) if self.t2_loaded_data_bin else [0]*length
                if len(out_b) < length: out_b += [0]*(length-len(out_b))
                out_b = out_b[:length]

            st_vuc2, data_vuc2, sense_vuc2 = send_scsi_command(handle, vuc_cdb2, length, direction, out_b, drive_label=f"PhysicalDrive{drive_num}")
            if st_vuc2 != 0: return self.t2_log_error("VUC 2 (資料傳輸)", st_vuc2, sense_vuc2)
            
            if direction == SCSI_IOCTL_DATA_IN and length > 0:
                self.t2_last_in_data = data_vuc2 
                self.t2_log("\n--- VUC 傳輸結果 (Data-In) ---")
                self.t2_log(hexdump(data_vuc2))
                self.t2_log("--------------------------------\n")
            elif direction == SCSI_IOCTL_DATA_OUT:
                self.t2_log("    (Data-Out Payload 傳輸成功)\n")
            elif direction == SCSI_IOCTL_DATA_UNSPECIFIED:
                self.t2_log("    (No-Data 指令執行成功)\n")

            vuc_cdb3 = [0x06, 0xfe, 0xc3, 0x00, 0x01, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
            st_vuc3, data_vuc3, sense_vuc3 = send_scsi_command(handle, vuc_cdb3, 512, SCSI_IOCTL_DATA_IN, None, drive_label=f"PhysicalDrive{drive_num}")
            if st_vuc3 != 0: return self.t2_log_error("VUC 3 (狀態讀取)", st_vuc3, sense_vuc3)
            
            self.t2_log("[VUC Sequence] 全部指令序列執行成功！")
            self.t2_log("==========================================")

        except Exception as e:
            self.t2_log(f"[Exception] 發生未預期錯誤: {str(e)}")
        finally:
            # BUG-1 fix: 改用 is not None 語意更嚴謹
            if handle is not None:
                if lock_enabled:
                    unlock_drive(handle)
                close_drive(handle)

    # ==========================================
    # Tab 3: 即時封包監控 (Packet Sniffer)
    # ==========================================
    def init_tab3_sniffer(self):
        self.t3_auto_scroll = tk.BooleanVar(value=True)
        self.t3_selected_record = None
        self.t3_records_map = {}  # index -> rec dict

        # 頂部控制面板
        ctrl_frame = tk.Frame(self.tab3, pady=6)
        ctrl_frame.pack(fill=tk.X, padx=10)

        self.t3_toggle_btn = tk.Button(
            ctrl_frame, text="■ 停止監控 (Stop)", command=self.t3_toggle_sniffer,
            bg="#D32F2F", fg="white", font=("Arial", 9, "bold"), width=16
        )
        self.t3_toggle_btn.pack(side=tk.LEFT, padx=5)

        self.t3_status_lbl = tk.Label(
            ctrl_frame, text="● 監控錄製中 (Recording)", fg="#2E7D32", font=("Arial", 9, "bold")
        )
        self.t3_status_lbl.pack(side=tk.LEFT, padx=10)

        tk.Button(
            ctrl_frame, text="🗑 清空列表 (Clear)", command=self.t3_clear_packets,
            bg="#E0E0E0", font=("Arial", 9)
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            ctrl_frame, text="💾 匯出 CSV (Export)", command=self.t3_export_csv,
            bg="#1976D2", fg="white", font=("Arial", 9, "bold")
        ).pack(side=tk.LEFT, padx=5)

        tk.Checkbutton(
            ctrl_frame, text="自動捲動至最新", variable=self.t3_auto_scroll, font=("Arial", 9)
        ).pack(side=tk.LEFT, padx=10)

        self.t3_count_lbl = tk.Label(
            ctrl_frame, text="總封包數: 0", font=("Arial", 9, "bold"), fg="#1565C0"
        )
        self.t3_count_lbl.pack(side=tk.RIGHT, padx=10)

        # 中間與底部：垂直分割視窗 (PanedWindow)
        paned = ttk.PanedWindow(self.tab3, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 1. 上半部：封包清單表格 (Treeview，緊湊比例)
        table_frame = tk.Frame(paned)
        paned.add(table_frame, weight=1)

        cols = ("idx", "time", "drive", "dir", "cmd", "len", "status", "latency")
        self.t3_tree = ttk.Treeview(
            table_frame, columns=cols, show="headings", selectmode="browse", height=6
        )

        self.t3_tree.heading("idx", text="#")
        self.t3_tree.heading("time", text="時間 (Time)")
        self.t3_tree.heading("drive", text="目標磁碟 (Drive)")
        self.t3_tree.heading("dir", text="方向 (Dir)")
        self.t3_tree.heading("cmd", text="指令名稱 (Command)")
        self.t3_tree.heading("len", text="長度 (Bytes)")
        self.t3_tree.heading("status", text="SCSI 狀態 (Status)")
        self.t3_tree.heading("latency", text="延遲 (ms)")

        self.t3_tree.column("idx", width=45, anchor="center")
        self.t3_tree.column("time", width=95, anchor="center")
        self.t3_tree.column("drive", width=120, anchor="center")
        self.t3_tree.column("dir", width=55, anchor="center")
        self.t3_tree.column("cmd", width=250, anchor="w")
        self.t3_tree.column("len", width=75, anchor="e")
        self.t3_tree.column("status", width=140, anchor="w")
        self.t3_tree.column("latency", width=75, anchor="e")

        tree_v_sb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.t3_tree.yview)
        tree_h_sb = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.t3_tree.xview)
        self.t3_tree.configure(yscrollcommand=tree_v_sb.set, xscrollcommand=tree_h_sb.set)

        self.t3_tree.grid(row=0, column=0, sticky="nsew")
        tree_v_sb.grid(row=0, column=1, sticky="ns")
        tree_h_sb.grid(row=1, column=0, sticky="ew")

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.t3_tree.tag_configure("tag_in", foreground="#1B5E20")
        self.t3_tree.tag_configure("tag_out", foreground="#E65100")
        self.t3_tree.tag_configure("tag_none", foreground="#424242")
        self.t3_tree.tag_configure("tag_error", foreground="#B71C1C", background="#FFEBEE")

        self.t3_tree.bind("<<TreeviewSelect>>", self.t3_on_select_packet)

        # 2. 下半部：封包詳細檢視 (佔據 70% 空間，100% 全寬度 Hexdump)
        detail_frame = tk.LabelFrame(paned, text="封包詳細檢視 (Packet Inspector & Full-Width Hexdump)", padx=10, pady=6)
        paned.add(detail_frame, weight=3)

        # 頂部緊湊摘要列 (橫向排列 CDB, Sense, 存檔按鈕)
        meta_frame = tk.Frame(detail_frame)
        meta_frame.pack(fill=tk.X, pady=(0, 6))

        # Row 1: CDB (16-Byte Hex) 與 Sense Data (橫向分欄)
        r1_frame = tk.Frame(meta_frame)
        r1_frame.pack(fill=tk.X, pady=(0, 4))

        tk.Label(r1_frame, text="CDB (Hex):", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.t3_cdb_txt = tk.Text(r1_frame, height=1, width=42, font=("Consolas", 9), bg="#F5F5F5", relief=tk.SOLID, bd=1)
        self.t3_cdb_txt.pack(side=tk.LEFT, padx=(4, 15))

        tk.Label(r1_frame, text="Sense Data:", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.t3_sense_txt = tk.Text(r1_frame, height=1, font=("Consolas", 9), bg="#F5F5F5", relief=tk.SOLID, bd=1)
        self.t3_sense_txt.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 10))

        tk.Button(
            r1_frame, text="💾 另存 Payload (.bin)", command=self.t3_save_selected_payload,
            bg="#FFF3E0", font=("Arial", 9, "bold")
        ).pack(side=tk.RIGHT)

        # Row 2: 狀態摘要標籤
        self.t3_summary_lbl = tk.Label(
            meta_frame, text="請從上方清單點選封包以檢視內容", fg="#0D47A1", font=("Arial", 9, "bold"), anchor="w"
        )
        self.t3_summary_lbl.pack(fill=tk.X)

        # 底部：超大寬度與高度的 Payload Hexdump 終端區
        dump_f = tk.Frame(detail_frame)
        dump_f.pack(fill=tk.BOTH, expand=True)

        dump_sb_y = ttk.Scrollbar(dump_f, orient=tk.VERTICAL)
        dump_sb_x = ttk.Scrollbar(dump_f, orient=tk.HORIZONTAL)
        self.t3_dump_txt = tk.Text(
            dump_f, font=("Consolas", 10), bg="#1E1E1E", fg="#A7F3D0",
            wrap=tk.NONE, yscrollcommand=dump_sb_y.set, xscrollcommand=dump_sb_x.set
        )
        self.t3_dump_txt.grid(row=0, column=0, sticky="nsew")
        dump_sb_y.grid(row=0, column=1, sticky="ns")
        dump_sb_x.grid(row=1, column=0, sticky="ew")
        dump_f.grid_rowconfigure(0, weight=1)
        dump_f.grid_columnconfigure(0, weight=1)
        dump_sb_y.config(command=self.t3_dump_txt.yview)
        dump_sb_x.config(command=self.t3_dump_txt.xview)

        # 預設啟動 PacketLogger 並註冊 Callback
        packet_logger.enable()
        packet_logger.add_callback(lambda rec: self.root.after(0, self.t3_on_new_packet, rec))

    # Tab 3 Methods
    def t3_toggle_sniffer(self):
        if packet_logger.is_enabled:
            packet_logger.disable()
            self.t3_toggle_btn.config(text="▶ 啟動監控 (Start)", bg="#2E7D32")
            self.t3_status_lbl.config(text="○ 已暫停監控 (Paused)", fg="#757575")
        else:
            packet_logger.enable()
            self.t3_toggle_btn.config(text="■ 停止監控 (Stop)", bg="#D32F2F")
            self.t3_status_lbl.config(text="● 監控錄製中 (Recording)", fg="#2E7D32")

    def t3_clear_packets(self):
        packet_logger.clear()
        self.t3_records_map.clear()
        self.t3_selected_record = None
        for item in self.t3_tree.get_children():
            self.t3_tree.delete(item)
        self.t3_count_lbl.config(text="總封包數: 0")
        self.t3_cdb_txt.delete(1.0, tk.END)
        self.t3_sense_txt.delete(1.0, tk.END)
        self.t3_dump_txt.delete(1.0, tk.END)
        self.t3_summary_lbl.config(text="列表已清空", fg="gray")

    def t3_export_csv(self):
        if not packet_logger.get_all():
            return messagebox.showinfo("提示", "目前沒有任何封包記錄可匯出！")
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files (*.csv)", "*.csv"), ("All Files", "*.*")],
            title="匯出封包紀錄為 CSV"
        )
        if path:
            count = packet_logger.export_csv(path)
            messagebox.showinfo("匯出成功", f"已成功匯出 {count} 筆封包紀錄至:\n{os.path.basename(path)}")

    def t3_on_new_packet(self, rec):
        idx = rec["index"]
        self.t3_records_map[idx] = rec

        direction = rec.get("direction", "?")
        scsi_st_str = rec.get("scsi_status", "")
        tag = "tag_in" if direction == "IN" else ("tag_out" if direction == "OUT" else "tag_none")
        if "CHECK CONDITION" in scsi_st_str or "0x02" in scsi_st_str:
            tag = "tag_error"

        item_id = self.t3_tree.insert(
            "", tk.END, iid=str(idx),
            values=(
                rec["index"],
                rec["timestamp"],
                rec["drive"],
                rec["direction"],
                rec["cmd_name"],
                rec["data_len"],
                rec["scsi_status"],
                rec["elapsed_ms"]
            ),
            tags=(tag,)
        )

        total_count = len(self.t3_records_map)
        self.t3_count_lbl.config(text=f"總封包數: {total_count}")

        if self.t3_auto_scroll.get():
            self.t3_tree.see(item_id)

    def t3_on_select_packet(self, event):
        selected = self.t3_tree.selection()
        if not selected:
            return
        idx = int(selected[0])
        rec = self.t3_records_map.get(idx)
        if not rec:
            return

        self.t3_selected_record = rec

        # 1. 顯示 CDB
        self.t3_cdb_txt.delete(1.0, tk.END)
        self.t3_cdb_txt.insert(tk.END, rec.get("cdb_hex", "(none)"))

        # 2. 顯示 Sense Data
        self.t3_sense_txt.delete(1.0, tk.END)
        self.t3_sense_txt.insert(tk.END, rec.get("sense_str", "(none)"))

        # 3. 顯示摘要狀態
        self.t3_summary_lbl.config(
            text=f"📌 封包 #{rec['index']}   |   時間: {rec['timestamp']}   |   磁碟: {rec['drive']}   |   方向: {rec.get('direction', '?')}   |   長度: {rec.get('data_len', 0)} Bytes   |   狀態: {rec.get('scsi_status', '')}   |   延遲: {rec['elapsed_ms']} ms",
            fg="#0D47A1"
        )

        # 4. 顯示 Payload Hexdump
        self.t3_dump_txt.delete(1.0, tk.END)
        raw_payload = rec.get("raw_payload", b"")
        if raw_payload:
            self.t3_dump_txt.insert(tk.END, hexdump(raw_payload))
        else:
            self.t3_dump_txt.insert(tk.END, "(No Payload Data)")

    def t3_save_selected_payload(self):
        if not self.t3_selected_record:
            return messagebox.showwarning("警告", "請先選取一筆封包！")
        raw_payload = self.t3_selected_record.get("raw_payload", b"")
        if not raw_payload:
            return messagebox.showwarning("警告", "所選取的封包沒有 Payload 資料！")
        path = filedialog.asksaveasfilename(
            defaultextension=".bin",
            filetypes=[("Binary Files (*.bin)", "*.bin"), ("All Files", "*.*")],
            title="儲存 Payload 資料"
        )
        if path:
            with open(path, "wb") as f:
                f.write(raw_payload)
            messagebox.showinfo("存檔成功", f"已成功儲存 {len(raw_payload)} Bytes 到 {os.path.basename(path)}")

    # ==========================================
    # Tab 4: MCU 韌體更新 (Firmware Update)
    # ==========================================
    def init_tab4_fw_update(self):
        self.fw_engine = FirmwareUpdateEngine()
        self.t4_cdb_entries = []

        # --- 區域 1：韌體分塊資料夾選擇 ---
        dir_frame = tk.LabelFrame(self.tab4, text="📁 韌體分塊資料夾 (Firmware Chunks Directory)", padx=10, pady=6)
        dir_frame.pack(fill=tk.X, padx=10, pady=(8, 4))

        dir_row = tk.Frame(dir_frame)
        dir_row.pack(fill=tk.X)
        tk.Label(dir_row, text="路徑:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.t4_dir_entry = tk.Entry(dir_row, width=60, font=("Consolas", 9))
        self.t4_dir_entry.pack(side=tk.LEFT, padx=(4, 8), fill=tk.X, expand=True)
        tk.Button(
            dir_row, text="📂 瀏覽資料夾 (Browse)", command=self.t4_browse_folder,
            bg="#E1F5FE", font=("Arial", 9, "bold")
        ).pack(side=tk.LEFT)

        self.t4_dir_info_lbl = tk.Label(
            dir_frame, text="尚未載入任何韌體檔案", fg="#757575", font=("Arial", 9), anchor="w"
        )
        self.t4_dir_info_lbl.pack(fill=tk.X, pady=(4, 0))

        # --- 區域 2：CDB 模板設定 ---
        cdb_frame = tk.LabelFrame(self.tab4, text="⚙️ CDB 模板與通訊設定", padx=10, pady=6)
        cdb_frame.pack(fill=tk.X, padx=10, pady=4)

        cdb_btn_row = tk.Frame(cdb_frame)
        cdb_btn_row.pack(fill=tk.X, pady=(0, 4))
        tk.Button(cdb_btn_row, text="📂 載入 CDB .bin", command=self.t4_load_cdb_bin, bg="#E1F5FE").pack(side=tk.LEFT)
        tk.Button(cdb_btn_row, text="清空 CDB", command=self.t4_clear_cdb).pack(side=tk.LEFT, padx=5)

        cdb_matrix = tk.Frame(cdb_frame)
        cdb_matrix.pack(pady=2)
        for i in range(16):
            r, c = i // 8, i % 8
            cf = tk.Frame(cdb_matrix, padx=2, pady=2)
            cf.grid(row=r, column=c)
            lbl_text = f"B{i:02d}"
            if i == 3:
                lbl_text = "B03 (Addr H)"
            elif i == 4:
                lbl_text = "B04 (Addr L)"
            tk.Label(cf, text=lbl_text, font=("Arial", 7), fg="gray").pack()
            e = tk.Entry(cf, width=4, font=("Consolas", 12, "bold"), justify='center')
            e.insert(0, "00")
            e.pack()
            self.t4_cdb_entries.append(e)

        addr_row = tk.Frame(cdb_frame)
        addr_row.pack(fill=tk.X, pady=(4, 0))
        tk.Label(addr_row, text="起始 Address (Hex):", font=("Arial", 9)).pack(side=tk.LEFT)
        self.t4_start_addr_entry = tk.Entry(addr_row, width=8, font=("Consolas", 10, "bold"), justify='center')
        self.t4_start_addr_entry.insert(0, "0000")
        self.t4_start_addr_entry.pack(side=tk.LEFT, padx=(4, 15))
        tk.Label(addr_row, text="每次遞增: 0x80 (128B)  |  Address 對應: CDB[3]=High Byte, CDB[4]=Low Byte",
                 font=("Arial", 9), fg="#616161").pack(side=tk.LEFT)

        # --- 區域 3：執行控制與即時進度 ---
        ctrl_frame = tk.LabelFrame(self.tab4, text="🚀 執行控制與即時進度", padx=10, pady=6)
        ctrl_frame.pack(fill=tk.X, padx=10, pady=4)

        btn_row = tk.Frame(ctrl_frame)
        btn_row.pack(fill=tk.X, pady=(0, 4))
        self.t4_start_btn = tk.Button(
            btn_row, text="▶ 開始韌體更新 (Start Update)", command=self.t4_start_update,
            bg="#2E7D32", fg="white", font=("Arial", 10, "bold"), width=28
        )
        self.t4_start_btn.pack(side=tk.LEFT)
        self.t4_abort_btn = tk.Button(
            btn_row, text="⏹ 中止更新 (Abort)", command=self.t4_abort_update,
            bg="#D32F2F", fg="white", font=("Arial", 10, "bold"), width=18, state=tk.DISABLED
        )
        self.t4_abort_btn.pack(side=tk.LEFT, padx=10)

        self.t4_progress = ttk.Progressbar(ctrl_frame, mode='determinate', length=600)
        self.t4_progress.pack(fill=tk.X, pady=(0, 4))

        self.t4_status_lbl = tk.Label(
            ctrl_frame, text="就緒 — 請載入韌體資料夾與設定 CDB 模板後開始",
            fg="#0D47A1", font=("Arial", 9, "bold"), anchor="w"
        )
        self.t4_status_lbl.pack(fill=tk.X)

        # --- 區域 4：更新日誌 Terminal ---
        log_frame = tk.LabelFrame(self.tab4, text="📜 更新日誌 (FW Update Log)", padx=10, pady=6)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 8))

        log_inner = tk.Frame(log_frame)
        log_inner.pack(fill=tk.BOTH, expand=True)
        log_sb_y = ttk.Scrollbar(log_inner, orient=tk.VERTICAL)
        log_sb_x = ttk.Scrollbar(log_inner, orient=tk.HORIZONTAL)
        self.t4_log_txt = tk.Text(
            log_inner, font=("Consolas", 9), bg="#1E1E1E", fg="#A7F3D0",
            wrap=tk.NONE, yscrollcommand=log_sb_y.set, xscrollcommand=log_sb_x.set
        )
        self.t4_log_txt.grid(row=0, column=0, sticky="nsew")
        log_sb_y.grid(row=0, column=1, sticky="ns")
        log_sb_x.grid(row=1, column=0, sticky="ew")
        log_inner.grid_rowconfigure(0, weight=1)
        log_inner.grid_columnconfigure(0, weight=1)
        log_sb_y.config(command=self.t4_log_txt.yview)
        log_sb_x.config(command=self.t4_log_txt.xview)

    # --- Tab 4 事件處理 ---
    def t4_log(self, msg):
        """寫入 Tab 4 Terminal Log (thread-safe via root.after)"""
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.t4_log_txt.insert(tk.END, f"[{ts}] {msg}\n")
        self.t4_log_txt.see(tk.END)

    def t4_browse_folder(self):
        folder = filedialog.askdirectory(title="選擇韌體分塊資料夾")
        if not folder:
            return
        self.t4_dir_entry.delete(0, tk.END)
        self.t4_dir_entry.insert(0, folder)
        self._t4_load_chunks(folder)

    def _t4_load_chunks(self, folder):
        """載入韌體分塊並更新統計"""
        try:
            start_hex = self.t4_start_addr_entry.get().strip()
            self.fw_engine.start_address = int(start_hex, 16)
        except ValueError:
            self.fw_engine.start_address = 0x0000

        ok, msg = self.fw_engine.load_chunks(folder)
        if ok:
            self.t4_dir_info_lbl.config(text=msg, fg="#1B5E20")
            self.t4_log(msg)
        else:
            self.t4_dir_info_lbl.config(text=msg, fg="#B71C1C")
            self.t4_log(f"❌ {msg}")

    def t4_load_cdb_bin(self):
        path = filedialog.askopenfilename(
            filetypes=[("Binary Files", "*.bin"), ("All Files", "*.*")],
            title="載入 CDB 模板 (.bin)"
        )
        if not path:
            return
        with open(path, 'rb') as f:
            raw = f.read(16)
        for i, b in enumerate(raw[:16]):
            self.t4_cdb_entries[i].delete(0, tk.END)
            self.t4_cdb_entries[i].insert(0, f"{b:02X}")
        self.t4_log(f"已載入 CDB 模板: {os.path.basename(path)} ({len(raw)} Bytes)")

    def t4_clear_cdb(self):
        for e in self.t4_cdb_entries:
            e.delete(0, tk.END)
            e.insert(0, "00")

    def _t4_read_cdb_from_entries(self):
        """從 16 格 Entry 讀取 CDB bytes"""
        cdb = []
        for e in self.t4_cdb_entries:
            try:
                cdb.append(int(e.get().strip(), 16))
            except ValueError:
                cdb.append(0x00)
        return cdb

    def t4_start_update(self):
        """開始韌體更新"""
        # 驗證磁碟選擇
        drive_str = self.drive_combo.get()
        if not drive_str:
            return messagebox.showwarning("警告", "請先選取目標磁碟！")

        try:
            drive_num = int(drive_str.split("PhysicalDrive")[-1].split()[0].split("-")[0].strip())
        except (ValueError, IndexError):
            return messagebox.showwarning("錯誤", f"無法解析磁碟編號: {drive_str}")

        # 驗證韌體檔案
        if not self.fw_engine.chunks:
            folder = self.t4_dir_entry.get().strip()
            if folder:
                self._t4_load_chunks(folder)
            if not self.fw_engine.chunks:
                return messagebox.showwarning("警告", "請先載入韌體分塊資料夾！")

        # 讀取 CDB 模板
        cdb = self._t4_read_cdb_from_entries()
        self.fw_engine.load_cdb_template(cdb)

        # 讀取起始 Address
        try:
            start_hex = self.t4_start_addr_entry.get().strip()
            self.fw_engine.start_address = int(start_hex, 16)
        except ValueError:
            self.fw_engine.start_address = 0x0000

        # 確認
        total = len(self.fw_engine.chunks)
        end_addr = self.fw_engine.start_address + total * ADDR_INCREMENT
        if not messagebox.askyesno(
            "確認開始韌體更新",
            f"目標磁碟: {drive_str}\n"
            f"韌體分塊: {total} 個 ({total * CHUNK_SIZE:,} Bytes)\n"
            f"Address 範圍: 0x{self.fw_engine.start_address:04X} → 0x{end_addr - ADDR_INCREMENT:04X}\n"
            f"CDB 模板: {' '.join(f'{b:02X}' for b in cdb)}\n\n"
            f"確定開始更新？此操作無法還原！"
        ):
            return

        # 切換按鈕狀態
        self.t4_start_btn.config(state=tk.DISABLED)
        self.t4_abort_btn.config(state=tk.NORMAL)
        self.t4_progress['value'] = 0
        self.t4_progress['maximum'] = total

        self.t4_log("=" * 60)
        self.t4_log(f"韌體更新啟動 — 目標: {drive_str}")
        self.t4_log(f"分塊數: {total}, Address: 0x{self.fw_engine.start_address:04X} → 0x{end_addr - ADDR_INCREMENT:04X}")
        self.t4_log("=" * 60)

        # 啟動背景執行緒
        self.fw_engine.start(
            drive_num,
            progress_cb=lambda cur, tot, addr: self.root.after(0, self._t4_on_progress, cur, tot, addr),
            log_cb=lambda msg: self.root.after(0, self.t4_log, msg),
            done_cb=lambda ok, msg: self.root.after(0, self._t4_on_done, ok, msg),
        )

    def t4_abort_update(self):
        """中止韌體更新"""
        self.fw_engine.abort()
        self.t4_abort_btn.config(state=tk.DISABLED)
        self.t4_log("⚠️ 正在中止更新...")

    def _t4_on_progress(self, current, total, address):
        """進度回呼 (GUI thread)"""
        self.t4_progress['value'] = current
        pct = current / total * 100 if total > 0 else 0
        self.t4_status_lbl.config(
            text=f"進度: {current} / {total} ({pct:.1f}%)  |  目前 Address: 0x{address:04X}",
            fg="#0D47A1"
        )

    def _t4_on_done(self, success, msg):
        """完成回呼 (GUI thread)"""
        self.t4_start_btn.config(state=tk.NORMAL)
        self.t4_abort_btn.config(state=tk.DISABLED)
        if success:
            self.t4_status_lbl.config(text=msg, fg="#1B5E20")
            self.t4_progress['value'] = self.t4_progress['maximum']
            messagebox.showinfo("韌體更新完成", msg)
        else:
            self.t4_status_lbl.config(text=msg, fg="#B71C1C")
            messagebox.showerror("韌體更新失敗", msg)

if __name__ == "__main__":
    if ctypes.windll.shell32.IsUserAnAdmin():
        root = tk.Tk()
        app = ScsiToolGUI(root)
        root.mainloop()
    else:
        params = None if getattr(sys, 'frozen', False) else f'"{__file__}"'
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        sys.exit()
