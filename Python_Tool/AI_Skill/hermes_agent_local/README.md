# Hermes Agent（地端版）— HMC 微型公司協定整合版

全部模型運行在公司 GB300 叢集上，零雲端依賴、資料不出內網。
整合 HMC v8.1 公司協定的角色分工、Anti-Pattern 資料庫、RCA 覆盤流程。

## 公司編制與模型對照

| 角色 | Profile | Skill | 模型 | 核心職責 |
|:---|:---|:---|:---|:---|
| 產品經理 / 執行長 | `@pm` / `@ceo` | Router | Qwen 3.8-27B | 需求梳理、分流調度、進度追蹤 |
| 資深 C 韌體工程師 | `@senior_c_eng` | c-review | DeepSeek V4.1 Flash | Driver/HAL/ISR 開發、Unity 測試 |
| 資深 Python 工具工程師 | `@senior_py_eng` | python-tool | DeepSeek V4.1 Flash | CLI/GUI 上位機、Codec、Mock 測試台 |
| 韌體 QA 驗收工程師 | `@qa` | security-audit | GLM-5.3 Flash | MISRA 掃描、Fuzzing、RCA 覆盤 |
| 架構師 / 程式碼分析師 | `@fw_architect` / `@code_analyst` | arch-review | GLM-5.3 Flash | 4 層架構、記憶體審計、技術報告 |
| 全員聯合 | 多角色協同 | deep-debug (MoA) | DeepSeek + GLM | 深度除錯、Release Review |

## 從 HMC 公司 Spec 整合的內容

| 原 Spec 功能 | 整合到 | 說明 |
|:---|:---|:---|
| 10 角色編制表 | SOUL.md + AGENTS.md | 精簡為 6 角色，每角色綁定 Skill + 模型 |
| Anti-Patterns DB | c-review SKILL.md | ERR-001~003 內建，新發現自動建議登錄 |
| RCA 錯誤覆盤 | security-audit + deep-debug | QA 和 MoA 都會執行 5 步驟 RCA |
| 4 層架構模型 | arch-review SKILL.md | BSP → HAL → Service → Application |
| 封包協議對齊 | python-tool SKILL.md | C struct ↔ Python struct.pack 嚴格對齊 |
| 專案生命週期 | AGENTS.md | 需求確認 → 架構 → 開發 → QA → 交付 |
| Fuzzing 測試策略 | security-audit SKILL.md | 異常封包設計與 Mock 測試台配合 |
| PROJECT_AUDIT 報告 | arch-review + deep-debug | 呈交甲方的正式技術報告格式 |

## 檔案結構

```
hermes_agent_local/
├── .env                              # 內網 vLLM endpoint
├── config.yaml                       # 主設定 + MoA preset
├── SOUL.md                           # @pm/@ceo 人格（Router）
├── AGENTS.md                         # 7 層分流 + 專案生命週期
├── README.md                         # 本文件
└── skills/
    ├── quick-task/SKILL.md           # Tier 1: 雜活（Qwen 27B）
    ├── c-review/SKILL.md             # Tier 2: @senior_c_eng（DeepSeek）
    ├── python-tool/SKILL.md          # Tier 3: @senior_py_eng（DeepSeek）
    ├── security-audit/SKILL.md       # Tier 4: @qa（GLM）
    ├── arch-review/SKILL.md          # Tier 5: @fw_architect/@code_analyst（GLM）
    └── deep-debug/SKILL.md           # Tier 6/7: 全員聯合（MoA）
```

## 分流邏輯

```
甲方（使用者）請求
  │
  ▼
@pm / @ceo Router（Qwen 3.8-27B）
  │
  ├── 簡單問答 ──────────→ 直接回答（Tier 1）
  ├── C code review ────→ @senior_c_eng  → DeepSeek（Tier 2）
  ├── 寫 Python 工具 ───→ @senior_py_eng → DeepSeek（Tier 3）
  ├── 安全 / QA 驗收 ──→ @qa            → GLM（Tier 4）
  ├── 架構 / 技術報告 ──→ @fw_architect  → GLM（Tier 5）
  ├── 複雜除錯 ─────────→ 全員聯合       → MoA（Tier 6）
  └── 正式 Release ────→ 全員聯合       → MoA（Tier 7）
```

## 部署步驟

### 1. 修改 .env

```env
DEEPSEEK_BASE_URL=http://你的DeepSeek伺服器IP:8000/v1
GLM_BASE_URL=http://你的GLM伺服器IP:8000/v1
QWEN_27B_BASE_URL=http://你的Qwen27B伺服器IP:8000/v1
```

### 2. 複製到 Hermes 設定目錄

```powershell
Copy-Item ".\*" "$env:USERPROFILE\.hermes\" -Recurse -Force
```

### 3. 驗證與啟動

```bash
hermes config check
hermes skills list
hermes
```

### 4. 測試分流

```
「Python dict 怎麼排序」              → Tier 1 直接回答
「review 這段 ISR handler」          → Tier 2 @senior_c_eng
「幫我寫一個 UART parser」           → Tier 3 @senior_py_eng
「這段 code 有沒有安全漏洞」          → Tier 4 @qa
「這個專案架構該怎麼改」              → Tier 5 @fw_architect
「這個 bug 怎麼試都修不好」           → Tier 6 全員聯合（MoA）
「做一次 release 前完整 review」      → Tier 7 全員聯合（MoA）
```
