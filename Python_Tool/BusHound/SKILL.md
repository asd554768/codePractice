---
name: BusHound Python Storage Debug Tool
description: >
  知識文件：用於理解、除錯與擴充 BusHound.py —— 一個以 Python + tkinter 實作的
  Windows SCSI/VUC 除錯工具，功能對標商業軟體 BusHound。
  當你需要修改、debug 或新增功能到此專案時，必須先讀此文件。
---

# BusHound.py — AI 知識總結

## 一、專案目的與架構概述

**目的**：模擬商業工具 BusHound，讓工程師能在 Windows 上透過 Python 直接對實體磁碟（PhysicalDrive）發送 SCSI / Vendor Unique Command (VUC)，並觀察回應資料與 Sense Data。

**執行環境**：
- 作業系統：Windows（強制需要 Admin 權限，啟動時自動 UAC 提權）
- Python：3.x，依賴 `tkinter`, `ctypes`, `subprocess`, `os`
- 完全無外部 pip 套件依賴

**檔案結構（目前）**：
```
BusHound/
  BusHound.py      # 主程式（644 行），GUI + SCSI 邏輯全在此
  AP_Key/
    ap_key.bin     # (執行時動態需要) AP_KEY 認證金鑰二進位檔，需自行放置
```

---

## 二、核心技術棧

### 1. Windows API 呼叫（ctypes）

| 用途 | API / IOCTL | 常數 |
|---|---|---|
| 開啟磁碟 Handle | `CreateFileW` | `GENERIC_READ | GENERIC_WRITE`, `OPEN_EXISTING` |
| 發送 SCSI 指令 | `DeviceIoControl` | `IOCTL_SCSI_PASS_THROUGH_DIRECT (0x4D014)` |
| 鎖定/解鎖磁碟 | `DeviceIoControl` | `FSCTL_LOCK_VOLUME (0x90018)` / `FSCTL_UNLOCK_VOLUME (0x9001C)` |
| 關閉 Handle | `CloseHandle` | — |

**關鍵結構體**：
```python
class SCSI_PASS_THROUGH_DIRECT(ctypes.Structure):
    _fields_ = [
        ("Length", USHORT),           # 必須 = sizeof(SCSI_PASS_THROUGH_DIRECT)
        ("ScsiStatus", c_ubyte),      # 回傳 SCSI 狀態
        ("PathId", c_ubyte),
        ("TargetId", c_ubyte),
        ("Lun", c_ubyte),
        ("CdbLength", c_ubyte),       # CDB 長度（通常 6 或 16）
        ("SenseInfoLength", c_ubyte), # Sense Buffer 大小
        ("DataIn", c_ubyte),          # 0=Out, 1=In, 2=No Data
        ("DataTransferLength", ULONG),# 傳輸位元組數
        ("TimeOutValue", ULONG),      # 逾時秒數（目前寫死 10）
        ("DataBuffer", c_void_p),     # 資料指標
        ("SenseInfoOffset", ULONG),   # Sense 資料在結構體的 offset
        ("Cdb", c_ubyte * 16)         # 最多 16 byte CDB
    ]
```

### 2. 指令架構：SPTD_WITH_SENSE 複合結構體

`send_scsi_command()` 採用 **In-place buffer** 設計，即同一個記憶體區塊同時作為 IOCTL 的 input 和 output buffer：

```python
class SPTD_WITH_SENSE(ctypes.Structure):
    _fields_ = [("sptd", SCSI_PASS_THROUGH_DIRECT), ("sense", SENSE_DATA_BUFFER)]
```

`SenseInfoOffset = sizeof(SCSI_PASS_THROUGH_DIRECT)` 讓驅動把 sense data 寫到結構體尾端。

---

## 三、GUI 架構

