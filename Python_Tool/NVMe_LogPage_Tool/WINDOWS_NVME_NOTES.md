# Windows NVMe 工具開發與除錯經驗紀錄

本文件記錄了在開發 `NVMe_LogPage_Tool` 時，針對 Windows 作業系統底層硬體存取（Win32 IOCTL）所遇到的坑、解法，以及單元測試的最佳實踐。

## 1. 裝置存取權限與 Handle 開啟策略

在 Windows 存取實體磁碟 (`\\.\PhysicalDriveN`) 時，`CreateFileW` 的 `DesiredAccess` 參數決定了你能做什麼操作：

- **裝置掃描 (無須管理員權限)**：
  若僅需列舉硬碟、取得型號、序號 (`IOCTL_STORAGE_QUERY_PROPERTY`) 與容量 (`IOCTL_DISK_GET_DRIVE_GEOMETRY`)，`DesiredAccess` 必須設為 `0`。
- **NVMe 直通指令 (需要管理員權限)**：
  若要發送 `IOCTL_STORAGE_PROTOCOL_COMMAND` (Pass-Through)，`DesiredAccess` 必須為 `GENERIC_READ | GENERIC_WRITE`。如果無管理員權限，`CreateFileW` 會直接回傳 `ERROR_ACCESS_DENIED (5)`。
- **Error 87 陷阱 (參數錯誤)**：
  如果程式試圖以「唯讀」權限開啟 Handle，卻向該 Handle 發送 `IOCTL_STORAGE_PROTOCOL_COMMAND`，Windows 核心的 `StorNVMe` 驅動會直接拒絕並回傳 `ERROR_INVALID_PARAMETER (87)`。

## 2. STORAGE_PROTOCOL_COMMAND 結構與嚴格限制

Windows 對 NVMe Pass-Through 結構體的驗證極為嚴格，欄位只要錯一個就會導致 BSOD 或是 Error 87：

- `Version` 必須設定為 `1` (`STORAGE_PROTOCOL_STRUCTURE_VERSION`)。
- `Flags` 必須包含 `0x80000000` (`STORAGE_PROTOCOL_COMMAND_FLAG_ADAPTER_REQUEST`)，這指示驅動程式將指令直接送到實體裝置。
- `CommandSpecific` 必須為 `1`，代表這是 NVMe Admin Command (若是 NVM 指令則為不同的常數)。
- **CDW10~CDW15** 必須正確對齊 NVMe Spec。請求的返回資料大小必須對齊 4 bytes (Dword)。

## 3. 雙通道驅動設計 (Dual-Channel Fallback)

為了最大化硬體相容性（尤其是應對某些不支援原生 Pass-Through 的 USB NVMe 轉接盒或特規驅動），本專案實作了降級機制：

1. **優先嘗試 Pass-Through**：使用 `IOCTL_STORAGE_PROTOCOL_COMMAND`。這能取得最完整的 Log Page。
2. **自動降級至 Query Property**：若失敗，改用 `IOCTL_STORAGE_QUERY_PROPERTY` 搭配 `StorageAdapterProtocolSpecificProperty` (PropertyId=49 / 50)。這是 Windows 提供的捷徑，可用來抓取基礎的 SMART / Health Log。

## 4. ctypes 與單元測試 (Mocking Win32 API)

撰寫 `unittest.mock` 來攔截 `DeviceIoControl` 時，必須注意 `ctypes` 物件的記憶體操作：

- **記憶體寫入方式**：
  Mock 函數收到的是 Python 的 `ctypes` Array 物件。不要試圖直接修改 `.raw` (對 `c_byte` 陣列無效會拋錯)，應使用 `ctypes.memmove` 來安全的寫入記憶體：
  ```python
  # 錯誤示範
  out_buf.raw = data.ljust(out_size, b'\x00')
  
  # 正確示範
  ctypes.memmove(ctypes.addressof(out_buf), data, len(data))
  ```

## 5. PyInstaller 打包陷阱 (--windowed)

將包含 `print()` 的 Python CLI / GUI 混用程式打包為隱藏終端機的執行檔時：
- **`sys.stdout` 與 `sys.stderr` 為 None**：
  在 `--windowed` 模式下，由於沒有 Console，Python 標準輸出流為 `None`。只要執行到 `print()` 就會觸發 `AttributeError: 'NoneType' object has no attribute 'write'`，導致程式瞬間閃退。
- **解法**：在 `main.py` 最頂端將缺失的輸出流重新導向至 `os.devnull`。
  ```python
  import sys, os
  if sys.stdout is None:
      sys.stdout = open(os.devnull, 'w')
  if sys.stderr is None:
      sys.stderr = open(os.devnull, 'w')
  ```

## 6. CSV 解析的強健性

- **BOM 與編碼**：Windows 上以 Excel 建立的 CSV 常帶有 `\ufeff` BOM 標籤。使用 `utf-8-sig` 讀取可自動過濾。
- **內嵌註解**：使用者可能在 CSV 中加入 `#` 進行註解。必須在解析 Row 之前先進行 `line.split('#')[0]` 清理，以避免被識別為錯誤的 NSID 或 LID。
