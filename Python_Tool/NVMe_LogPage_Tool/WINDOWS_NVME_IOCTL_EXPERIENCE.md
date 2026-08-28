# Windows NVMe 底層通訊、IOCTL 與單元測試實戰經驗全紀錄

本文件完整記錄在 Windows 平臺開發 NVMe Get Log Page 工具、對接微軟 `stornvme.sys` 與各家 OEM/Intel NVMe Miniport 驅動時所累積的底層除錯經驗、通訊架構與 33 項單元測試設計規範。

---

## 一、Windows NVMe 驅動架構與通訊通道

在 Windows 環境下與 NVMe 裝置直接通訊主要有三大通道，程式實作了**三重通道自動降級與路由機制**：

```
+-------------------------------------------------------------------------------+
|                             NVMe Log Page Tool                                |
+-------------------------------------------------------------------------------+
       |                               |                              |
       v                               v                              v
[通道 1: Protocol-Query]     [通道 2: Pass-Through]       [通道 3: Miniport Pass-Through]
IOCTL_STORAGE_QUERY_PROPERTY  IOCTL_STORAGE_PROTOCOL_COMMAND  IOCTL_SCSI_MINIPORT
(0x002D1400)                  (0x002DD3C0)                    (0x0004D008)
       |                               |                              |
       v                               v                              v
  stornvme.sys                    stornvme.sys                Intel RST / VMD / OEM
(微軟原生驅動查詢介面)          (微軟標準 NVMe SQE 直通)      (IaNVMe / SecNvme 私有介面)
```

---

## 二、關鍵 Windows Error Code 與根因對策

| Windows Error Code | 錯誤常數 | 常見原因 (Root Cause) | 解決方案與程式碼對策 |
| :--- | :--- | :--- | :--- |
| **87** | `ERROR_INVALID_PARAMETER` | 1. **`ProtocolType` 誤設為 1 (SCSI)**：Windows SDK `STORAGE_PROTOCOL_TYPE` 定義 `ProtocolTypeNvme = 3`（1 為 SCSI、2 為 ATA）。<br>2. `STORAGE_PROTOCOL_COMMAND` 記憶體排版缺少 64B `ErrorInfo` 空間。<br>3. `DataFromDeviceBufferOffset` 偏移量不正確。<br>4. NVMe 傳輸長度小於硬體限制（需向上對齊至 512B）。 | 1. **修正 `PROTOCOL_TYPE_NVME = 3`**。<br>2. 保留 `[144..207]` 64 Bytes 錯誤日誌緩衝區。<br>3. 資料區偏移設定為 `208`。<br>4. 建立策略矩陣依序嘗試 `Length=84/80/144` 與 `Flags`。 |
| **1117** | `ERROR_IO_DEVICE` | 1. **`ProtocolType` 誤設為 1 (SCSI)**：NVMe 驅動發現請求 Protocol 非 NVMe 直接拒絕。<br>2. `IOCTL_STORAGE_QUERY_PROPERTY` 輸入緩衝區大小非 48 Bytes。<br>3. 請求資料長度超過該 Log Page 的硬體最大長度。 | 1. **修正 `PROTOCOL_TYPE_NVME = 3`**。<br>2. `cbInBuffer` 嚴格限制為 **48 Bytes**。<br>3. `ProtocolDataLength` 精確設定為 512 Bytes。 |
| **5** | `ERROR_ACCESS_DENIED` | 開啟 `\\.\PhysicalDriveN` 時未具備系統管理員權限。 | 1. 執行檔 manifest 加入 `requireAdministrator` (`--uac-admin`)。<br>2. 透過 `ShellExecuteW` 動詞 `"runas"` 自動觸發 UAC 提權。 |
| **1** | `ERROR_INVALID_FUNCTION` | `IOCTL_SCSI_MINIPORT` 僅支援發送給 Adapter 控制器 Handle，發給 `\\.\PhysicalDriveN` 被拒絕。 | 自動探測開啟 `\\.\Scsi0:` ~ `\\.\Scsi3:` 介面作為備用通道發送。 |

---

## 三、微軟 StorNVMe 緩衝區記憶體佈局規範

### 1. `IOCTL_STORAGE_PROTOCOL_COMMAND` (0x002DD3C0) 標準排版
微軟核心驅動 `stornvme.sys` 要求記憶體連續排列如下：

```
Offset 0       Offset 80      Offset 144     Offset 208                  Offset 208+N
+--------------+--------------+--------------+---------------------------+
| SPC Header   | NVMe SQE     | ErrorInfo    | Data Transfer Buffer      |
| (80 Bytes)   | (64 Bytes)   | (64 Bytes)   | (N Bytes, Min 512 Bytes)  |
+--------------+--------------+--------------+---------------------------+
```

- **結構欄位關鍵賦值**：
  - `Version = 1`
  - `Length = 84` (或 `sizeof(STORAGE_PROTOCOL_COMMAND)`)
  - `ProtocolType = 3` (`ProtocolTypeNvme`)
  - `Flags = 0x80000000` (`STORAGE_PROTOCOL_COMMAND_FLAG_ADAPTER_REQUEST`)
  - `CommandLength = 64`
  - `ErrorInfoLength = 64`
  - `ErrorInfoOffset = 144`
  - `DataFromDeviceTransferLength = max(aligned_length, 512)`
  - `DataFromDeviceBufferOffset = 208`
  - `CommandSpecific = 1` (`STORAGE_PROTOCOL_SPECIFIC_NVME_ADMIN_COMMAND`)

