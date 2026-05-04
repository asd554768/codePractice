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
    result = []
    for i in range(0, len(src), length):
        chunk = src[i:i+length]
        hex_str = ' '.join(f'{b:02X}' for b in chunk)
        ascii_str = ''.join(chr(b) if 0x20 <= b < 0x7F else '.' for b in chunk)
        result.append(f"{i:04X}   {hex_str:<{length*3}}   {ascii_str}")
    return '\n'.join(result)

# --- 核心通訊 ---
def send_scsi_command(physical_drive_num, cdb_bytes, data_transfer_length, direction, out_data_bytes=None):
    drive_path = f"\\\\.\\PhysicalDrive{physical_drive_num}"
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateFileW(drive_path, GENERIC_READ | GENERIC_WRITE, 
                                  FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
    if handle == -1: raise PermissionError(f"Open Failed: {kernel32.GetLastError()}")

    sense_buffer = SENSE_DATA_BUFFER()
    data_buffer = (ctypes.c_ubyte * data_transfer_length)(*(out_data_bytes if out_data_bytes else [0]*data_transfer_length))

    class SPTD_WITH_SENSE(ctypes.Structure):
        _fields_ = [("sptd", SCSI_PASS_THROUGH_DIRECT), ("sense", SENSE_DATA_BUFFER)]

    combined = SPTD_WITH_SENSE()
    combined.sptd.Length = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT)
    combined.sptd.CdbLength = len(cdb_bytes)
    combined.sptd.DataIn = direction
    combined.sptd.DataTransferLength = data_transfer_length
    combined.sptd.TimeOutValue = 10 
    combined.sptd.DataBuffer = ctypes.cast(ctypes.pointer(data_buffer), ctypes.c_void_p)
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
    return combined.sptd.ScsiStatus, bytes(data_buffer), bytes(combined.sense.data)

