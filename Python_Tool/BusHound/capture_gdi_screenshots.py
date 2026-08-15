import ctypes
from ctypes import wintypes
import tkinter as tk
from PIL import Image
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))
from BusHound import ScsiToolGUI
from backend_storage import hexdump

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD),
        ('biWidth', wintypes.LONG),
        ('biHeight', wintypes.LONG),
        ('biPlanes', wintypes.WORD),
        ('biBitCount', wintypes.WORD),
        ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD),
        ('biXPelsPerMeter', wintypes.LONG),
        ('biYPelsPerMeter', wintypes.LONG),
        ('biClrUsed', wintypes.DWORD),
        ('biClrImportant', wintypes.DWORD)
    ]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ('bmiHeader', BITMAPINFOHEADER),
        ('bmiColors', wintypes.DWORD * 3)
    ]

def capture_hwnd_to_png(hwnd, output_path):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    if w <= 0 or h <= 0:
        w, h = 1050, 850

    hwnd_dc = user32.GetWindowDC(hwnd)
    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
    gdi32.SelectObject(mem_dc, bitmap)

    # PW_RENDERFULLCONTENT = 0x00000002
    user32.PrintWindow(hwnd, mem_dc, 2)

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h  # top-down DIB
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0  # BI_RGB

    buffer_len = w * h * 4
    buf = (ctypes.c_char * buffer_len)()
    gdi32.GetDIBits(mem_dc, bitmap, 0, h, ctypes.byref(buf), ctypes.byref(bmi), 0)

    # 轉為 PIL Image (BGRA -> RGBA)
    img = Image.frombuffer("RGBA", (w, h), bytes(buf), "raw", "BGRA", 0, 1)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path)
    print(f"Successfully saved HWND capture: {output_path} ({w}x{h})")

    # 釋放 GDI 物件
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hwnd, hwnd_dc)

