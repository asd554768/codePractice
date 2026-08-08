# C 語言韌體 AI 輔助開發與企業知識封裝 Master Planning 指南

> **文件簡介**：本指南為 C 語言韌體開發者（Embedded Firmware Engineers）提供完整的 AI 輔助開發、程式流程分析、文件自動化與企業知識封裝（Enterprise Knowledge Packaging）規劃方案。整合開源 AI 模型（Ollama / Qwen2.5-Coder / DeepSeek-Coder）、IDE 插件 (Continue.dev)、MCP 服務與 2026 前沿 AI 工具鏈。

---

## 📌 目錄 (Table of Contents)

1. [一、 系統架構與開源 AI 模型選型 (Tech Stack & Models)](#一-系統架構與開源-ai-模型選型)
2. [二、 現有 Skill 適用性分析矩陣 (Skill Matrix)](#二-現有-skill-適用性分析矩陣)
3. [三、 企業與團隊知識封裝原則 (Enterprise Knowledge Packaging)](#三-企業與團隊知識封裝原則)
4. [四、 程式流程分析與圖表自動化 (Flow Tracing & Diagrams)](#四-程式流程分析與圖表自動化)
5. [五、 韌體文件與 Doxygen 自動化規範 (Documentation Workflow)](#五-韌體文件與-doxygen-自動化規範)
6. [六、 Log 文字解析與 HardFault 除錯 (Log & Crash Parsing)](#六-log-文字解析與-hardfault-除錯)
7. [七、 Token 最佳化與成本控制技巧 (Token Optimization)](#七-token-最佳化與成本控制技巧)
8. [八、 2026 開源工具鏈對照落地指南 (Grenade.tw 工具鏈)](#八-2026-開源工具鏈對照落地指南)

---

## 一、 系統架構與開源 AI 模型選型

為滿足韌體專案 **高隱私（離線 NDA 安全）**、**零 API 費用** 與 **高推理品質** 的需求，採用 **兩層式開源模型架構**：

```
                    [ 嵌入式開發者 VS Code / Cursor ]
                                   │
              ┌────────────────────┴────────────────────┐
              ▼                                         ▼
   [ 行內毫秒級補全 (Autocomplete) ]           [ 程式碼分析 / 除錯 / 文件 (Chat/Agent) ]
      • 模型: Qwen2.5-Coder 1.5B                 • 主力模型: Qwen2.5-Coder 14B / 32B
      • 引擎: Ollama / llama.cpp                 • 推理模型: DeepSeek-R1 14B / Devstral 24B
      • 延遲: < 100ms                            • 引擎: Ollama / vLLM (OpenAI-compatible)
```

### 1. 推薦模型配置
* **`qwen2.5-coder:14b`**：主力分析模型，C 語言邏輯、ISR 安全與代碼生成最佳化。
* **`qwen2.5-coder:32b`**：用於大型架構重構與跨檔案依賴分析（需 24GB+ VRAM）。
* **`deepseek-r1:14b`**：處理複雜狀態機 (State Machine) 與時序競態 (Race Condition) 之推理。
* **`qwen2.5-coder:1.5b`**：專用於 Continue.dev / Cursor 行內實時補全。

---

## 二、 現有 Skill 適用性分析矩陣

| Skill 名稱 | 韌體開發適用度 | 關鍵應用場景 | 最佳搭檔工具 |
|---|:---:|---|---|
| `deep-research` | ⭐⭐⭐⭐⭐ | 晶片 MCU 規格比較、RTOS 架構選型、生態評估報告 | WebSearch, markdownify-mcp |
| `doc-coauthoring` | ⭐⭐⭐⭐⭐ | 撰寫 SRS/SDS 設計規格書、RFC、架構評審文件 | Markdown, Artifacts |
| `markdownify-mcp` | ⭐⭐⭐⭐⭐ | 將晶片 PDF Datasheet、廠商 DOCX 轉為 AI 可讀 Markdown | OCR, pdf |
| `find-docs` | ⭐⭐⭐⭐ | 實時檢索 FreeRTOS、CMSIS、Zephyr、HAL 庫最新 API 規格 | Context7 CLI |
| `internal-comms` | ⭐⭐⭐⭐ | 撰寫週報 (3P Updates)、Bug Report、事故檢討報告 (Incident Report) | Markdown |
| `pdf` / `docx` / `xlsx` | ⭐⭐⭐ | 提煉 Memory Map、GPIO 分配表、暫存器對照表、測試矩陣 | Python scripts |

---

## 三、 企業與團隊知識封裝原則

將團隊知識打包成 Skill 時，**文件搬家 ≠ 工作流工程化**。必須建立強大導航架構：

### 1. 知識三分類權重矩陣
* 🔴 **硬規則 (Guardrails / Hard Rules - P0 最高權重)**：
  * 禁止 `malloc/free` 動態記憶體配置。
  * ISR 中斷遮蔽時間不得大於 10µs。
  * 資訊不全時**禁止自行預設位址或參數**。
  * *策略*：Mandatory Enforcement (違規立即中斷發出一級警告)。
* 🟡 **工作流 (Workflows & Steps - P1 中權重)**：
  * 修改暫存器後必須驗證狀態旗標。
  * 修改 API 需先更新 `.h` 再修正 `.c`。
  * *策略*：Sequential Execution (按條件導航依序執行驗證)。
* 🟢 **背景知識 (Context - P2 參考權重)**：
  * 專案歷史、Legacy Workaround 說明、部門術語。
  * *策略*：Reference Only (僅供語意對照，不可覆蓋 P0/P1)。

### 2. 按資料域 (Data Domain) 切分目錄
避免依檔案類型堆疊，應依任務領域放置於 `references/`：
```
firmware-dev-ai/
├── SKILL.md                  # 主導引與決策樹
└── references/
    ├── driver_registers.md   # 板級暫存器定義
    ├── rtos_concurrency.md   # RTOS 多任務與 ISR 競態規範
    ├── safety_compliance.md  # MISRA-C / 護欄規範
    └── memory_map.md         # Flash / RAM 分區表
```

### 3. AI 模型 Fail-Safe 避錯協定
1. **資訊缺失**：觸發 `[CONTEXT_MISSING]` 標註，終止代碼生成並向使用者提問。
2. **新舊衝突**：優先採納 P0 Guardrails 規則，並標註 Legacy 衝突點。
3. **輸出邊界**：除錯模式輸出 Raw Memory Dump；對外模式轉化為非技術報告。

---

## 四、 程式流程分析與圖表自動化

### 1. Call Graph 結構化分析
使用結構化 Prompt 引導 AI 進行三層分析：
```text
分析目標函式 `usart_rx_isr`：
1. Call Tree：ASCII 樹狀圖（區分直接呼叫 vs 函式指標間接呼叫）
2. 共享資源表：全域變數/暫存器，檢查 volatile 與 Critical Section 完整性
3. Stack 風險：區域陣列與最大 Stack 深度估算
4. 問題表格：Severity | Location | Issue | Recommended Fix
```

### 2. 流程圖與 Draw.io 自動化
* **Mermaid.js**：生成 `flowchart TD` 或 `sequenceDiagram`，可直接在 VS Code / Markdown 渲染。
* **Draw.io (mxGraph XML)**：指示 AI 直接輸出 `<mxfile>` XML 內容，存成 `.drawio` 後可雙擊打開拖拉編輯。
* **Draw.io 1秒匯入**：使用 Mermaid/PlantUML 語法，在 Draw.io 選擇 `Arrange` ➔ `Insert` ➔ `Advanced` ➔ `Mermaid` 自動繪製。

---

## 五、 韌體文件與 Doxygen 自動化規範

### 1. Doxygen 自動生成 (嚴格限制)
* **黃金法則**：**絕對禁止**修改、重構或調換原始程式碼邏輯！
* **標籤規範**：包含 `@file`, `@brief`, `@param[in/out]`, `@return`, `@note` (硬體/ISR限制), `@warning` (危險操作)。

### 2. 模組詳細設計規格書 (SDS) 生成
結構化輸出 8 大標準章節：
1. Purpose & Scope
2. Architecture Overview (Mermaid 關係圖)
3. Data Structures (結構體欄位說明)
4. API Reference Table
5. State Machine (Mermaid stateDiagram)
6. Error Handling Strategy
7. Memory Usage Estimation
8. Known Limitations & Workarounds

---

## 六、 Log 文字解析與 HardFault 除錯

### 1. Cortex-M HardFault SCB Dump 解析
提供暫存器 Raw Value (R0-R12, LR, PC, xPSR, CFSR, HFSR, BFAR)，AI 自動執行：
* 解析精確 Fault 類型 (BusFault / UsageFault / MemManage)。
* 分析引發 Fault 的記憶體位址 (如 Precise Data Access Violation)。
* 根據 PC/LR 追蹤出問題的指令與修正建議。

### 2. UART/CAN Log 異常特徵提取
* 統計 Error Code 出現頻率。
* 捕捉 Timestamp 間隔異常（時序延遲或中斷卡死）。
* 自動生成 Python Regex 提取器，供後續自動過濾腳本使用。

---

## 七、 Token 最佳化與成本控制技巧

1. **Constraint-First Prompting**：將 `無 malloc`、`RAM <= 32KB`、`C99` 等非談判限制放置在 Prompt 最頂端。
2. **Minimalist Snippets**：僅提供型別定義、目標函式實作與直屬 API Signature，拒絕貼入整個檔案。
3. **Session Context Card**：新對話開啟時，貼上固定的專案環境卡片，避免重複說明 MCU、RTOS 與規範。
4. **分階段分析法 (Phased Analysis)**：大型 Codebase 採「架構地圖 ➔ 聚焦模組 ➔ 精確函式」三階段推進。

---

## 八、 2026 開源工具鏈對照落地指南

對照 Grenade 2026 精選 60 工具清單，韌體開發者之最佳落地組合：

* **開發 Agent**：`Claude Code` (CLI) + `Cursor` (IDE) + `Superpowers` (Skill 庫) + `Spec Kit` (規格驅動)。
* **知識與 MCP**：`Context7` (API 文件注入) + `Task Master AI` (任務拆解) + `markdownify-mcp` (Datasheet 轉檔)。
* **本地推論與記憶**：`Ollama` (本地 LLM 引擎) + `Codebase Memory MCP` (程式碼知識圖譜)。

---

## 🚀 落地執行檢查清單 (Action Checklist)

- [x] 在本機與 Git 專案建立 `firmware-dev-ai/SKILL.md`
- [x] 配置 Ollama `firmware-dev.Modelfile` 系統提示
- [x] 在 Continue.dev 配置 `/doxygen`, `/flow`, `/review`, `/rca` 指令
- [x] 建立劃分 Context (P2), Workflows (P1), Guardrails (P0) 的企業知識庫架構
- [x] 驗證 Draw.io XML 與 Mermaid 流程圖生成流程
