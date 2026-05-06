import sys
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import os

# --- Windows API 常數與結構 ---
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2

IOCTL_SCSI_PASS_THROUGH_DIRECT = 0x4D014
SCSI_IOCTL_DATA_OUT = 0
SCSI_IOCTL_DATA_IN = 1
SCSI_IOCTL_DATA_UNSPECIFIED = 2

FSCTL_LOCK_VOLUME = 0x00090018
FSCTL_UNLOCK_VOLUME = 0x0009001C

class SCSI_PASS_THROUGH_DIRECT(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT), ("ScsiStatus", ctypes.c_ubyte),
        ("PathId", ctypes.c_ubyte), ("TargetId", ctypes.c_ubyte),
        ("Lun", ctypes.c_ubyte), ("CdbLength", ctypes.c_ubyte),
        ("SenseInfoLength", ctypes.c_ubyte), ("DataIn", ctypes.c_ubyte),
        ("DataTransferLength", wintypes.ULONG), ("TimeOutValue", wintypes.ULONG),
        ("DataBuffer", ctypes.c_void_p), ("SenseInfoOffset", wintypes.ULONG),
        ("Cdb", ctypes.c_ubyte * 16)
    ]

class SENSE_DATA_BUFFER(ctypes.Structure):
    _fields_ = [("data", ctypes.c_ubyte * 24)]

# --- 輔助函數 ---
def get_physical_drives():
    drives = []
    try:
        cmd = ['powershell', '-NoProfile', '-Command', 
               "Get-CimInstance Win32_DiskDrive | ForEach-Object { '{0}:::{1}' -f $_.Index, $_.Model }"]
        result = subprocess.run(cmd, capture_output=True, text=True, creationflags=0x08000000)
        for line in result.stdout.splitlines():
            if ":::" in line:
                idx, model = line.split(":::", 1)
                drives.append(f"PhysicalDrive{idx.strip()} - {model.strip()}")
    except: pass
    return drives if drives else [f"PhysicalDrive{i}" for i in range(8)]

def hexdump(src, length=16):
    if not src: return ""
    result = []
    for i in range(0, len(src), length):
        chunk = src[i:i+length]
        hex_str = ' '.join(f'{b:02X}' for b in chunk)
        ascii_str = ''.join(chr(b) if 0x20 <= b < 0x7F else '.' for b in chunk)
        result.append(f"{i:04X}   {hex_str:<{length*3}}   {ascii_str}")
    return '\n'.join(result)

