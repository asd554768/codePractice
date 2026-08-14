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
        
        self.notebook.add(self.tab1, text=" SCSI Command (16-Byte) ")
        self.notebook.add(self.tab2, text=" Vendor/Ext Command (64-Byte VUC) ")
        
        self.init_tab1_scsi()
        self.init_tab2_64byte()

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
        sb = tk.Scrollbar(out_f)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.t1_out = tk.Text(out_f, font=("Consolas", 10), bg="#1E1E1E", fg="#D4D4D4", yscrollcommand=sb.set)
        self.t1_out.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=self.t1_out.yview)

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
        sb = tk.Scrollbar(out_f)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.t2_out = tk.Text(out_f, font=("Consolas", 10), bg="#000000", fg="#00FF00", yscrollcommand=sb.set)
        self.t2_out.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=self.t2_out.yview)

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

if __name__ == "__main__":
    if ctypes.windll.shell32.IsUserAnAdmin():
        root = tk.Tk()
        app = ScsiToolGUI(root)
        root.mainloop()
    else:
        params = None if getattr(sys, 'frozen', False) else f'"{__file__}"'
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        sys.exit()