```
ScsiToolGUI
├── create_global_header()   → 磁碟選擇 ComboBox（全 Tab 共用）
├── Tab 1: SCSI Command (16-Byte)
│   ├── 16 格 CDB 輸入矩陣（Entry×16）
│   ├── Data In / Data Out / No Data 方向選擇
│   ├── 傳輸長度輸入
│   ├── 載入 .bin CDB / Data Out
│   └── EXECUTE → t1_execute()
└── Tab 2: VUC 64-Byte Payload
    ├── 64 格 Payload 輸入矩陣（Entry×64，4行×16列）
    ├── AP_KEY checkbox（執行前先做 3-step 認證序列）
    ├── Lock Device checkbox
    ├── 載入 64-byte .bin / Data Out .bin
    └── EXECUTE → t2_execute()
```

---

## 四、VUC 指令序列邏輯（最重要）

### AP_KEY 認證序列（3 個 SCSI 指令）
```
Step 1: CDB [06 FE C0 00 01 00 00 02 ...] Data-Out 512B  → 送 AP Key 資料
Step 2: CDB [06 FE C1 00 00 00 ...] No-Data              → 觸發動作
Step 3: CDB [06 FE C3 00 01 00 00 02 ...] Data-In 512B   → 讀取狀態
```

### VUC 主體序列（3 個 SCSI 指令）
```
Step 1 (VUC 1): CDB [06 FE C0 ...] Data-Out 512B  → 送 64-byte 指令 payload（補零到 512B）
Step 2 (VUC 2): CDB [06 FE C2/C1 Byte3 Byte4 Byte5~8 ...] Data-In/Out Nbytes → 實際資料傳輸
Step 3 (VUC 3): CDB [06 FE C3 ...] Data-In 512B   → 讀取執行後狀態
```

**VUC CDB 欄位計算**：
- `Byte3~4`：傳輸的 Sector 數（`math.ceil(length / 512)`）
- `Byte5~8`：傳輸的 Byte 數（32-bit，b5=最高位）
- `Byte2`：`0xC2`=Data-In，`0xC1`=Data-Out 或 No-Data

---

## 五、已知 Bug 與問題

### BUG-1：Handle 關閉判斷語意不嚴謹（Tab 1 & 2）
**位置**：`finally: if handle: close_drive(handle)`

`open_drive()` 若 `CreateFileW` 回傳 `INVALID_HANDLE_VALUE (-1)` 且被轉換成 Python int，`if handle` 評估為 True（因 -1 是 truthy），但程式已在 `open_drive()` 內部拋出 `PermissionError`，所以 handle 實際在 finally 時為 `None`。**不會出問題，但語意不嚴謹**。

**建議修正**：用 `if handle is not None` 取代 `if handle`。

---

### BUG-2（高危）：`t2_execute()` finally 區塊可能 NameError
**位置**：Line 631-633

```python
finally:
    if handle:
        if lock_enabled:   # 若 try 在 lock_enabled 賦值前 crash，NameError!
            unlock_drive(handle)
```

`lock_enabled` 在 try block 第 513 行才賦值。若在此之前（如 drive_num 解析失敗）拋出例外，finally 執行時 `lock_enabled` 不存在，**二次拋出 NameError 導致原始例外被覆蓋、難以 debug**。

**立即修正（在函式頂加一行）**：
```python
def t2_execute(self):
    self.t2_out.delete(1.0, tk.END)
    self.t2_last_in_data = None
    handle = None
    lock_enabled = False  # ← 加這行！確保 finally 安全
```

---

### BUG-3：AP_KEY 純解鎖模式的 return 行為需確認
**位置**：Line 563-565

```python
if ap_key_enabled and is_matrix_empty:
    self.t2_log("純解鎖模式，跳過 VUC 指令。")
    return  # ← 此 return 在 try 內，會觸發 finally → 解鎖磁碟
```

行為：完成 AP_KEY 序列後發現矩陣全空 → 記 log → return → finally 解鎖。**流程本身正確**，但需確認「純解鎖後磁碟應保持 exclusive lock 還是立即解鎖」，目前設計是立即解鎖。

---