# --- 裝置控制 (Open / Close / Lock) ---
def open_drive(physical_drive_num):
    drive_path = f"\\\\.\\PhysicalDrive{physical_drive_num}"
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateFileW(drive_path, GENERIC_READ | GENERIC_WRITE, 
                                  FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
    if handle == -1: raise PermissionError(f"Open Failed: {kernel32.GetLastError()}")
    return handle

def close_drive(handle):
    ctypes.windll.kernel32.CloseHandle(handle)

def lock_drive(handle):
    bytes_returned = wintypes.DWORD()
    kernel32 = ctypes.windll.kernel32
    result = kernel32.DeviceIoControl(handle, FSCTL_LOCK_VOLUME, None, 0, None, 0, ctypes.byref(bytes_returned), None)
    err_code = kernel32.GetLastError() if not result else 0
    return result != 0, err_code

def unlock_drive(handle):
    bytes_returned = wintypes.DWORD()
    ctypes.windll.kernel32.DeviceIoControl(handle, FSCTL_UNLOCK_VOLUME, None, 0, None, 0, ctypes.byref(bytes_returned), None)

# --- 核心通訊 ---
def send_scsi_command(handle, cdb_bytes, data_transfer_length, direction, out_data_bytes=None):
    sense_buffer = SENSE_DATA_BUFFER()
    
    if direction == SCSI_IOCTL_DATA_UNSPECIFIED:
        data_transfer_length = 0
        data_buffer = None
    elif direction == SCSI_IOCTL_DATA_OUT and out_data_bytes:
        data_buffer = (ctypes.c_ubyte * data_transfer_length)(*(out_data_bytes[:data_transfer_length]))
    else:
        data_buffer = (ctypes.c_ubyte * data_transfer_length)()

    class SPTD_WITH_SENSE(ctypes.Structure):
        _fields_ = [("sptd", SCSI_PASS_THROUGH_DIRECT), ("sense", SENSE_DATA_BUFFER)]

    combined = SPTD_WITH_SENSE()
    combined.sptd.Length = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT)
    combined.sptd.CdbLength = len(cdb_bytes)
    combined.sptd.DataIn = direction
    combined.sptd.DataTransferLength = data_transfer_length
    combined.sptd.TimeOutValue = 10 
    
    if data_transfer_length > 0 and data_buffer is not None:
        combined.sptd.DataBuffer = ctypes.cast(ctypes.pointer(data_buffer), ctypes.c_void_p)
    else:
        combined.sptd.DataBuffer = None

    combined.sptd.SenseInfoLength = ctypes.sizeof(sense_buffer)
    combined.sptd.SenseInfoOffset = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT)
    for i in range(len(cdb_bytes)): combined.sptd.Cdb[i] = cdb_bytes[i]

    bytes_returned = wintypes.DWORD()
    kernel32 = ctypes.windll.kernel32
    result = kernel32.DeviceIoControl(handle, IOCTL_SCSI_PASS_THROUGH_DIRECT, 
                                      ctypes.byref(combined), ctypes.sizeof(combined),
                                      ctypes.byref(combined), ctypes.sizeof(combined), 
                                      ctypes.byref(bytes_returned), None)
    
    if not result: raise OSError(f"IOCTL Failed: {kernel32.GetLastError()}")
    
    returned_data = bytes(data_buffer) if data_buffer else b""
    return combined.sptd.ScsiStatus, returned_data, bytes(combined.sense.data)

