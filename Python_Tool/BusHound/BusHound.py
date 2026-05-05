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

def send_scsi_command(physical_drive_num, cdb_bytes, data_transfer_length, direction, out_data_bytes=None):
    drive_path = f"\\\\.\\PhysicalDrive{physical_drive_num}"
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateFileW(drive_path, GENERIC_READ | GENERIC_WRITE, 
                                  FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
    if handle == -1: raise PermissionError(f"Open Failed: {kernel32.GetLastError()}")

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
    result = kernel32.DeviceIoControl(handle, IOCTL_SCSI_PASS_THROUGH_DIRECT, 
                                      ctypes.byref(combined), ctypes.sizeof(combined),
                                      ctypes.byref(combined), ctypes.sizeof(combined), 
                                      ctypes.byref(bytes_returned), None)
    kernel32.CloseHandle(handle)
    
    if not result: raise OSError(f"IOCTL Failed: {kernel32.GetLastError()}")
    
    returned_data = bytes(data_buffer) if data_buffer else b""
    return combined.sptd.ScsiStatus, returned_data, bytes(combined.sense.data)

# --- GUI 主程式 ---
class ScsiToolGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Python Storage Debug Tool (Multi-Tab Edition)")
        self.root.geometry("900x850")
        
        # 建立共用的頂部控制區 (選擇磁碟)
        self.create_global_header()
        
        # 建立 Notebook 分頁系統
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 建立兩個分頁
        self.tab1 = ttk.Frame(self.notebook)
        self.tab2 = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab1, text=" SCSI Command (16-Byte) ")
        self.notebook.add(self.tab2, text=" Vendor/Ext Command (64-Byte) ")
        
        # 初始化兩個分頁的內容
        self.init_tab1_scsi()
        self.init_tab2_64byte()

    def create_global_header(self):
        header_frame = tk.LabelFrame(self.root, text="Global Settings", padx=10, pady=5)
        header_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(header_frame, text="目標磁碟 (Target Drive):").pack(side=tk.LEFT)
        self.drive_combo = ttk.Combobox(header_frame, values=get_physical_drives(), state="readonly", width=60)
        if self.drive_combo['values']: self.drive_combo.current(0)
        self.drive_combo.pack(side=tk.LEFT, padx=10)

    # ==========================================
    # Tab 1: 原本的 16-Byte SCSI 工具
    # ==========================================
    def init_tab1_scsi(self):
        self.t1_dir_var = tk.IntVar(value=SCSI_IOCTL_DATA_IN)
        self.t1_loaded_data_bin = None
        self.t1_cdb_entries = []
        self.t1_last_in_data = None

        # 方向與 CDB 區域
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
            e.bind('<KeyRelease>', lambda ev, idx=i: self.t1_auto_focus(ev, idx))
            self.t1_cdb_entries.append(e)

        # Buffer 區域
        buf_frame = tk.LabelFrame(self.tab1, text="Data Buffer", padx=10, pady=5)
        buf_frame.pack(fill=tk.X, pady=5)
        tk.Label(buf_frame, text="傳輸長度 (Bytes):").pack(side=tk.LEFT)
        self.t1_len_entry = tk.Entry(buf_frame, width=15)
        self.t1_len_entry.insert(0, "36")
        self.t1_len_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(buf_frame, text="載入 Data Out .bin", command=self.t1_load_data).pack(side=tk.LEFT, padx=10)
        self.t1_data_lbl = tk.Label(buf_frame, text="未選擇檔案", fg="gray")
        self.t1_data_lbl.pack(side=tk.LEFT)

        # 執行與輸出
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

    # Tab 1 Methods (簡化保留，維持功能)
    def t1_auto_focus(self, ev, idx):
        if len(self.t1_cdb_entries[idx].get()) >= 2 and idx < 15:
            self.t1_cdb_entries[idx+1].focus_set()
            self.t1_cdb_entries[idx+1].selection_range(0, tk.END)
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
        try:
            dnum = int(self.drive_combo.get().split(" ")[0].replace("PhysicalDrive", ""))
            cdb = [int(e.get() or "00", 16) for e in self.t1_cdb_entries]
            length = int(self.t1_len_entry.get() or "0") if self.t1_dir_var.get() != SCSI_IOCTL_DATA_UNSPECIFIED else 0
            out_b = list(self.t1_loaded_data_bin) if self.t1_loaded_data_bin else [0]*length
            
            st, data, sense = send_scsi_command(dnum, cdb, length, self.t1_dir_var.get(), out_b)
            self.t1_log(f"Status: 0x{st:02X}")
            if self.t1_dir_var.get() == SCSI_IOCTL_DATA_IN and length > 0:
                if st == 0: self.t1_last_in_data = data
                self.t1_log(hexdump(data))
        except Exception as e: self.t1_log(f"Error: {e}")

    # ==========================================
    # Tab 2: 全新 64-Byte 工具區塊
    # ==========================================
    def init_tab2_64byte(self):
        self.t2_dir_var = tk.IntVar(value=SCSI_IOCTL_DATA_IN)
        self.t2_entries = []
        self.t2_ap_key_var = tk.BooleanVar(value=False)
        self.t2_last_in_data = None
        self.t2_loaded_data_bin = None

        # 頂部控制列 (AP_KEY, 方向, 長度)
        ctrl_frame = tk.Frame(self.tab2, pady=10)
        ctrl_frame.pack(fill=tk.X, padx=10)

        # 1. AP_KEY Checkbox
        tk.Checkbutton(ctrl_frame, text="AP_KEY (啟用特權)", variable=self.t2_ap_key_var, font=("Arial", 10, "bold"), fg="#D32F2F").pack(side=tk.LEFT, padx=10)
        
        # 2. 傳輸方向
        ttk.Separator(ctrl_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        tk.Radiobutton(ctrl_frame, text="Data In", variable=self.t2_dir_var, value=SCSI_IOCTL_DATA_IN).pack(side=tk.LEFT)
        tk.Radiobutton(ctrl_frame, text="Data Out", variable=self.t2_dir_var, value=SCSI_IOCTL_DATA_OUT).pack(side=tk.LEFT)
        tk.Radiobutton(ctrl_frame, text="No Data", variable=self.t2_dir_var, value=SCSI_IOCTL_DATA_UNSPECIFIED).pack(side=tk.LEFT)
        
        # 3. 傳輸長度
        ttk.Separator(ctrl_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        tk.Label(ctrl_frame, text="Length:").pack(side=tk.LEFT)
        self.t2_len_entry = tk.Entry(ctrl_frame, width=10)
        self.t2_len_entry.insert(0, "0")
        self.t2_len_entry.pack(side=tk.LEFT, padx=5)

        # 4. 64-Byte 矩陣區塊
        grid_frame = tk.LabelFrame(self.tab2, text="Command Bytes (64-Byte Payload / CDB)", padx=10, pady=10)
        grid_frame.pack(fill=tk.X, padx=10, pady=5)

        btn_box = tk.Frame(grid_frame)
        btn_box.pack(fill=tk.X, pady=5)
        tk.Button(btn_box, text="載入 64-Byte .bin", command=self.t2_load_64b_bin, bg="#E8EAF6").pack(side=tk.LEFT)
        tk.Button(btn_box, text="清空矩陣", command=self.t2_clear_grid).pack(side=tk.LEFT, padx=5)

        matrix = tk.Frame(grid_frame)
        matrix.pack()
        
        # 畫出行標題 (00 ~ 0F)
        for col in range(16):
            tk.Label(matrix, text=f"{col:02X}", fg="#3F51B5", font=("Arial", 8, "bold")).grid(row=0, column=col+1)
            
        # 畫出 4x16 矩陣
        for row in range(4):
            # 列標題 (00:, 10:, 20:, 30:)
            tk.Label(matrix, text=f"{row*16:02X}:", fg="#3F51B5", font=("Arial", 8, "bold")).grid(row=row+1, column=0, padx=5)
            for col in range(16):
                idx = row * 16 + col
                e = tk.Entry(matrix, width=3, font=("Consolas", 12), justify='center')
                e.insert(0, "00")
                e.grid(row=row+1, column=col+1, padx=2, pady=2)
                e.bind('<KeyRelease>', lambda ev, i=idx: self.t2_auto_focus(ev, i))
                self.t2_entries.append(e)

        # 5. 執行與輸出區塊
        act_f = tk.Frame(self.tab2, padx=10, pady=5)
        act_f.pack(fill=tk.X)
        tk.Button(act_f, text="EXECUTE 64-BYTE COMMAND", command=self.t2_execute, bg="#1976D2", fg="white", font=("Arial", 11, "bold"), width=30).pack(side=tk.LEFT)
        tk.Button(act_f, text="儲存 Data In (.bin)", command=self.t2_save_data, bg="#FF9800", fg="white", font=("Arial", 10, "bold")).pack(side=tk.RIGHT)

        out_f = tk.Frame(self.tab2, padx=10, pady=5)
        out_f.pack(fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(out_f)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.t2_out = tk.Text(out_f, font=("Consolas", 10), bg="#000000", fg="#00FF00", yscrollcommand=sb.set) # Hacker Style
        self.t2_out.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=self.t2_out.yview)

    def t2_log(self, msg):
        self.t2_out.insert(tk.END, msg + "\n")
        self.t2_out.see(tk.END)

    def t2_auto_focus(self, ev, idx):
        if len(self.t2_entries[idx].get()) >= 2 and idx < 63:
            self.t2_entries[idx+1].focus_set()
            self.t2_entries[idx+1].selection_range(0, tk.END)

    def t2_clear_grid(self):
        for e in self.t2_entries:
            e.delete(0, tk.END)
            e.insert(0, "00")

    def t2_load_64b_bin(self):
        path = filedialog.askopenfilename(title="選擇 64-Byte Bin 檔案")
        if path:
            with open(path, "rb") as f:
                data = f.read(64)
                
                # 填入 64 個小格子
                for i, byte in enumerate(data):
                    if i < 64:
                        self.t2_entries[i].delete(0, tk.END)
                        self.t2_entries[i].insert(0, f"{byte:02X}")
                
                # 自動解析 Byte 40 ~ 43 為 Little-Endian 長度
                if len(data) >= 44:
                    length_bytes = data[40:44]
                    transfer_length = int.from_bytes(length_bytes, byteorder='little')
                    
                    if transfer_length > 0:
                        self.t2_len_entry.delete(0, tk.END)
                        self.t2_len_entry.insert(0, str(transfer_length))
                        self.t2_log(f"[Auto-Parse] 從 Offset 40-43 擷取到長度: {transfer_length} Bytes")

    def t2_save_data(self):
        if not self.t2_last_in_data:
            messagebox.showwarning("無法儲存", "目前沒有可用的 Data In 資料！")
            return
        path = filedialog.asksaveasfilename(defaultextension=".bin")
        if path:
            with open(path, "wb") as f: f.write(self.t2_last_in_data)
            self.t2_log(f"[存檔成功] 已儲存 {len(self.t2_last_in_data)} Bytes 到 {os.path.basename(path)}")

    def t2_execute(self):
        self.t2_out.delete(1.0, tk.END)
        self.t2_last_in_data = None
        
        try:
            drive_str = self.drive_combo.get()
            
            # 蒐集 64-byte 矩陣資料
            cmd_64_bytes = []
            for entry in self.t2_entries:
                val = entry.get().strip()
                cmd_64_bytes.append(int(val if val else "00", 16))
                
            length = int(self.t2_len_entry.get().strip() or "0")
            direction = self.t2_dir_var.get()
            ap_key_enabled = self.t2_ap_key_var.get()
            
            # TODO: 這裡目前僅實作將收集到的參數顯示出來。
            # 因為原生的 SCSI Pass Through Direct 的 CDB 欄位最大只支援 16 Bytes。
            # 64-Byte 的指令通常需要透過特定的 Vendor CDB 包裝，或是使用 NVMe Pass Through IOCTL。
            # 請在之後依照您的硬體規格，修改這裡的底層呼叫邏輯。
            
            dir_str = "DATA IN" if direction == SCSI_IOCTL_DATA_IN else "DATA OUT" if direction == SCSI_IOCTL_DATA_OUT else "NO DATA"
            self.t2_log(f">>> 執行目標: {drive_str}")
            self.t2_log(f">>> 傳輸方向: {dir_str} | 長度: {length} Bytes")
            self.t2_log(f">>> AP_KEY 狀態: {'[啟用 ON]' if ap_key_enabled else '[停用 OFF]'}")
            self.t2_log(">>> 收集到的 64-Byte 指令 Payload (Hex):")
            self.t2_log(hexdump(bytes(cmd_64_bytes), 16))
            
            self.t2_log("\n[等待實作] 參數已成功收集。請在此處串接對應的 64-byte 底層 API...")
            
            # 假資料模擬 Data In (供你測試儲存按鈕)
            if direction == SCSI_IOCTL_DATA_IN and length > 0:
                dummy_data = bytes([0xAA, 0xBB, 0xCC, 0xDD] * (length // 4 + 1))[:length]
                self.t2_last_in_data = dummy_data
                self.t2_log("\n--- (模擬) Data In 接收結果 ---")
                self.t2_log(hexdump(dummy_data))
                
        except Exception as e:
            self.t2_log(f"[Error] {str(e)}")

if __name__ == "__main__":
    if ctypes.windll.shell32.IsUserAnAdmin():
        root = tk.Tk()
        app = ScsiToolGUI(root)
        root.mainloop()
    else:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{__file__}"', None, 1)
        sys.exit()