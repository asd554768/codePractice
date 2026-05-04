import sys
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess

# --- 定義 Windows API 常數與結構 ---
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2

IOCTL_SCSI_PASS_THROUGH_DIRECT = 0x4D014
SCSI_IOCTL_DATA_IN = 1
SCSI_IOCTL_DATA_OUT = 0

class SCSI_PASS_THROUGH_DIRECT(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("ScsiStatus", ctypes.c_ubyte),
        ("PathId", ctypes.c_ubyte),
        ("TargetId", ctypes.c_ubyte),
        ("Lun", ctypes.c_ubyte),
        ("CdbLength", ctypes.c_ubyte),
        ("SenseInfoLength", ctypes.c_ubyte),
        ("DataIn", ctypes.c_ubyte),
        ("DataTransferLength", wintypes.ULONG),
        ("TimeOutValue", wintypes.ULONG),
        ("DataBuffer", ctypes.c_void_p),
        ("SenseInfoOffset", wintypes.ULONG),
        ("Cdb", ctypes.c_ubyte * 16)
    ]

# --- 獲取磁碟名稱函數 ---
def get_physical_drives():
    drives = []
    try:
        cmd = ['powershell', '-NoProfile', '-Command', 
               "Get-CimInstance Win32_DiskDrive | ForEach-Object { '{0}:::{1}' -f $_.Index, $_.Model }"]
        
        creationflags = 0
        if hasattr(subprocess, 'CREATE_NO_WINDOW'):
            creationflags = subprocess.CREATE_NO_WINDOW
            
        result = subprocess.run(cmd, capture_output=True, text=True, creationflags=creationflags)
        
        for line in result.stdout.splitlines():
            if ":::" in line:
                idx, model = line.split(":::", 1)
                drives.append(f"PhysicalDrive{idx.strip()} - {model.strip()}")
                
    except Exception as e:
        print(f"無法獲取磁碟名稱: {e}")
        
    return drives if drives else [f"PhysicalDrive{i}" for i in range(8)]

# --- 核心發送函數 ---
def send_scsi_command(physical_drive_num, cdb_bytes, data_transfer_length, data_in=True):
    drive_path = f"\\\\.\\PhysicalDrive{physical_drive_num}"
    kernel32 = ctypes.windll.kernel32
    
    handle = kernel32.CreateFileW(
        drive_path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
        None, OPEN_EXISTING, 0, None
    )
    
    if handle == -1:
        error_code = kernel32.GetLastError()
        if error_code == 5:
            raise PermissionError("權限不足：請確認程式是否以系統管理員身分執行！")
        raise OSError(f"無法開啟設備，錯誤碼: {error_code}")

    data_buffer = (ctypes.c_ubyte * data_transfer_length)()
    sptd = SCSI_PASS_THROUGH_DIRECT()
    sptd.Length = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT)
    sptd.CdbLength = len(cdb_bytes)
    sptd.DataIn = SCSI_IOCTL_DATA_IN if data_in else SCSI_IOCTL_DATA_OUT
    sptd.DataTransferLength = data_transfer_length
    sptd.TimeOutValue = 10 
    sptd.DataBuffer = ctypes.cast(ctypes.pointer(data_buffer), ctypes.c_void_p)
    sptd.SenseInfoLength = 0
    sptd.SenseInfoOffset = 0
    
    for i in range(len(cdb_bytes)):
        sptd.Cdb[i] = cdb_bytes[i]

    bytes_returned = wintypes.DWORD()
    result = kernel32.DeviceIoControl(
        handle, IOCTL_SCSI_PASS_THROUGH_DIRECT, ctypes.byref(sptd), ctypes.sizeof(sptd),
        ctypes.byref(sptd), ctypes.sizeof(sptd), ctypes.byref(bytes_returned), None
    )
    
    kernel32.CloseHandle(handle)
    
    if not result:
        raise OSError(f"發送 SCSI 指令失敗，錯誤碼: {kernel32.GetLastError()}")
        
    return sptd.ScsiStatus, bytes(data_buffer)