# --- GUI 主程式 ---
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
        
        # 下拉選單
        self.drive_combo = ttk.Combobox(header_frame, state="readonly", width=60)
        self.drive_combo.pack(side=tk.LEFT, padx=10)
        
        # 新增: 重新掃描設備按鈕
        tk.Button(header_frame, text="🔄 Rescan", command=self.rescan_drives, bg="#E0E0E0", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        
        # 初始化掃描
        self.rescan_drives()

    def rescan_drives(self):
        """重新掃描系統實體磁碟並更新下拉選單"""
        current_selection = self.drive_combo.get()
        drives = get_physical_drives()
        self.drive_combo['values'] = drives
        
        if drives:
            # 如果原本選的磁碟還在，就保留原選項；否則選第一個
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
            # 移除自動跳格綁定，讓使用者可用 Tab 鍵正常切換
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
            # 修正: 加上對 lbl 的更新，讓載入狀態有反饋
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
            st, data, sense = send_scsi_command(handle, cdb, length, self.t1_dir_var.get(), out_b)
            
            self.t1_log(f"Status: 0x{st:02X}")
            if self.t1_dir_var.get() == SCSI_IOCTL_DATA_IN and length > 0:
                if st == 0: self.t1_last_in_data = data
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
        self.t2_last_in_data = None
        self.t2_loaded_data_bin = None 

        ctrl_frame = tk.Frame(self.tab2, pady=10)
        ctrl_frame.pack(fill=tk.X, padx=10)

        tk.Checkbutton(ctrl_frame, text="AP_KEY (解鎖)", variable=self.t2_ap_key_var, font=("Arial", 10, "bold"), fg="#D32F2F").pack(side=tk.LEFT, padx=10)
        
        tk.Checkbutton(ctrl_frame, text="Lock Device (防干擾鎖定)", variable=self.t2_lock_var, font=("Arial", 10, "bold"), fg="#E65100").pack(side=tk.LEFT, padx=5)

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
                # 移除自動跳格綁定
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
                
                if len(data) >= 44:
                    length_bytes = data[40:44]
                    transfer_length = int.from_bytes(length_bytes, byteorder='little') * 4
                    if transfer_length > 0:
                        self.t2_len_entry.delete(0, tk.END)
                        self.t2_len_entry.insert(0, str(transfer_length))
                        self.t2_log(f"[Auto-Parse] 從 Offset 40-43 擷取長度並乘以 4: {transfer_length} Bytes")

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

            # ==========================================
            # Handle 建立與防干擾鎖定狀態顯示
            # ==========================================
            handle = open_drive(drive_num)
            
            if lock_enabled:
                self.t2_log("================= LOCK STATUS ================")
                is_locked, err_code = lock_drive(handle)
                if is_locked:
                    self.t2_log("[ O K ] 實體磁碟已成功獨佔鎖定 (FSCTL_LOCK_VOLUME)")
                    self.t2_log("        目前的 VUC 序列將受到嚴格的防干擾保護。")
                else:
                    self.t2_log(f"[WARNING] 鎖定失敗！(Error Code: {err_code})")
                    self.t2_log("          Windows 系統或其他程式可能會在背景偷下 Read CMD！")
                    self.t2_log("          💡 專家提示：若持續受到干擾，請至「電腦管理 -> 磁碟管理」")
                    self.t2_log("          將該磁碟設為「離線 (Offline)」，即可徹底阻斷 Windows 輪詢。")
                self.t2_log("==============================================\n")

            # ==========================================
            # 1. AP_KEY 解鎖序列
            # ==========================================
            if ap_key_enabled:
                self.t2_log("==========================================")
                self.t2_log("[AP_KEY Auth] 開始執行特權解鎖序列 (3 cmds)...")
                
                ap_key_path = os.path.join("AP_Key", "ap_key.bin")
                if not os.path.exists(ap_key_path):
                    self.t2_log(f"[Error] 找不到金鑰檔案！請確保路徑正確: {ap_key_path}")
                    return
                
                with open(ap_key_path, "rb") as f:
                    ap_key_data = f.read(512)
                if len(ap_key_data) < 512:
                    ap_key_data = ap_key_data.ljust(512, b'\x00')

                cdb1 = [0x06, 0xfe, 0xc0, 0x00, 0x01, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
                self.t2_log(" -> [AP_KEY 1/3] 發送 Data-Out (Length: 512)")
                st1, _, _ = send_scsi_command(handle, cdb1, 512, SCSI_IOCTL_DATA_OUT, list(ap_key_data))
                if st1 != 0: return self.t2_log(f"   [Error] 序列 1 失敗！Status: 0x{st1:02X}")

                cdb2 = [0x06, 0xfe, 0xc1, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
                self.t2_log(" -> [AP_KEY 2/3] 發送 No-Data (Length: 0)")
                st2, _, _ = send_scsi_command(handle, cdb2, 0, SCSI_IOCTL_DATA_UNSPECIFIED, None)
                if st2 != 0: return self.t2_log(f"   [Error] 序列 2 失敗！Status: 0x{st2:02X}")

                cdb3 = [0x06, 0xfe, 0xc3, 0x00, 0x01, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
                self.t2_log(" -> [AP_KEY 3/3] 發送 Data-In (Length: 512)")
                st3, _, _ = send_scsi_command(handle, cdb3, 512, SCSI_IOCTL_DATA_IN, None)
                if st3 != 0: return self.t2_log(f"   [Error] 序列 3 失敗！Status: 0x{st3:02X}")

                self.t2_log("[AP_KEY Auth] 解鎖成功，硬碟進入特權模式！")
                self.t2_log("==========================================\n")
            
            if ap_key_enabled and is_matrix_empty:
                self.t2_log("[系統提示] 偵測到 64-Byte 矩陣全為 0，且 AP_KEY 已勾選。")
                self.t2_log("=> 僅執行 AP_KEY 解鎖序列，跳過後續 VUC 指令。")
                return

            # ==========================================
            # 2. VUC 主體指令序列 (背景執行 VUC 1 & 3, 僅顯示 VUC 2)
            # ==========================================
            self.t2_log("==========================================")
            self.t2_log(f"[VUC Sequence] 背景執行 64-Byte VUC 配置序列...")
            
            vuc_cdb1 = [0x06, 0xfe, 0xc0, 0x00, 0x01, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
            vuc1_payload = cmd_64_bytes.copy()
            if len(vuc1_payload) < 512:
                vuc1_payload += [0] * (512 - len(vuc1_payload))
                
            st_vuc1, _, _ = send_scsi_command(handle, vuc_cdb1, 512, SCSI_IOCTL_DATA_OUT, vuc1_payload)
            if st_vuc1 != 0: return self.t2_log(f"   [Error] VUC 1 (配置指令) 失敗！Status: 0x{st_vuc1:02X}")

            sectors = length // 512 if length > 0 else 0
            b3 = (sectors >> 8) & 0xFF
            b4 = sectors & 0xFF
            
            bytes_len = sectors * 512
            b5 = (bytes_len >> 24) & 0xFF
            b6 = (bytes_len >> 16) & 0xFF
            b7 = (bytes_len >> 8) & 0xFF
            b8 = bytes_len & 0xFF

            if direction == SCSI_IOCTL_DATA_IN:
                b2 = 0xc2
            else:
                b2 = 0xc1
                
            vuc_cdb2 = [0x06, 0xfe, b2, b3, b4, b5, b6, b7, b8, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
            dir_str2 = "DATA IN" if direction == SCSI_IOCTL_DATA_IN else "DATA OUT" if direction == SCSI_IOCTL_DATA_OUT else "NO DATA"
            self.t2_log(f" -> 發送主要指令 ({dir_str2})")
            self.t2_log(f"    (OpCode: 0x{b2:02X}, Sectors: 0x{sectors:04X} -> Byte3: 0x{b3:02X}, Byte4: 0x{b4:02X})")
            self.t2_log(f"    (Bytes Length: 0x{bytes_len:08X} -> Byte5~8: 0x{b5:02X} 0x{b6:02X} 0x{b7:02X} 0x{b8:02X})")
            
            out_b = None
            if direction == SCSI_IOCTL_DATA_OUT:
                out_b = list(self.t2_loaded_data_bin) if self.t2_loaded_data_bin else [0]*length
                if len(out_b) < length: out_b += [0]*(length-len(out_b))
                out_b = out_b[:length]

            st_vuc2, data_vuc2, _ = send_scsi_command(handle, vuc_cdb2, length, direction, out_b)
            if st_vuc2 != 0: return self.t2_log(f"   [Error] VUC 2 (資料傳輸) 失敗！Status: 0x{st_vuc2:02X}")
            
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
            st_vuc3, data_vuc3, _ = send_scsi_command(handle, vuc_cdb3, 512, SCSI_IOCTL_DATA_IN, None)
            if st_vuc3 != 0: return self.t2_log(f"   [Error] VUC 3 (狀態讀取) 失敗！Status: 0x{st_vuc3:02X}")
            
            self.t2_log("[VUC Sequence] 全部指令序列執行成功！")
            self.t2_log("==========================================")

        except Exception as e:
            self.t2_log(f"[Exception] 發生未預期錯誤: {str(e)}")
        finally:
            if handle:
                if lock_enabled:
                    unlock_drive(handle)
                close_drive(handle)

if __name__ == "__main__":
    if ctypes.windll.shell32.IsUserAnAdmin():
        root = tk.Tk()
        app = ScsiToolGUI(root)
        root.mainloop()
    else:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{__file__}"', None, 1)
        sys.exit()
