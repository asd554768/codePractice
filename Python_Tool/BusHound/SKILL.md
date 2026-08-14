---
name: BusHound Python Storage Debug Tool
description: >
  知識文件：用於理解、除錯與擴充 BusHound.py —— 一個以 Python + tkinter 實作的
  Windows SCSI/VUC 除錯工具，功能對標商業軟體 BusHound。
  當你需要修改、debug 或新增功能到此專案時，必須先讀此文件。
---

# BusHound.py — AI 知識總結

## 📑 目錄規劃 (Table of Contents)
- [一、專案目的與架構概述](#一專案目的與架構概述)
- [二、核心技術棧](#二核心技術棧)
- [三、GUI 與邏輯解析](#三gui-與邏輯解析)
- [四、VUC (64-byte) 實務流程解析](#四vuc-64-byte-實務流程解析)
- [五、已知缺陷與潛在 Bug (已修復/待修復)](#五已知缺陷與潛在-bug-已修復待修復)
- [六、除錯工具與技巧](#六除錯工具與技巧)
- [七、給後續 AI 的開發建議](#七給後續-ai-的開發建議)
- [八、打包成 EXE（PyInstaller 指南）](#八打包成-exepyinstaller-指南)
- [九、更新歷程 (Changelog)](#九更新歷程-changelog)
- [十、後續功能規劃與研究方向](#十後續功能規劃與研究方向)

## 📖 建議下次閱讀順序 (Suggested Reading Order for AI)
> 如果你是剛接手這個專案的 AI，強烈建議按照以下順序閱讀此文件，以便最快進入狀況：
> 1. **⚠️【強制規範】每次修改/更新程式碼後，必須執行單元測試**：`python -m unittest discover -s tests -p "test_*.py"` 確保所有測試 PASS。
> 2. **[十、後續功能規劃與研究方向](#十後續功能規劃與研究方向)**：特別是 **10.7 尚未完成清單 (TODO)**，這是你當前的首要任務目標。
> 3. **[九、更新歷程 (Changelog)](#九更新歷程-changelog)**：了解前幾個 Session 已經完成的事項（包含後端分離、PacketLogger 實作與各種 Bug 修復），避免重複造輪子。
> 4. **[一、專案目的與架構概述](#一專案目的與架構概述)**：快速掌握專案目錄結構與職責劃分（`BusHound.py`、`backend_storage.py`、`test_backend.py`、`test_gui.py`）。
> 5. **[四、VUC (64-byte) 實務流程解析](#四vuc-64-byte-實務流程解析)**：若你的任務涉及發送 SCSI 或 NVMe 實體指令，請務必了解其通訊與上鎖機制。
> 6. 若有打包需求，再閱讀 **[八、打包成 EXE](#八打包成-exepyinstaller-指南)**。


## 一、專案目的與架構概述

**目的**：模擬商業工具 BusHound，讓工程師能在 Windows 上透過 Python 直接對實體磁碟（PhysicalDrive）發送 SCSI / Vendor Unique Command (VUC)，並觀察回應資料與 Sense Data。

**執行環境**：
- 作業系統：Windows（強制需要 Admin 權限，啟動時自動 UAC 提權）
- Python：3.x，依賴 `tkinter`, `ctypes`, `subprocess`, `os`
- 完全無外部 pip 套件依賴

**檔案結構（目前）**：
```
BusHound/
  src/
    BusHound.py        # 主程式，純 GUI 邏輯
    backend_storage.py # 後端存取核心（IOCTL, SCSI Pass-Through, 協定解析, PacketLogger）
    __init__.py
  tests/
    test_backend.py    # 後端單元測試套件（23 項測試）
    test_gui.py        # GUI 邏輯與安全邊界單元測試（5 項測試）
    __init__.py
  AP_Key/
    ap_key.bin         # (執行時動態需要) AP_KEY 認證金鑰二進位檔，需自行放置
  SKILL.md             # 專案知識庫與開發手冊（本文件）
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

- [ ] **⚠️【強制規範】更新程式碼後，必須執行單元測試確認全數通過：**
  ```powershell
  python -m unittest discover -s tests -p "test_*.py"
  ```
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
# 切換到專案根目錄
cd "C:\Users\asd55\OneDrive\桌面\code\myGit\codePractice\Python_Tool\BusHound"

# 打包（單一 EXE，無 CMD 視窗，加入 src 模組搜尋路徑）
pyinstaller --onefile --windowed --paths src --name BusHound src/BusHound.py
```

**關鍵旗標說明**：

| 旗標 | 作用 |
|---|---|
| `--onefile` | 所有檔案壓縮成單一 `.exe`，方便散布 |
| `--windowed` / `--noconsole` | **不跳出 CMD 黑視窗**（兩者等效，擇一即可） |
| `--paths src` | **指定模組搜尋路徑**（確保 `backend_storage.py` 被納入打包） |
| `--name BusHound` | 輸出 EXE 名稱 |

**加入圖示（可選）**：
```powershell
pyinstaller --onefile --windowed --paths src --name BusHound --icon icon.ico src/BusHound.py
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

---

### 2026-08-08 Session 4 — 功能規劃、後端分離與封包錄製研究

#### 完成項目

**架構重構：後端分離**
- 將 BusHound.py 內的所有後端邏輯（Windows API 常數、結構體、SCSI 函式、協定解析）移至獨立的 `backend_storage.py`
- `BusHound.py` 改為 `from backend_storage import *`，負責純 GUI 邏輯
- `backend_storage.py` 新增 `PacketLogger` class（見下方說明）

**新增 PacketLogger（backend_storage.py）**
- Thread-safe 的自發指令記錄器，掛鉤在 `send_scsi_command()` 內
- 每次 IOCTL 回傳後自動記錄：index、timestamp（毫秒精度）、drive、direction、CDB hex、cmd_name（解析後）、data_len、**完整 payload hex**、scsi_status、sense_str、elapsed_ms
- 支援 callback 機制，GUI 可即時收到每筆記錄
- 支援 `export_csv()` 匯出所有記錄
- 透過 `packet_logger.enable()` / `disable()` 控制

**注意**：`send_scsi_command()` 新增了 `drive_label="?"` 參數，呼叫端需傳入磁碟名稱字串（如 `"PhysicalDrive1"`），否則記錄欄位顯示 `?`。後續修改 Tab1 / Tab2 呼叫時需補上此參數。

---

### 2026-08-15 Session 5 — PowerShell 磁碟列舉修復 & drive_label 補齊（Antigravity / Claude Sonnet 4.6）

#### 分析過程
1. 重新完整閱讀 `BusHound.py`（493 行）與 `backend_storage.py`（353 行）
2. 使用 `python -m py_compile` 靜態語法檢查，發現 `SyntaxWarning: invalid escape sequence '\.'`
3. 實際執行 PowerShell 命令驗證：原始指令語法錯誤，修正後成功輸出磁碟列表
4. 確認 Session 4 留下的 `drive_label` TODO 尚未完成，本次一併補齊

#### 已修復

**BUG-6：`get_physical_drives()` 的 PowerShell 指令語法錯誤（backend_storage.py L144）**
- **根本原因（雙層問題）**：
  1. Python 層：字串 `"\.Index"` 中的 `\.` 是 Python 無效 escape sequence（SyntaxWarning），Python 實際傳給 shell 的字串是 `.Index, .Model`（反斜線被丟棄）
  2. PowerShell 層：收到 `.Index, .Model` 無法識別（需要 `$_.Index`），拋出 `ParserError`，subprocess 靜默失敗 → `get_physical_drives()` 進入 `except` 回傳 fallback `["PhysicalDrive0"..."PhysicalDrive7"]`，磁碟型號完全消失
- **症狀**：下拉選單只顯示 `PhysicalDrive0`~`PhysicalDrive7`，沒有型號資訊（`- CT500MX500SSD1` 等）
- **修正**：`\.Index, \.Model` → `$_.Index, $_.Model`
- **驗證**：直接執行修正後的 PowerShell 指令，成功輸出 `1:::CT500MX500SSD1`、`2:::INTEL SSDPEKNU512GZ`、`0:::SATA SSD`

**drive_label 補齊（BusHound.py，7 處）**
- **背景**：Session 4 新增 `PacketLogger` 時，`send_scsi_command()` 加了 `drive_label="?"` 可選參數，但所有 GUI 呼叫端都沒有傳入，導致 PacketLogger 記錄的 `drive` 欄位永遠是 `"?"`
- **修正位置**（7 處）：
  - Tab 1 `t1_execute()`：L164 補 `drive_label=f"PhysicalDrive{dnum}"`
  - Tab 2 `t2_execute()` AP_KEY 序列：L391（cmd1）、L396（cmd2）、L401（cmd3）
  - Tab 2 `t2_execute()` VUC 序列：L426（VUC1）、L456（VUC2）、L470（VUC3）
- **變數名稱注意**：Tab 1 用 `dnum`，Tab 2 用 `drive_num`，兩者均直接來自 `drive_combo.get()` 解析

#### 本次修改檔案
- `backend_storage.py`：L143~144，修復 PowerShell `$_` 變數語法
- `BusHound.py`：7 處 `send_scsi_command()` 呼叫補上 `drive_label`
- `SKILL.md`（本文件）：新增 Session 5 changelog + 更新 TODO 狀態

---

### 2026-08-15 Session 6 — 目錄分類重構、單元測試套件建置與打包路徑修復（Antigravity / Gemini 3.7 Flash & Claude Sonnet 4.6）

#### 完成項目與分析

1. **目錄結構分類重構**：
   - 建立 `src/` 資料夾：移入 `BusHound.py`、`backend_storage.py`、`__init__.py`。
   - 建立 `tests/` 資料夾：移入 `test_backend.py`、`test_gui.py`、`__init__.py`。
   - 建立 `AP_Key/` 資料夾供放置認證金鑰。
   - 測試檔案頂部加入 `sys.path.insert(0, ...)` 指向 `../src`，確保任意目錄執行皆能正確 import。

2. **完整單元測試套件建置（28 項測試全數 PASS）**：
   - [`tests/test_backend.py`](file:///c:/Users/asd55/OneDrive/桌面/code/myGit/codePractice/Python_Tool/BusHound/tests/test_backend.py)：涵蓋 ctypes 結構體大小、CDB / Sense Data 解析、hexdump 格式化、Win32 錯誤碼解析、PowerShell 磁碟列舉 mock、PacketLogger 記錄/Callback/CSV 匯出、以及 Mock `DeviceIoControl` 傳輸與磁碟鎖定（23 項測試）。
   - [`tests/test_gui.py`](file:///c:/Users/asd55/OneDrive/桌面/code/myGit/codePractice/Python_Tool/BusHound/tests/test_gui.py)：涵蓋 16-Byte / 64-Byte 矩陣清空、Offset 40~43 長度自動計算確認/略過、以及超大長度 (> 256MB) 安全上限攔截（5 項測試）。
   - **強制規範確立**：於 `SKILL.md` 確立「每次修改程式碼後必須執行單元測試」規範。

3. **重要修復：`SCSI_PASS_THROUGH_DIRECT` 記憶體對齊修正**：
   - **問題**：`backend_storage.py` 原設定 `_pack_ = 4` 導致 64-bit 指標強制被 4-byte 對齊，結構體大小變為 48 Bytes 且 `DataBuffer` 偏移量錯誤 (offset 20)。
   - **修復**：移除 `_pack_ = 4`，恢復 64-bit Windows WDK 自然 8-byte 對齊，結構體大小為 56 Bytes，`DataBuffer` 正確對齊 offset 24。

4. **PyInstaller 打包 Bug 修復（ModuleNotFoundError: backend_storage）**：
   - **根本原因**：目錄拆分為 `src/` 後，PyInstaller 在根目錄執行時預設未將 `src/` 納入搜尋路徑，且 `BusHound.py` 未將同層目錄注入 `sys.path`，導致 `backend_storage.py` 未被包入 EXE 內部。
   - **修復措施**：
     - `src/BusHound.py` 頂部加入 `_current_dir` 自動注入 `sys.path`。
     - 打包指令加入 `--paths src` 旗標：`pyinstaller --onefile --windowed --paths src --name BusHound src/BusHound.py`。
     - UAC 提權在 frozen 模式下避免傳入無效 script 參數 (`params = None if getattr(sys, 'frozen', False) else ...`)。
   - **產出物更新**：成功重新生成 `dist/BusHound.exe` 並更新至 `BusHound.7z`。

#### 本次修改檔案
- `src/BusHound.py`：加入 `_current_dir` 至 `sys.path`、優化 frozen 模式 UAC 入口點
- `src/backend_storage.py`：移除 `_pack_ = 4` 修正 64-bit 結構體對齊
- `tests/test_backend.py`：建立後端單元測試套件
- `tests/test_gui.py`：建立 GUI 邏輯單元測試套件
- `dist/BusHound.exe` & `BusHound.7z`：重新封裝並更新無黑視窗版本
- `SKILL.md`：記錄 Session 6 Changelog、更新目錄結構、測試指令與打包指令

---



> 下次 AI 接手時，請先讀此節，從「尚未完成」清單挑選目標繼續。

### 10.1 封包錄製（Packet Sniffer Tab）— 架構設計

目標：新增 Tab 3「Packet Sniffer」，提供即時封包記錄與監控。

#### 實現方式分析

| 技術 | 適用對象 | Payload 完整性 | 複雜度 | 需額外安裝 |
|---|---|---|---|---|
| **PacketLogger（已實作）** | BusHound 自發的指令 | ✅ 100% 完整 | 低 | 無 |
| **ETW Storport** | 系統全域所有 SCSI/NVMe | ❌ 僅 metadata（CDB、長度、時間） | 中 | 無（Windows 內建）|
| **frida hook** | 指定 PID 的 user-mode 程式 | ✅ 完整（拿到目標 process 的 DeviceIoControl buffer）| 中 | `pip install frida frida-tools` |
| **Kernel Filter Driver** | 系統全域所有 I/O，含核心層 | ✅ 完整（最完整） | 極高 | WDK + EV 簽章，不適合純 Python |

#### 建議實作順序

1. **Phase 1（最優先）**：完成 Tab 3 GUI，整合 PacketLogger，顯示自發指令完整記錄。
2. **Phase 2**：整合 ETW Storport，監聽外部指令的 metadata（CDB + 時間戳記）。
3. **Phase 3（選用）**：整合 frida，可 hook 指定 Process（如 vendor exe）取得完整 Payload。

#### Tab 3 GUI 設計草圖

```
┌─────────────────────────────────────────────────────────┐
│ [▶ Start Logging]  [■ Stop]  [🗑 Clear]  [💾 Export CSV] │
│ ─────────────────────────────────────────────────────── │
│ # | Time      | Drive | Dir | Cmd Name      | Len | ms  │
│ 1 | 10:23:01  | PD1   | IN  | READ(10)      | 512 | 2.3 │
│ 2 | 10:23:02  | PD1   | OUT | VUC/AP_KEY    |  64 | 1.1 │
│ ─────────────────────────────────────────────────────── │
│ 選中封包詳情：                                          │
│   CDB:     28 00 00 00 00 00 00 00 01 00 00 00 00 00... │
│   Payload: 00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D... │
│   Sense:   (none) / Sense Key: NO SENSE                 │
└─────────────────────────────────────────────────────────┘
```

### 10.2 ETW Storport 整合細節

- **Provider GUID**：`{C4636A1E-7986-4646-BF10-7BC3B4A76E8E}`（Microsoft-Windows-StorPort）
- **Python 呼叫方式**：透過 `ctypes` 呼叫 `Advapi32.dll` 的 `StartTraceW` / `EnableTraceEx2` / `OpenTraceW` / `ProcessTrace`，或使用第三方套件 `pywintrace`（`pip install pywintrace`）
- **事件結構**：`EVENT_RECORD` → 解析 `UserData` 欄位，含 SCSI CDB（最多 16 bytes）、Transfer Length、方向、SRB Status
- **重要設定**：必須先在 Event Viewer 啟用 Storport 的 Analytic channel 才能獲取更多事件（預設只有 Operational channel）
- **效能注意**：大量 I/O 時 ETW 會產生極多事件，必須使用 Circular Buffer 模式或限速

### 10.3 frida Hook 整合細節

- **安裝**：`pip install frida frida-tools`
- **原理**：frida 可在 User-mode 動態 hook 目標 process 的 `DeviceIoControl` 函式，在呼叫前後截取 `lpInBuffer` / `lpOutBuffer`（含完整 SPTD 結構與 Payload）
- **限制**：
  - 只能 hook user-mode process（無法看到 OS 核心自身的 I/O）
  - 目標 process 需可被 attach（部分有保護的商業軟體會阻止）
  - frida server 需要與目標 process 相同的 bitness（32/64）
- **使用情境**：Vendor 提供的測試 exe 對磁碟下指令時，可用 frida 攔截完整 SCSI payload

### 10.4 Kernel Filter Driver（備忘，暫不實作）

- **運作層**：插在 Storport 與 miniport 之間，攔截所有 SRB（SCSI Request Block）
- **開發需求**：C/C++ + WDK + Visual Studio + EV Code Signing Certificate
- **簽章方式**：
  - 開發測試：`bcdedit /set testsigning on` + 自簽憑證（僅限開發機）
  - 正式分發：EV 憑證（$300-500 USD/年）+ Microsoft WHQL Portal 簽章
- **Python 橋接**：驅動可透過 Named Pipe 或自訂 IOCTL device 把資料傳回 Python GUI
- **現況評估**：對個人/小團隊開發環境來說門檻過高，除非有明確的量產需求，否則不建議走此路線

### 10.5 NVMe Admin Commands（下一個主要功能）

- **IOCTL**：`IOCTL_STORAGE_PROTOCOL_COMMAND`（值 `0x2D1420`）
- **需要定義的 ctypes 結構體**：
  - `STORAGE_PROTOCOL_COMMAND`（主要命令容器）
  - `STORAGE_PROTOCOL_SPECIFIC_DATA`（協定特定資料）
  - `STORAGE_PROTOCOL_DATA_DESCRIPTOR`（描述符）
- **優先實作的指令**：
  - `Identify Controller`（Opcode `0x06`，CNS=1）→ 取得型號、SN、FW 版本（4096 bytes）
  - `Get Log Page - SMART/Health Info`（Opcode `0x02`，Log ID `0x02`）→ 取得溫度、壽命、錯誤計數
- **GUI 規劃**：新增 Tab 4「NVMe Admin Cmd」，含預設按鈕直接填入 Opcode 參數
- **參考來源**：`smartmontools` 的 `os_win32.cpp` 是 Windows 上 NVMe IOCTL 最完整的開源 C 參考實作

### 10.6 單元測試（Unit Tests）架構與實作

目前已實作完整的單元測試套件（基於 Python 內建 `unittest`），無須額外安裝 pytest 等第三方套件：

1. **後端核心測試 [`test_backend.py`](file:///c:/Users/asd55/OneDrive/桌面/code/myGit/codePractice/Python_Tool/BusHound/test_backend.py)** (共 23 項測試):
   - `TestCtypesStructures`：驗證 64-bit Windows 下 `SCSI_PASS_THROUGH_DIRECT` (56 Bytes) 與 `SENSE_DATA_BUFFER` (24 Bytes) 大小與 8-byte 指標自然對齊。
   - `TestProtocolParsing`：驗證標準 SCSI Opcode 解析、VUC (0x06/0xFE/0xC0~0xC3) 解析、Sense Data (0x70/0x71, Sense Key, ASC/ASCQ) 解析與異常長度保護。
   - `TestHelpers`：驗證 `hexdump` 格式化、`get_win_error_msg` Win32 錯誤轉換、`get_base_dir` 路徑解析，以及 mock PowerShell 磁碟列舉成功與 fallback。
   - `TestPacketLogger`：驗證記錄器開關、記錄格式、GUI Callback 機制、CSV 匯出與清除功能。
   - `TestScsiIoControl`：Mock Win32 `DeviceIoControl` 驗證 Pass-Through 成功、失敗 OSError 拋出、以及磁碟鎖定/解鎖 `FSCTL_LOCK_VOLUME`。

2. **GUI 狀態測試 [`test_gui.py`](file:///c:/Users/asd55/OneDrive/桌面/code/myGit/codePractice/Python_Tool/BusHound/test_gui.py)** (共 5 項測試):
   - `TestGuiLogic`：驗證 Tab 1 / Tab 2 矩陣清空、64-Byte VUC Offset 40~43 長度自動計算與使用者確認/略過邏輯、超大長度 (> 256MB) 安全上限攔截。

**執行所有測試指令**：
```powershell
python -m unittest discover -s tests -p "test_*.py"
```

### 10.7 尚未完成清單（給下一個 AI 的 TODO）

- `[ ]` Tab 3 Packet Sniffer GUI 實作（整合 PacketLogger 顯示）
- `[x]` BusHound.py Tab1 / Tab2 的 `send_scsi_command()` 呼叫補上 `drive_label` 參數（Session 5 完成）
- `[x]` `test_backend.py` / `test_gui.py` 單元測試建置（28 項測試全數通過）
- `[ ]` ETW Storport 整合（Phase 2，可先用 `pywintrace`）
- `[ ]` frida hook 整合（Phase 3，選用）
- `[ ]` NVMe Admin Cmd Tab 4 實作（Identify + SMART）
- `[ ]` 打包指令更新：需將 `backend_storage.py` 一起納入（`--onefile` 模式會自動處理，`--onedir` 需確認）
