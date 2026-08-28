# Windows NVMe 底層通訊、IOCTL、Ring0 MMIO 與驅動實戰經驗全紀錄 (v19)

本文件完整記錄在 Windows 平臺開發 NVMe Get Log Page 工具、對接微軟 `stornvme.sys`、第三方 Miniport 驅動以及基於 `WinRing0` 的 Direct-MMIO 核心直通引擎時所累積的底層除錯經驗、通訊架構與 49 項單元測試設計規範。

---

## 一、Windows NVMe 驅動架構與通訊通道

在 Windows 環境下與 NVMe 裝置通訊具有以下四種通道架構：

```
+---------------------------------------------------------------------------------------------------+
|                                      NVMe Log Page Tool                                           |
+---------------------------------------------------------------------------------------------------+
       |                               |                              |                             |
       v                               v                              v                             v
[通道 1: Direct-MMIO]         [通道 2: Pass-Through]       [通道 3: Protocol-Query]         [通道 4: Miniport Pass-Through]
WinRing0x64.sys (Ring0)       IOCTL_STORAGE_PROTOCOL_CMD   IOCTL_STORAGE_QUERY_PROP         IOCTL_SCSI_MINIPORT
(物理記憶體/Doorbell直敲)     (0x002DD3C0)                 (0x002D1400)                     (0x0004D008)
       |                               |                              |                             |
       v                               v                              v                             v
  PCIe MMIO Doorbell              stornvme.sys                    stornvme.sys                Intel RST / VMD / OEM
(100% 繞過微軟核心改寫)        (微軟標準 NVMe SQE 直通)      (精確 ProtocolDataLength 映射)   (IaNVMe / SecNvme 私有介面)
```

---

## 二、關鍵 Windows Error Code 與根因對策

| Windows Error Code | 錯誤常數 | 常見原因 (Root Cause) | 解決方案與程式碼對策 |
| :--- | :--- | :--- | :--- |
| **87** | `ERROR_INVALID_PARAMETER` | 1. **`ProtocolType` 誤設為 1 (SCSI)**：Windows SDK `STORAGE_PROTOCOL_TYPE` 定義 `ProtocolTypeNvme = 3`（1 為 SCSI、2 為 ATA）。<br>2. `STORAGE_PROTOCOL_COMMAND` 記憶體排版缺少 64B `ErrorInfo` 空間。<br>3. `DataFromDeviceBufferOffset` 偏移量不正確。<br>4. **WinRing0 `ReadPhysicalMemory` 存取了受保護的實體記憶體位址**（Windows 10/11 核心安全防禦隔離機制禁止任意實體記憶體映射）。 | 1. **修正 `PROTOCOL_TYPE_NVME = 3`**。<br>2. 保留 `[144..207]` 64 Bytes 錯誤日誌緩衝區。<br>3. 資料區偏移設定為 `208`。<br>4. 透過 PCI Config Space 直接掃描 NVMe BAR0，並具備優雅降級。 |
| **317** | `ERROR_MR_MID_NOT_FOUND` | **微軟 Storport DMA 限制**：`IOCTL_STORAGE_PROTOCOL_COMMAND` 下發給 `\\.\PhysicalDriveN` 時，若 `DataFromDeviceTransferLength < 512`（例如設為 4B），微軟核心 Storport PRP/DMA 檢查未通過，拋出未映射的 NTSTATUS (Win32 Error 317)。 | 1. DMA 接收緩衝區維持 512B 對齊。<br>2. **使用精確的 Protocol-Query 通道下發自定義長度**。 |
| **6** | `ERROR_INVALID_HANDLE` | **64 位元 ctypes 指標截斷陷阱**：`OpenSCManagerW` 或 `CreateFileW` 回傳 64-bit 指標，但 Python `ctypes` 預設回傳型態為 `c_int` (32-bit)，導致指標高位元被截斷，傳遞給 `CreateServiceW` 被系統判定為無效 Handle。 | 1. 顯式設定所有 Win32 SCM API 的 `argtypes` 與 `restype = wintypes.HANDLE`。<br>2. 優先採用 Windows 原生 `sc.exe create` 與 `sc.exe start` 進行服務註冊，完全免除 ctypes 指標型態異常。 |
| **1275** | `ERROR_DRIVER_BLOCKED` | `WinRing0x64.sys` 驅動被 Windows 11/10 的「記憶體完整性 (HVCI)」或「易受攻擊驅動程式封鎖清單」封鎖。 | 捕捉錯誤碼並引導使用者於 Windows 安全性中心關閉驅動封鎖或使用自定義私有 Opcode 繞過。 |
| **1117** | `ERROR_IO_DEVICE` | 1. **`ProtocolType` 誤設為 1 (SCSI)**：NVMe 驅動發現請求 Protocol 非 NVMe 直接拒絕。<br>2. `IOCTL_STORAGE_QUERY_PROPERTY` 輸入緩衝區大小非 48 Bytes。<br>3. 請求資料長度超過該 Log Page 的硬體最大長度。 | 1. **修正 `PROTOCOL_TYPE_NVME = 3`**。<br>2. `cbInBuffer` 嚴格限制為 **48 Bytes**。<br>3. `ProtocolDataLength` 精確設定為對應傳輸長度。 |
| **5** | `ERROR_ACCESS_DENIED` | 開啟 `\\.\PhysicalDriveN` 或存取 SCM 時未具備系統管理員權限。 | 1. 執行檔 manifest 加入 `requireAdministrator` (`--uac-admin`)。<br>2. 透過 `ShellExecuteW` 動詞 `"runas"` 自動觸發 UAC 提權。 |
| **1** | `ERROR_INVALID_FUNCTION` | `IOCTL_SCSI_MINIPORT` 僅支援發送給 Adapter 控制器 Handle，發給 `\\.\PhysicalDriveN` 被拒絕。 | 自動探測開啟 `\\.\Scsi0:` ~ `\\.\Scsi3:` 介面作為備用通道發送。 |