def run():
    root = tk.Tk()
    root.geometry("1050x850")
    app = ScsiToolGUI(root)
    root.update()

    # 模擬硬碟列表
    app.drive_combo['values'] = [
        "PhysicalDrive1 - CT500MX500SSD1 (500GB)",
        "PhysicalDrive0 - SATA SSD 128GB",
        "PhysicalDrive2 - INTEL SSDPEKNU512GZ NVMe"
    ]
    app.drive_combo.current(0)

    # 1. 產生 Tab 1 截圖
    app.notebook.select(app.tab1)
    inq_cdb = ["12", "00", "00", "00", "24", "00"] + ["00"]*10
    for i, val in enumerate(inq_cdb):
        app.t1_cdb_entries[i].delete(0, tk.END)
        app.t1_cdb_entries[i].insert(0, val)
    app.t1_len_entry.delete(0, tk.END)
    app.t1_len_entry.insert(0, "36")
    
    app.t1_out.delete(1.0, tk.END)
    app.t1_log(">>> 發送指令: [INQUIRY (0x12)]")
    app.t1_log("    (Length: 36 Bytes)\n")
    app.t1_log("[返回狀態] GOOD (0x00)\n")
    app.t1_log("--- 接收資料 (Data In) ---")
    mock_inq = (
        b"\x00\x80\x02\x02\x1f\x00\x00\x00"
        b"ATA     "
        b"CT500MX500SSD1  "
        b"M3CR043 "
    )
    app.t1_log(hexdump(mock_inq))
    root.update()
    
    hwnd = root.winfo_id()
    capture_hwnd_to_png(hwnd, os.path.join(os.path.dirname(__file__), "assets", "screenshot_tab1_scsi.png"))

    # 2. 產生 Tab 2 截圖
    app.notebook.select(app.tab2)
    app.t2_ap_key_var.set(True)
    app.t2_lock_var.set(True)
    app.t2_keep_lock_var.set(False)
    app.t2_len_entry.delete(0, tk.END)
    app.t2_len_entry.insert(0, "512")
    
    for i, e in enumerate(app.t2_entries):
        e.delete(0, tk.END)
        if i == 0: e.insert(0, "AA")
        elif i == 1: e.insert(0, "55")
        elif i == 2: e.insert(0, "01")
        elif i == 40: e.insert(0, "01")
        else: e.insert(0, "00")
        
    app.t2_out.delete(1.0, tk.END)
    app.t2_log("================= LOCK STATUS ================")
    app.t2_log("[ O K ] 實體磁碟已成功獨佔鎖定 (FSCTL_LOCK_VOLUME)")
    app.t2_log("==============================================\n")
    app.t2_log("==========================================")
    app.t2_log("[AP_KEY Auth] 開始執行特權解鎖序列 (3 cmds)...")
    app.t2_log("[AP_KEY] 找到金鑰: AP_Key\\ap_key.bin")
    app.t2_log(" -> [AP_KEY 1/3] [VUC / AP_KEY: CONFIG DATA-OUT (0x06)]")
    app.t2_log(" -> [AP_KEY 2/3] [VUC / AP_KEY: ACTION NO-DATA/OUT (0x06)]")
    app.t2_log(" -> [AP_KEY 3/3] [VUC / AP_KEY: READ STATUS (0x06)]")
    app.t2_log("[AP_KEY Auth] 解鎖成功，硬碟進入特權模式！")
    app.t2_log("==========================================\n")
    app.t2_log("==========================================")
    app.t2_log("[VUC Sequence] 背景執行 64-Byte VUC 配置序列...")
    app.t2_log(" -> 發送主要指令: [VUC: ACTION DATA-IN (0x06)]")
    app.t2_log("    (Sectors: 0x0001 -> Byte3: 0x00, Byte4: 0x01)")
    app.t2_log("    (Bytes Length: 0x00000200 -> Byte5~8: 0x00 0x00 0x02 0x00)\n")
    app.t2_log("--- VUC 傳輸結果 (Data-In) ---")
    mock_vuc_data = bytes([i % 256 for i in range(64)])
    app.t2_log(hexdump(mock_vuc_data))
    app.t2_log("--------------------------------\n")
    app.t2_log("[VUC Sequence] 全部指令序列執行成功！")
    app.t2_log("==========================================")
    
    root.update()
    capture_hwnd_to_png(hwnd, os.path.join(os.path.dirname(__file__), "assets", "screenshot_tab2_vuc.png"))

    # 3. 產生 Tab 3 (Packet Sniffer) 截圖
    app.notebook.select(app.tab3)
    app.t3_clear_packets()
    
    # 模擬 4 筆封包
    packets = [
        {
            "index": 1, "timestamp": "10:15:32.102", "drive": "PhysicalDrive1", "direction": "OUT",
            "cdb_hex": "06 FE C0 00 01 00 00 02 00 00 00 00 00 00 00 00",
            "cmd_name": "[VUC / AP_KEY: CONFIG DATA-OUT (0x06)]",
            "data_len": 512, "payload_hex": "AA 55 01 00", "scsi_status": "0x00 - GOOD",
            "sense_str": "(none)", "elapsed_ms": "0.85",
            "raw_payload": bytes([0xAA, 0x55, 0x01] + [0]*509), "raw_cdb": b"", "raw_sense": b""
        },
        {
            "index": 2, "timestamp": "10:15:32.105", "drive": "PhysicalDrive1", "direction": "NONE",
            "cdb_hex": "06 FE C1 00 00 00 00 00 00 00 00 00 00 00 00 00",
            "cmd_name": "[VUC / AP_KEY: ACTION NO-DATA/OUT (0x06)]",
            "data_len": 0, "payload_hex": "(none)", "scsi_status": "0x00 - GOOD",
            "sense_str": "(none)", "elapsed_ms": "0.42",
            "raw_payload": b"", "raw_cdb": b"", "raw_sense": b""
        },
        {
            "index": 3, "timestamp": "10:15:32.108", "drive": "PhysicalDrive1", "direction": "IN",
            "cdb_hex": "06 FE C3 00 01 00 00 02 00 00 00 00 00 00 00 00",
            "cmd_name": "[VUC / AP_KEY: READ STATUS (0x06)]",
            "data_len": 512, "payload_hex": "00 55 AA 00", "scsi_status": "0x00 - GOOD",
            "sense_str": "(none)", "elapsed_ms": "1.12",
            "raw_payload": bytes([0x00, 0x55, 0xAA] + [0]*509), "raw_cdb": b"", "raw_sense": b""
        },
        {
            "index": 4, "timestamp": "10:15:32.115", "drive": "PhysicalDrive1", "direction": "IN",
            "cdb_hex": "12 00 00 00 24 00 00 00 00 00 00 00 00 00 00 00",
            "cmd_name": "[INQUIRY (0x12)]",
            "data_len": 36, "payload_hex": "00 80 02 02 1F 00 00 00 41 54 41 ...", "scsi_status": "0x00 - GOOD",
            "sense_str": "(none)", "elapsed_ms": "1.34",
            "raw_payload": mock_inq, "raw_cdb": b"\x12\x00\x00\x00\x24\x00", "raw_sense": b""
        }
    ]
    for p in packets:
        app.t3_on_new_packet(p)

    # 選中第 4 筆 (INQUIRY) 以在下方顯示 Hexdump
    children = app.t3_tree.get_children()
    if children:
        app.t3_tree.selection_set(children[-1])
        app.t3_on_select_packet(None)

    root.update()
    capture_hwnd_to_png(hwnd, os.path.join(os.path.dirname(__file__), "assets", "screenshot_tab3_sniffer.png"))

    root.destroy()

if __name__ == "__main__":
    run()