### BUG-4：`t2_load_64b_bin()` Length 自動解析硬編碼 offset
**位置**：Line 472-478

```python
length_bytes = data[40:44]
transfer_length = int.from_bytes(length_bytes, 'little') * 4
```

- Offset 40 是特定廠商 payload 格式的 sector count 欄位
- 乘以 4 的假設（unit=? 需確認）
- 無上限保護，極端值可能導致超大 buffer 配置
- 若使用不同廠商格式，自動解析出錯會靜默設定錯誤長度

---

### BUG-5：AP_KEY 金鑰路徑用相對路徑（CWD 依賴）
**位置**：Line 535

```python
ap_key_path = os.path.join("AP_Key", "ap_key.bin")
```

此路徑相對於 **Python 執行時的 CWD**，非腳本所在目錄。若從其他目錄執行（如 IDE、桌面捷徑）會找不到檔案。

**修正**：
```python
ap_key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AP_Key", "ap_key.bin")
```

---

### 潛在問題：SCSI_PASS_THROUGH_DIRECT 結構體 Alignment
Windows 驅動在 64-bit OS 要求 `SCSI_PASS_THROUGH_DIRECT` 有特定 alignment（`DataBuffer` 為指標，需 8-byte 對齊）。目前無 `_pack_` 設定。

若遇到：
- `IOCTL_SCSI_PASS_THROUGH_DIRECT` 回傳 Error 87（Invalid Parameter）
- Error 5（Access Denied，有時是 alignment 問題偽裝）

優先懷疑此問題，測試加上 `_pack_ = 1` 或讓系統自然對齊。

---

## 六、下一步規劃建議

### 短期（Bug Fix 優先）
1. **修 BUG-2**：`t2_execute()` 頂部加 `lock_enabled = False`（5 分鐘）
2. **修 BUG-5**：AP_KEY 路徑改用 `__file__` 為基準（5 分鐘）
3. **Error Code 人類可讀**：用 `FormatMessageW` 替代直接顯示 `GetLastError()` 數字

### 中期（功能擴充）
4. **Log 匯出**：`t1_out` / `t2_out` 文字存成 `.txt`
5. **Preset 系統**：CDB/Payload 矩陣存成 JSON 預設集合，可快速載入
6. **Sense Data ASC/ASCQ 細化**：加完整 T10 lookup table（目前只解析 Sense Key）
7. **hex 輸入驗證**：矩陣 Entry 加 `validatecommand`，防止非 hex 字元
8. **多指令批次執行**：Sequence Editor，排列多步驟一次執行

### 長期（架構重構）
9. **後端分離**：將 `send_scsi_command`, `open_drive` 等抽成 `scsi_backend.py`
10. **CLI 模式**：`python BusHound.py --drive 0 --cdb "06FEC0..." --length 512 --in`
11. **IDENTIFY DEVICE 解析**：ATA PASS-THROUGH 支援，自動解析 512B identify data

---

## 七、重要注意事項（給 AI 的 checklist）

- [ ] 必須以 Admin 執行，程式已內建 UAC 提權
- [ ] 操作 PhysicalDrive Write 有資料損毀風險，修改前確認
- [ ] FSCTL_LOCK_VOLUME 失敗目前只警告不中止，需注意
- [ ] Tab 2 的 64-byte Payload 要補零到 512B 才送（程式已處理）
- [ ] `send_scsi_command()` 中 `SPTD_WITH_SENSE` 是定義在函式內的 local class，每次呼叫都重建，這是刻意設計（避免 ctypes 狀態殘留）
- [ ] Tab 1 的 CDB 固定 16 byte，Tab 2 的 Payload 是 64 byte 送 512B buffer

---

## 八、打包成 EXE（PyInstaller 指南）

> 此程式**完全不依賴任何第三方 pip 套件**，僅使用 Python 標準函式庫。

### 依賴清單