### 2. `IOCTL_STORAGE_QUERY_PROPERTY` (0x002D1400) 標準排版
- **輸入緩衝區 (`inBuffer`)**：大小固定為 **48 Bytes**
  - `[0..7]`：`STORAGE_PROPERTY_QUERY` (`PropertyId=50` 或 `49`, `QueryType=0`)
  - `[8..47]`：`STORAGE_PROTOCOL_SPECIFIC_DATA` (`ProtocolType=3`, `DataType=2`, `LID`, `ProtocolDataOffset=40`, `ProtocolDataLength=512`)
- **輸出緩衝區 (`outBuffer`)**：大小為 **48 + ProtocolDataLength**
  - `[0..47]`：`STORAGE_PROTOCOL_DATA_DESCRIPTOR`
  - `[48..]`：NVMe 回傳之原始日誌資料（實際資料起始點為 `8 + outBuffer[24]`）

---

## 四、NVMe Get Log Page 指令 CDW 編碼與 NUMD 規範

| 暫存器 | 欄位定義 | 組合方式 (Python) | 說明 |
| :--- | :--- | :--- | :--- |
| **CDW0** | `OPC` (0x02) | `0x02` | Admin Opcode: Get Log Page |
| **CDW1** | `NSID` | `0xFFFFFFFF` (或 `0`) | 全域日誌（如 SMART）使用 `0xFFFFFFFF` |
| **CDW10** | `NUMDL[31:16]`<br>`RAE[15]`<br>`LSP[11:8]`<br>`LID[7:0]` | `((numd & 0xFFFF) << 16) \| ((rae & 1) << 15) \| ((lsp & 0xF) << 8) \| (lid & 0xFF)` | `Data Length = (NUMD + 1) * 4 Bytes` |
| **CDW11** | `NUMDU[15:0]` | `(numd >> 16) & 0xFFFF` | 超過 64K Dwords 時的高位傳輸長度 |
| **CDW12** | `LPOL[31:0]` | `lpo & 0xFFFFFFFF` | Log Page Offset 低 32 位 |
| **CDW13** | `LPOU[31:0]` | `(lpo >> 32) & 0xFFFFFFFF` | Log Page Offset 高 32 位 |

### CSV 輸入欄位支援 NUMD（16 進位 / 10 進位 / 單位）
- `7F` 或 `0x7F` $\rightarrow$ NUMD = 127 $\rightarrow$ 資料長度 = **512 Bytes**
- `FF` 或 `0xFF` $\rightarrow$ NUMD = 255 $\rightarrow$ 資料長度 = **1024 Bytes**
- `01` 或 `0x01` $\rightarrow$ NUMD = 1 $\rightarrow$ 資料長度 = **8 Bytes**
- `00` 或 `0x00` $\rightarrow$ NUMD = 0 $\rightarrow$ 資料長度 = **4 Bytes** (最小 Dword)
- `3FF` 或 `0x3FF` $\rightarrow$ NUMD = 1023 $\rightarrow$ 資料長度 = **4096 Bytes**
- `4KB` 或 `512B` $\rightarrow$ 自動換算對應 NUMD


---

## 五、33 項自動化單元測試架構

本專案建立了包含 33 項自動化單元測試的完整驗證套件（涵蓋所有核心模組與異常邊界條件）：

```
tests/
├── test_commands.py       (4 項): CDW10~CDW13 暫存器組合、4-Byte Dword 對齊、NUMD 計算
├── test_parsers.py        (4 項): SMART 欄位解析、非列印字元過濾、Hex Dump 雙欄格式化
├── test_csv_parser.py     (7 項): HEX/DEC 自動識別、4KB/64K 單位解析、BOM 移除、行內註解
├── test_win_ioctl.py      (3 項): PhysicalDrive Handle 開啟、權限不足異常處理
├── test_nvme_driver.py    (5 項): SPC 結構驗證、雙通道降級切換、資料裁切至請求長度
├── test_device_scanner.py (2 項): NVMe BusType 17 過濾、降級容錯邏輯
├── test_batch_runner.py   (3 項): 批次執行流程、遇錯停止 (STOP) 策略、手動取消中斷
├── test_reporter.py       (2 項): .bin / .hex / .json 輸出檔產出、summary.csv 彙整統計
└── test_cli.py            (3 項): CLI --scan, --csv, --lid 參數解析與執行
```

### 關鍵 Mock 測試技巧
- **非侵入式 Win32 API Mock**：透過 `unittest.mock.patch("core.nvme_driver.device_io_control")` 模擬 Windows 核心的 `DeviceIoControl` 呼叫。
- **記憶體位元組模擬**：在 Mock 函式中直接透過 `ctypes.memmove` 與 `struct.pack_into` 模擬真實 NVMe 驅動回傳的 binary buffer。
- **多通道降級測試**：透過在 Mock 中針對不同 IOCTL Code (`0x002DD3C0`, `0x002D1400`, `0x0004D008`) 回傳不同成功/失敗結果，精確驗證驅動層的 fallback 機制。

---

## 六、打包與發布注意事項 (PyInstaller)

1. **強制管理員身分**：
   打包時必須帶入 `--uac-admin`，確保產生之 EXE 具有 `requireAdministrator` 的 Application Manifest，否則直接被作業系統拒絕存取 PhysicalDrive。
2. **靜態資源打包**：
   使用 `--add-data "test_cases;test_cases"` 將預設 CSV 測試腳本內嵌至二進位檔案。
3. **視窗模式**：
   使用 `--windowed` 關閉控制台黑視窗，透過自建之 GUI (Tkinter) 與多執行緒後台非阻塞執行。