---

## 三、微軟 Protocol-Query 精確長度映射機理 (重大突破)

### 1. `ProtocolDataLength` 與 CDW10.NUMD 的核心計算公式
- 微軟 `stornvme.sys` 處理 `IOCTL_STORAGE_QUERY_PROPERTY`（`StorageDeviceProtocolSpecificProperty`）時，核心組裝 NVMe SQE 的規則如下：
  $$\text{NUMDL} = \left(\frac{\text{ProtocolDataLength}}{4}\right) - 1$$
- **先前誤區**：若在結構中寫死 `ProtocolDataLength = 512`，微軟核心就會在 SQE CDW10 中填入 $(512 / 4) - 1 = 127 = \text{0x7F}$！
- **正確做法**：
  - 當使用者請求 $1\text{ Dword} = 4\text{ Bytes}$（`NUMD = 0x00`）時，將 `ProtocolDataLength` 精確設為 **`4`**。
  - 微軟核心自動計算：$\text{NUMDL} = (4 / 4) - 1 = \mathbf{0x00}$！
  - 核心組裝出的 NVMe SQE CDW10 即為完美的 **`0x000000F0`**，設備端 100% 收到真實的 `NUMD = 0x00`！

---

## 四、自定義私有 Admin Opcode 穿透機制

- **背景**：微軟 `stornvme.sys` 會針對標準 Admin Opcode `0x02` (Get Log Page) 進行長度審查與對齊介入。
- **解決方案**：
  - NVMe Spec 規範 `0xC0` ~ `0xFF` 為 Vendor Specific Admin Opcodes。
  - 微軟驅動遇到 Vendor Specific Opcode 時，不會進行欄位審查與修改，會 100% 原始透傳至硬體。
  - CSV 支援 3 欄格式（`OPCODE,LID,NUMD`，例如 `0xC0,0xF0,0x00`），實現原始封包穿透。

---

## 五、Direct-MMIO (Ring0) 與 PCI Configuration 掃描技術

1. **PCI Configuration Space 直掃**：
   - 透過 `WinRing0` 直接在 PCIe 匯流排（Bus 0~255, Dev 0~31, Func 0~7）搜尋 NVMe 標準類別碼 `0x010802`。
   - 直接從 PCI 暫存器 Offset `0x10`（BAR0 Low）與 `0x14`（BAR0 High）讀取 100% 精準的 NVMe 實體 BAR0。
2. **Doorbell 門鈴計算**：
   - `Admin SQ0 Tail Doorbell Offset = 0x1000 + (2 * 0 * (4 << CAP.DSTRD))`。
   - 將 64-byte SQE 寫入實體 Host Memory 後，寫入 Doorbell 暫存器觸發硬體執行。

---

## 六、單元測試驗證體系 (49 項測試)

- `test_commands.py` (5 項)：CDW 組合、NUMD 計算與高位傳輸長度。
- `test_parsers.py` (4 項)：SMART 欄位解析與 Hex Dump 格式化。
- `test_csv_parser.py` (9 項)：極簡 2 欄 (LID,NUMD)、3 欄 (OPCODE,LID,NUMD)、BOM 與容錯解析。
- `test_win_ioctl.py` (3 項)：Windows 裝置開啟與錯誤權限處理。
- `test_nvme_driver.py` (15 項)：多通道路由、降級防護、裁切長度驗證與常數回歸。
- `test_mmio_direct.py` (3 項)：PCIe BAR0 探測、暫存器讀取與 SQE 組裝 Doorbell 測試。
- `test_device_scanner.py` (2 項)：NVMe 磁碟掃描與 BusType 篩選。
- `test_batch_runner.py` (3 項)：非阻塞執行緒、錯誤策略與手動中斷。
- `test_reporter.py` (2 項)：檔案歸檔、Dump 生成與 summary.csv 欄位完整性。
- `test_cli.py` (3 項)：CLI 掃描、單筆執行與 CSV 批次執行。