| 項目 | 說明 |
|---|---|
| **Python 3.8+** | 建議使用 3.10 或 3.11，穩定性最佳 |
| **tkinter** | Python 內建，Windows 安裝版已包含 |
| **ctypes / wintypes** | Python 內建 |
| **subprocess, os, sys** | Python 內建 |
| **PyInstaller** | 僅打包時需要，**目標電腦不需安裝** |

### 安裝 PyInstaller（開發機執行一次即可）

```powershell
pip install pyinstaller
```

### 打包指令

```powershell
# 切換到 BusHound.py 所在目錄
cd "C:\Users\asd55\OneDrive\桌面\code\myGit\codePractice\Python_Tool\BusHound"

# 打包（單一 EXE，無 CMD 視窗，含版本圖示）
pyinstaller --onefile --windowed --name BusHound BusHound.py
```

**關鍵旗標說明**：

| 旗標 | 作用 |
|---|---|
| `--onefile` | 所有檔案壓縮成單一 `.exe`，方便散布 |
| `--windowed` / `--noconsole` | **不跳出 CMD 黑視窗**（兩者等效，擇一即可） |
| `--name BusHound` | 輸出 EXE 名稱 |

**加入圖示（可選）**：
```powershell
pyinstaller --onefile --windowed --name BusHound --icon icon.ico BusHound.py
```

### 輸出目錄結構

```
BusHound/
  dist/
    BusHound.exe        ← 只需要這個檔案
  build/                ← 中間暫存，可刪除
  BusHound.spec         ← 打包設定檔，可留存供下次復用
```

### 部署目標電腦所需檔案

```
任意資料夾/
  BusHound.exe          ← 主程式
  AP_Key/
    ap_key.bin          ← 金鑰檔（若使用 AP_KEY 功能才需要）
```

> [!IMPORTANT]
> `AP_Key/ap_key.bin` **必須放在 EXE 旁邊的同層目錄**，不是放進 EXE 內。
> 程式會以 `sys.executable` 所在目錄為根目錄自動搜尋，搜尋順序：
> 1. EXE 同層目錄下的 `AP_Key\ap_key.bin`
> 2. 當前工作目錄下的 `AP_Key\ap_key.bin`
> 3. 上一層目錄下的 `AP_Key\ap_key.bin`
> 4. 全部找不到 → 彈出 filedialog 讓使用者手動選擇

### 目標電腦的執行環境要求

| 項目 | 要求 |
|---|---|
| 作業系統 | Windows 10 / 11（64-bit）|
| 執行權限 | **系統管理員（Administrator）**，程式已內建 UAC 提權 |
| Python | **不需要安裝**（PyInstaller 已打包 runtime）|
| Visual C++ Redistributable | 通常 Win10/11 已內建，若啟動失敗才需安裝 |

### 常見打包問題

**問題 1：啟動後閃退**
- 原因：Admin 提權失敗或 UAC 被 Group Policy 禁用
- 解法：右鍵 → 以系統管理員執行

**問題 2：`ap_key.bin` 找不到**
- 確認 `AP_Key` 資料夾放在 **EXE 同層**，不是 `build/` 或 `dist/dist/`

**問題 3：EXE 被防毒誤判**
- PyInstaller 打包的 EXE 常被 Windows Defender 或防毒軟體誤報
- 解法：加入白名單，或改用 `--onedir`（目錄模式）降低誤判率

**問題 4：打包後路徑錯誤（frozen mode）**
- **已處理**：程式已加入 `get_base_dir()` 函式，透過 `sys.frozen` 偵測是否為 EXE 模式並切換路徑策略，不會再指向 `_MEIPASS` 暫存目錄

---

## 九、更新歷程 (Changelog)

> 格式：`[日期] [工具/AI] 描述`

---

### 2026-08-08 — 初版分析與 Bug Fix（Antigravity / Claude Sonnet 4.6）

