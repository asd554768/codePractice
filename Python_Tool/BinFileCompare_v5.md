# 產品 Bin File 比較工具 - 操作手冊

本工具專為比對產品不同版本所產生的 Bin File 而設計，能自動化比對特定資料區塊（如 InfoBlock、IDPage、systeminfo），並自動過濾不需要比對的黑名單範圍，最後一鍵匯出包含統計數據的多工作表 Excel 報表。

## 1. 初次執行與環境初始化

1. 確保電腦已安裝 Python 以及必備套件：`pandas`, `openpyxl`。
2. 執行主程式 `bin_compare.py`（或點擊已打包的執行檔）。
3. 程式初次啟動時，會自動在同一個目錄下建立以下資料夾與設定檔：
   * 📁 **Bin_Files/** (內含 `InfoBlock`, `IDPage`, `systeminfo` 子資料夾)
   * 📁 **Struct/**
   * 📁 **Result/**
   * 📄 **config.ini**

---

## 2. 檔案配置與準備

在開始比對前，請依據以下規則放置您的檔案：

### 📁 Struct 資料夾 (資料格式定義)
請在 `Struct` 資料夾內放入與子區塊同名的 Excel 檔案（`.xlsx`）：
* `InfoBlock.xlsx`
* `IDPage.xlsx`
* `systeminfo.xlsx`

**Excel 內容格式要求（不需標題列，或第一列為標題皆可）：**
* **第一欄**：變數名稱
* **第二欄**：起始 Byte（整數，如 0, 10, 100）
* **第三欄**：長度（整數，如 1, 2, 4）

### 📁 Bin_Files 資料夾 (待比對檔案)
請將要比對的 Bin File 放入對應的子資料夾中。
* **命名規則**：檔名開頭必須為 `YYMMDD` 日期格式（例如：`260315_InfoBlock_1234.bin`）。
* **數量限制**：每個子資料夾內可以放多個檔案，程式會自動尋找符合您輸入日期的最相近檔案。

---

## 3. 黑名單設定 (config.ini)

若有部分 Byte 範圍（如時間戳記、CRC 校驗碼）每次編譯都會改變且不需要比對，請設定 `config.ini`：

```ini
[Blacklist]
# 設定略過比對的 Byte 範圍。支援格式: 123~234 或 Byte_123~Byte_234
# 若有多組範圍，請用逗號分隔。
InfoBlock = Byte_123~Byte_234, 500~600
IDPage = 10~50
systeminfo =