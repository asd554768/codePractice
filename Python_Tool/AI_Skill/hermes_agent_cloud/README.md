# Hermes Agent — Sub-Agent Router 配置

韌體工程師專用的 Hermes Agent 設定，使用 Sub-Agent Router 模式自動分流任務到不同模型。

## 檔案結構

```
hermes_agent/
├── .env                          # API Key（需自行填入）
├── config.yaml                   # 主設定檔
├── SOUL.md                       # Agent 人格定義（Router）
├── AGENTS.md                     # 分流規則
├── README.md                     # 本文件
└── skills/
    ├── quick-task/
    │   └── SKILL.md              # Tier 1: 雜活（Gemini Flash-Lite）
    ├── python-tool/
    │   └── SKILL.md              # Tier 2: Python 工具開發（Claude Sonnet 5）
    └── deep-debug/
        └── SKILL.md              # Tier 3: 深度除錯（Claude Opus 5.5）
```

## 分流邏輯

```
使用者請求
  │
  ▼
Router（Gemini 2.5 Flash-Lite，成本 ~$0.001/次）
  │
  ├── 簡單問答 ──────→ quick-task   → Gemini 2.5 Flash-Lite
  ├── 寫 Python 工具 ─→ python-tool → Claude Sonnet 5
  └── 複雜除錯 ──────→ deep-debug  → Claude Opus 5.5
```

## 月預算分配（$200/月）

| Tier | 模型 | 預算 | 用途 |
|:---|:---|:---|:---|
| Router | Gemini 2.5 Flash-Lite | ~$5 | 分流判斷（幾乎免費） |
| Tier 1 | Gemini 2.5 Flash-Lite | ~$25 | 雜活、boilerplate |
| Tier 2 | Claude Sonnet 5 | ~$120 | Python 工具開發主力 |
| Tier 3 | Claude Opus 5.5 | ~$50 | 深度除錯、跨語言問題 |

## 部署步驟

### 1. 修改 .env

```env
ROUTER_API_KEY=你的實際 API Key
ROUTER_BASE_URL=你的公司 Router URL
```

### 2. 複製到 Hermes 設定目錄

**Windows:**
```powershell
# 備份現有設定（如果有）
Copy-Item "$env:LOCALAPPDATA\hermes" "$env:LOCALAPPDATA\hermes.bak" -Recurse -ErrorAction SilentlyContinue

# 複製新設定
Copy-Item ".\*" "$env:LOCALAPPDATA\hermes\" -Recurse -Force
# 或者如果 Hermes 用 ~/.hermes/
Copy-Item ".\*" "$env:USERPROFILE\.hermes\" -Recurse -Force
```

**Linux/macOS:**
```bash
# 備份
cp -r ~/.hermes ~/.hermes.bak 2>/dev/null

# 複製
cp -r ./* ~/.hermes/
# 或
cp -r ./* ~/.local/share/hermes/
```

### 3. 驗證

```bash
hermes config check     # 驗證設定
hermes skills list      # 確認 skill 已載入
```

### 4. 啟動

```bash
hermes
```

## 調校建議

- 跑幾天後檢查 log：`~/.hermes/logs/`
- 如果分流常判斷錯誤，修改 `AGENTS.md` 的觸發條件關鍵字
- 如果 Tier 1 品質不夠，把 `quick-task/SKILL.md` 的 model 改成 `gemini-3.8-flash`
- 如果預算有剩，把多的挪給 Tier 3（Opus）