#### 分析過程
1. 完整閱讀 `BusHound.py`（644 行），理解整體架構
2. 識別 GUI 兩個 Tab 的職責劃分：Tab1 = 原生 16-byte SCSI，Tab2 = 64-byte VUC 廠商指令
3. 梳理 AP_KEY 認證序列（3 步）與 VUC 主體序列（3 步）的指令邏輯
4. 發現 5 個 Bug，記錄於第五節

#### 已修復

**BUG-2 fix**（高危，`t2_execute` NameError）
- **問題**：`lock_enabled` 在 `try` 區塊內第 513 行才賦值，若在賦值前拋出例外，`finally` 執行 `if lock_enabled:` 會觸發 `NameError`，覆蓋掉原始例外，極難 debug
- **修正**：在函式頂部（`handle = None` 之後）加一行 `lock_enabled = False`，確保 `finally` 任何情況下都能安全存取
- **位置**：`t2_execute()` Line ~501

**BUG-5 fix**（AP_KEY 路徑搜尋邏輯改寫）
- **問題原始設計**：`os.path.join("AP_Key", "ap_key.bin")` 為 CWD 相對路徑，從 IDE 或桌面捷徑啟動時 CWD 不是腳本目錄，會直接 return 失敗且只顯示路徑字串
- **使用者追加需求**：優先自動搜尋附近目錄，找不到才讓使用者手動匯入路徑
- **修正後邏輯**（按優先順序）：
  1. `os.path.dirname(os.path.abspath(__file__))` → 腳本所在目錄
  2. `os.getcwd()` → 當前工作目錄
  3. 腳本的上一層目錄
  4. 以上皆無 → 彈出 `filedialog.askopenfilename()` 讓使用者手動選擇 `.bin`
  5. 使用者取消選擇 → log 提示並 `return`，不繼續執行
- **位置**：`t2_execute()` Line ~535

#### 尚未處理（待後續修復）
- **BUG-1**：`if handle` 語意不嚴謹（低危，實際不出問題）
- **BUG-3**：純解鎖模式 return 後磁碟立即解鎖的行為需業務確認
- **BUG-4**：`t2_load_64b_bin()` offset 40-43 硬編碼解析無上限保護
- **潛在**：`SCSI_PASS_THROUGH_DIRECT` 無 `_pack_` alignment 設定，遇 Error 87 時優先懷疑

#### 本次新增檔案
- `SKILL.md`（本文件）：放置於 `BusHound/` 專案目錄根，供後續 AI 快速上手

---

### 2026-08-08 Session 2 — 尚未處理清單全數修復（Antigravity / Claude Sonnet 4.6）

#### 分析過程
1. 重新閱讀程式碼確認 BUG-1、3、4 與 Alignment 問題的精確位置與影響範圍
2. 針對 BUG-3 確認業務語意：「純解鎖模式後磁碟是否應保持鎖定」→ 結論：讓使用者自己決定，加 Checkbox
3. 針對 BUG-4 確認 offset 40-43 的硬編碼邏輯無法判斷是否符合當前 payload 格式 → 結論：加上限保護 + 使用者確認視窗

#### 已修復

**BUG-1 fix**（Handle 判斷語意改善 + FormatMessageW 人類可讀錯誤訊息）
- 新增 `INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value` 常數
- `open_drive()` 改成 `if handle == INVALID_HANDLE_VALUE or handle is None`
- `raise PermissionError(f"Open Failed [{code}]: {get_win_error_msg(code)}")`
- 新增 `get_win_error_msg(code)` 函式，使用 `FormatMessageW` 轉換錯誤碼為字串
- `send_scsi_command()` 的 IOCTL 失敗也一同改用人類可讀格式
- `finally` 區塊改為 `if handle is not None`

**BUG-3 fix**（純解鎖模式後磁碟鎖定行為由使用者決定）
- 新增 `self.t2_keep_lock_var = tk.BooleanVar(value=False)`
- UI 加入 `Checkbutton(text="Keep Lock (純解鎖後維持鎖定)")` （預設 False，即維持原行為解鎖）
- 純解鎖模式 `return` 前，若 `keep_lock_var=True` 則將 `lock_enabled = False`，使 `finally` 跳過 `unlock_drive`
- 同時在 log 中提示「請記得手動關閉程式以解鎖」