# --- 輔助函數：格式化 Hex Dump ---
def hexdump(src, length=16):
    result = []
    for i in range(0, len(src), length):
        chunk = src[i:i+length]
        hex_str = ' '.join(f'{b:02X}' for b in chunk)
        ascii_str = ''.join(chr(b) if 0x20 <= b < 0x7F else '.' for b in chunk)
        result.append(f"{i:04X}   {hex_str:<{length*3}}   {ascii_str}")
    return '\n'.join(result)

# --- GUI 介面設計 ---
class ScsiToolGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Python SCSI Cmd Tool (Administrator)")
        self.root.geometry("680x480")
        self.create_widgets()

    def create_widgets(self):
        control_frame = tk.Frame(self.root, padx=10, pady=10)
        control_frame.pack(fill=tk.X)

        tk.Label(control_frame, text="Select Drive:").grid(row=0, column=0, sticky=tk.W, pady=5)
        
        drive_list = get_physical_drives()
        self.drive_combo = ttk.Combobox(control_frame, values=drive_list, state="readonly", width=45)
        if drive_list:
            self.drive_combo.current(0)
        self.drive_combo.grid(row=0, column=1, columnspan=2, sticky=tk.W, padx=5)

        tk.Label(control_frame, text="CDB (Hex):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.cdb_entry = tk.Entry(control_frame, width=40, font=("Consolas", 10))
        self.cdb_entry.insert(0, "12 00 00 00 24 00")
        self.cdb_entry.grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=5)
        tk.Label(control_frame, text="(空格分隔)").grid(row=1, column=3, sticky=tk.W)

        tk.Label(control_frame, text="Transfer Length:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.len_entry = tk.Entry(control_frame, width=10)
        self.len_entry.insert(0, "36")
        self.len_entry.grid(row=2, column=1, sticky=tk.W, padx=5)

        self.send_btn = tk.Button(control_frame, text="Send Command", command=self.on_send, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        self.send_btn.grid(row=3, column=0, columnspan=2, pady=15, sticky=tk.W)

        output_frame = tk.Frame(self.root, padx=10, pady=5)
        output_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(output_frame, text="Output (Hex Dump):").pack(anchor=tk.W)
        self.output_text = tk.Text(output_frame, height=15, font=("Consolas", 10), bg="#1E1E1E", fg="#D4D4D4")
        self.output_text.pack(fill=tk.BOTH, expand=True)

    def on_send(self):
        self.output_text.delete(1.0, tk.END)
        try:
            drive_str = self.drive_combo.get()
            drive_num_str = drive_str.split(" ")[0].replace("PhysicalDrive", "")
            drive_num = int(drive_num_str)
            
            cdb_str = self.cdb_entry.get().strip()
            if not cdb_str:
                raise ValueError("CDB 不能為空！")
            
            cdb_bytes = [int(x, 16) for x in cdb_str.split()]
            if len(cdb_bytes) > 16:
                raise ValueError("CDB 長度不能超過 16 Bytes！")

            transfer_length = int(self.len_entry.get())

            self.log(f">>> Sending to [{drive_str}]")
            self.log(f">>> CDB: {cdb_str} (Length: {transfer_length})")
            
            status, data = send_scsi_command(drive_num, cdb_bytes, transfer_length)
            
            self.log(f"--- SCSI Status: 0x{status:02X} ---")
            
            if len(data) > 0:
                self.log(hexdump(data))
            else:
                self.log("No data returned.")
                
        except ValueError as e:
            messagebox.showerror("格式錯誤", f"請檢查輸入格式：\n{e}")
        except Exception as e:
            self.log(f"ERROR: {str(e)}")

    def log(self, message):
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)

# --- 權限檢查與主程式入口 ---
def is_admin():
    """檢查當前是否具有系統管理員權限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if __name__ == "__main__":
    if is_admin():
        # 如果已經是管理員，正常啟動 GUI
        root = tk.Tk()
        app = ScsiToolGUI(root)
        root.mainloop()
    else:
        # 如果不是管理員，呼叫 UAC 請求提權，並重新啟動程式
        print("請求系統管理員權限中...")
        # sys.executable 是 python.exe 的路徑
        # __file__ 是當前腳本的路徑
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{__file__}"', None, 1)
        # 退出當前的無權限進程
        sys.exit()