# --- GUI 介面 ---
class ScsiToolGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Python SCSI Cmd Tool (Enterprise Edition)")
        self.root.geometry("850x850")
        self.dir_var = tk.IntVar(value=SCSI_IOCTL_DATA_IN)
        self.loaded_data_bin = None
        self.cdb_entries = [] # 儲存 16 個 Entry 物件
        self.create_widgets()

    def create_widgets(self):
        # 1. 磁碟設定
        cfg_frame = tk.LabelFrame(self.root, text="Step 1: 裝置與方向", padx=10, pady=10)
        cfg_frame.pack(fill=tk.X, padx=10, pady=5)
        self.drive_combo = ttk.Combobox(cfg_frame, values=get_physical_drives(), state="readonly", width=70)
        if self.drive_combo['values']: self.drive_combo.current(0)
        self.drive_combo.pack(side=tk.TOP, anchor=tk.W, pady=5)

        tk.Radiobutton(cfg_frame, text="Data In (讀取)", variable=self.dir_var, value=SCSI_IOCTL_DATA_IN).pack(side=tk.LEFT)
        tk.Radiobutton(cfg_frame, text="Data Out (寫入)", variable=self.dir_var, value=SCSI_IOCTL_DATA_OUT).pack(side=tk.LEFT, padx=20)

        # 2. CDB 輸入區 (改善項目：16-Byte 矩陣)
        cdb_frame = tk.LabelFrame(self.root, text="Step 2: CDB (Command Descriptor Block)", padx=10, pady=10)
        cdb_frame.pack(fill=tk.X, padx=10, pady=5)

        # CDB 檔案載入按鈕
        cdb_btn_frame = tk.Frame(cdb_frame)
        cdb_btn_frame.pack(fill=tk.X, pady=5)
        tk.Button(cdb_btn_frame, text="從 .bin 載入 CDB", command=self.on_load_cdb_file, bg="#E1F5FE").pack(side=tk.LEFT)
        tk.Button(cdb_btn_frame, text="清空 CDB", command=self.on_clear_cdb).pack(side=tk.LEFT, padx=5)

        # 16 個 Byte 輸入框矩陣 (8x2 佈局)
        matrix_frame = tk.Frame(cdb_frame)
        matrix_frame.pack(pady=5)

        for i in range(16):
            row = i // 8
            col = i % 8
            # 加上 Label 標示 Offset
            cell_frame = tk.Frame(matrix_frame, padx=2, pady=2)
            cell_frame.grid(row=row, column=col)
            tk.Label(cell_frame, text=f"{i:02d}", font=("Arial", 7), fg="gray").pack()
            
            entry = tk.Entry(cell_frame, width=4, font=("Consolas", 12, "bold"), justify='center')
            entry.insert(0, "00")
            entry.pack()
            # 綁定自動跳格事件
            entry.bind('<KeyRelease>', lambda e, idx=i: self.auto_focus(e, idx))
            self.cdb_entries.append(entry)

        # 3. Data Buffer 設定
        buf_frame = tk.LabelFrame(self.root, text="Step 3: Data Buffer (僅 Data Out 時使用)", padx=10, pady=10)
        buf_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(buf_frame, text="傳輸長度 (Bytes):").pack(side=tk.LEFT)
        self.len_entry = tk.Entry(buf_frame, width=15)
        self.len_entry.insert(0, "36")
        self.len_entry.pack(side=tk.LEFT, padx=5)

        tk.Button(buf_frame, text="載入 Data Bin", command=self.on_load_data_file).pack(side=tk.LEFT, padx=10)
        self.data_file_label = tk.Label(buf_frame, text="未選擇檔案", fg="gray")
        self.data_file_label.pack(side=tk.LEFT)

        # 4. 執行與輸出
        self.send_btn = tk.Button(self.root, text="EXECUTE SCSI COMMAND", command=self.on_send, 
                                  bg="#2E7D32", fg="white", font=("Arial", 12, "bold"), pady=10)
        self.send_btn.pack(fill=tk.X, padx=10, pady=10)

        out_frame = tk.Frame(self.root)
        out_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.scrollbar = tk.Scrollbar(out_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_text = tk.Text(out_frame, font=("Consolas", 10), bg="#1E1E1E", fg="#D4D4D4", 
                                   yscrollcommand=self.scrollbar.set)
        self.output_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.output_text.yview)

    def auto_focus(self, event, idx):
        # 如果輸入滿 2 個字元，自動跳到下一個框
        val = self.cdb_entries[idx].get()
        if len(val) >= 2 and idx < 15:
            self.cdb_entries[idx+1].focus_set()
            self.cdb_entries[idx+1].selection_range(0, tk.END)

    def on_load_cdb_file(self):
        path = filedialog.askopenfilename(title="選擇 CDB Bin 檔案", filetypes=[("Binary", "*.bin"), ("All", "*.*")])
        if path:
            with open(path, "rb") as f:
                data = f.read(16) # 只讀取前 16 bytes
                for i, byte in enumerate(data):
                    self.cdb_entries[i].delete(0, tk.END)
                    self.cdb_entries[i].insert(0, f"{byte:02X}")

    def on_clear_cdb(self):
        for entry in self.cdb_entries:
            entry.delete(0, tk.END)
            entry.insert(0, "00")

    def on_load_data_file(self):
        path = filedialog.askopenfilename(title="選擇 Data Bin 檔案")
        if path:
            with open(path, "rb") as f: self.loaded_data_bin = f.read()
            self.data_file_label.config(text=f"已載入: {os.path.basename(path)}", fg="green")
            self.len_entry.delete(0, tk.END)
            self.len_entry.insert(0, str(len(self.loaded_data_bin)))
            self.dir_var.set(SCSI_IOCTL_DATA_OUT)

    def on_send(self):
        self.output_text.delete(1.0, tk.END)
        try:
            drive_num = int(self.drive_combo.get().split(" ")[0].replace("PhysicalDrive", ""))
            
            # 從 16 個 Entry 收集 CDB
            cdb_bytes = []
            for entry in self.cdb_entries:
                val = entry.get().strip()
                cdb_bytes.append(int(val if val else "00", 16))
            
            length = int(self.len_entry.get())
            direction = self.dir_var.get()
            
            out_bytes = None
            if direction == SCSI_IOCTL_DATA_OUT:
                out_bytes = list(self.loaded_data_bin) if self.loaded_data_bin else [0]*length
                if len(out_bytes) < length: out_bytes += [0]*(length-len(out_bytes))
                out_bytes = out_bytes[:length]

            self.log(f">>> 發送指令至 {self.drive_combo.get()}")
            status, data, sense = send_scsi_command(drive_num, cdb_bytes, length, direction, out_bytes)
            
            self.log(f"Status: 0x{status:02X}")
            if status != 0: self.log(f"Sense Key Error: {' '.join([f'{b:02x}' for b in sense])}")
            if direction == SCSI_IOCTL_DATA_IN: self.log(hexdump(data))
                
        except Exception as e: self.log(f"Error: {str(e)}")

    def log(self, msg):
        self.output_text.insert(tk.END, msg + "\n")
        self.output_text.see(tk.END)

if __name__ == "__main__":
    if ctypes.windll.shell32.IsUserAnAdmin():
        root = tk.Tk(); app = ScsiToolGUI(root); root.mainloop()
    else:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{__file__}"', None, 1)
        sys.exit()