**BUG-4 fix**（offset 40-43 自動解析加上限保護與使用者確認）
- 新增全域常數 `MAX_TRANSFER_BYTES = 256 * 1024 * 1024`（256MB）
- 解析流程改為三段：
  1. `transfer_length > MAX_TRANSFER_BYTES` → log 警告，略過填入
  2. `0 < transfer_length <= MAX_TRANSFER_BYTES` → 彈出 `messagebox.askyesno()` 顯示 raw value 與計算結果讓使用者確認
  3. 使用者拒絕 → log 提示，不填入

**Alignment fix**（`SCSI_PASS_THROUGH_DIRECT` 結構體對齊）
- 加上 `_pack_ = 4`，與 Windows WDK 頭文件行為一致
- 同時加上說明注解記錄各欄位累積 size 與對齊分析
- 解決潛在的 IOCTL Error 87 (Invalid Parameter) 問題

#### 尚未處理
- 無。所有已知 Bug 均已修復。

#### 本次修改檔案
- `BusHound.py`：共修改 8 處，涵蓋常數定義、結構體、`open_drive()`、`send_scsi_command()`、`init_tab2_64byte()`、`t2_load_64b_bin()`、`t2_execute()` pure-unlock return 路徑、`finally` 區塊
- `SKILL.md`（本文件）：加入 Session 2 changelog

---

### 2026-08-08 Session 3 — EXE 打包支援（Antigravity / Claude Sonnet 4.6）

#### 需求
使用者需要將程式打包成 EXE 並確保：
1. 執行時不跳出 CMD 黑視窗
2. 另一台電腦上的 AI 也能按照文件完成安裝與打包

#### 發現的新問題

**Packaging Bug：frozen 模式下 AP_Key 路徑錯誤**
- PyInstaller `--onefile` 打包後，`__file__` 指向 `_MEIPASS` 暫存解壓目錄（例如 `C:\Users\xxx\AppData\Local\Temp\_MEI12345\BusHound.py`）
- 導致 `os.path.dirname(os.path.abspath(__file__))` 指向暫存目錄，而非 EXE 旁邊的資料夾
- 搜尋 `AP_Key\ap_key.bin` 永遠找不到，會直接跳到 filedialog

#### 已修復

**Packaging fix：新增 `get_base_dir()` helper 函式**
- 位置：`BusHound.py` 頂部（import 之後，常數定義之前）
- 邏輯：
  ```python
  def get_base_dir():
      if getattr(sys, 'frozen', False):
          return os.path.dirname(sys.executable)  # EXE 模式
      return os.path.dirname(os.path.abspath(__file__))  # .py 執行
  ```
- `sys.frozen` 由 PyInstaller 在打包 EXE 啟動時自動設為 `True`
- `sys.executable` 在 EXE 模式下指向 `.exe` 本身路徑，`os.path.dirname()` 即為 EXE 所在目錄
- AP_Key 搜尋邏輯改為呼叫 `get_base_dir()` 取代 `os.path.dirname(os.path.abspath(__file__))`

#### 文件新增

**SKILL.md 第八節：打包成 EXE（PyInstaller 指南）**，包含：
- 完整依賴清單（stdlib only，不需要任何 pip 套件）
- PyInstaller 安裝指令
- 打包指令與旗標說明（`--onefile --windowed` 消除黑視窗）
- 輸出目錄結構說明
- 部署目標電腦所需檔案清單
- 目標電腦執行環境要求
- 四個常見打包問題排查指南

#### 本次修改檔案
- `BusHound.py`：新增 `get_base_dir()` 函式 + AP_Key 搜尋改用 `base_dir`
- `SKILL.md`（本文件）：新增第八節打包指南 + Session 3 changelog
