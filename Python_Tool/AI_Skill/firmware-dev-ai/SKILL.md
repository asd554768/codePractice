---
name: firmware-dev-ai
description: >-
  Designed for C firmware engineers. Covers code flow analysis, Doxygen generation,
  token-saving techniques, and optimized prompt templates for open-source models
  (Ollama/Qwen2.5-Coder/DeepSeek-Coder/Devstral). Triggers on keywords: firmware,
  embedded, C language, MCU, RTOS, register, call graph, Doxygen, code flow, ISR,
  interrupt, driver. Also use for writing technical docs, analyzing function call flows,
  generating module design specs (SDS/SRS).
---

# 韌體開發 AI 輔助工作流程技能包 (Firmware Dev AI Workflow Skill Pack)

> **AI 模型閱讀指南 (Notice for AI Models)**:
> 本文件已優化為結構化 Prompt 規範。任何 AI 模型（Ollama/Claude/GPT/Qwen/DeepSeek）讀取本 Skill 時，請優先查閱【AI 閱讀順序與決策樹】，直接跳轉至對應任務模組執行。

---

## 📚 檔案目錄 (Table of Contents)

1. [🧭 AI 模型執行與閱讀導引 (Recommended AI Execution Flow)](#-ai-模型執行與閱讀導引-recommended-ai-execution-flow)
2. [模組一：現有 Skill 適用性分析 (Existing Skill Analysis)](#模組一現有-skill-適用性分析公司環境)
3. [模組二：開源模型選擇與 Ollama 設定 (Local Open-Source Model Setup)](#模組二開源模型選擇與-ollama-設定)
4. [模組三：程式流程與 Call Graph 分析 Prompt 模板 (Code Flow & RCA)](#模組三程式流程分析-prompt-模板)
5. [模組四：程式流程圖與 Draw.io 繪製 Prompt 模板 (Diagram Generation)](#模組四程式流程圖與時序圖繪製-prompt-模板)
6. [模組五：Doxygen 與 SDS 模組規格書生成 Prompt 模板 (Documentation)](#模組五文件撰寫-prompt-模板)
7. [模組六：Log 文字解析與 HardFault Dump 分析 Prompt 模板 (Log Analysis)](#模組六log-文字解析與學習-prompt-模板)
8. [模組七：Token 節省技巧 (Token Optimization Techniques)](#模組七token-節省技巧)
9. [模組八：Continue.dev IDE 整合設定 (IDE Integration)](#模組八continuedev-ide-整合設定)
10. [模組九：Grenade.tw 60 個精選工具對照表 (2026 Recommended Stack)](#模組九grenadetw-2026-精選-claude-skills--github-開源專案對照與記錄)
11. [模組十一：企業與團隊知識封裝原則 (Enterprise Knowledge Packaging)](#module-11-企業與團隊知識封裝原則-enterprise-knowledge-packaging)

---

## 🧭 AI 模型執行與閱讀導引 (Recommended AI Execution Flow)

當接收到使用者任務時，AI 模型請依照以下**決策樹 (Decision Tree)** 優先跳轉至相應模組：

`
[使用者請求]
  │
  ├── 1. 任務：理解程式流程 / 繪製流程圖 / 分析 Call Graph
  │    └── 📖 跳轉：[模組三] 程式流程分析  ➔  [模組四] 流程圖/Draw.io 繪製
  │
  ├── 2. 任務：生成 Doxygen 注解 / 撰寫 SDS 模組設計規格書
  │    └── 📖 跳轉：[模組五] 文件撰寫 (嚴格執行：禁止修改原始碼邏輯)
  │
  ├── 3. 任務：除錯 / 解析 HardFault Register Dump / 處理 Log
  │    └── 📖 跳轉：[模組三] 3.3 RCA 模板  ➔  [模組六] Log 解析與 Dump 分析
  │
  ├── 4. 任務：優化 Prompt / 降低 Token 費用 / 分析大型 Codebase
  │    └── 📖 跳轉：[模組七] Token 節省技巧 (Constraint-First / Session Card)
  │
  ├── 5. 任務：設定本地 Ollama 開源模型 / 配置 IDE 擴充功能
  │    └── 📖 跳轉：[模組二] 模型與 Modelfile 設定  ➔  [模組八] Continue.dev 設定
  │
  └── 6. 任務：尋找其他開發工具 / 評估開源專案
       └── 📖 跳轉：[模組一] 現有 Skill 分析  ➔  [模組九] 60 個工具對照表
`

---


This skill covers five modules for C firmware engineers:
**Existing Skill Analysis** -> **Open-Source Model Setup** -> **Code Flow Analysis** -> **Doc Writing** -> **Token Efficiency**

---

## Module 1: Existing Skill Suitability Analysis (Company Use)

| Skill | Fit | Firmware Use Case |
|---|:---:|---|
| `deep-research` | 5/5 | Research MCU specs, RTOS comparisons, tech selection; generates cited reports |
| `doc-coauthoring` | 5/5 | Write SDS/SRS module design docs, design review docs, RFC via structured workflow |
| `markdownify-mcp` | 5/5 | Convert PDF datasheets and DOCX manuals to Markdown for AI analysis (supports OCR) |
| `find-docs` | 4/5 | Look up latest FreeRTOS/Zephyr/CMSIS/HAL APIs to avoid outdated info |
| `internal-comms` | 4/5 | Write bug reports, weekly 3P updates, incident reports |
| `pdf` | 3/5 | Merge/split/extract datasheet PDFs, OCR scanned manuals |
| `docx` | 3/5 | Generate or edit Word-format technical docs, test specs |
| `pptx` | 2/5 | Create architecture slides, tech briefings |
| `xlsx` | 2/5 | Generate memory maps, GPIO allocation tables, test matrices |
| `skill-creator` | 3/5 | Continuously improve this skill or create project-specific skills |

**Not suitable for company use** (design/entertainment): `algorithmic-art`, `canvas-design`,
`frontend-design`, `slack-gif-creator`, `web-artifacts-builder`, `webapp-testing`,
`fastapi`, `mcp-builder`, `mcp-playwright`

---

## Module 2: Open-Source Model Selection & Ollama Setup

### Recommended Models (2025-2026)

| Model | Use Case | Install Command |
|---|---|---|
| `qwen2.5-coder:14b` | Daily code analysis, debug (primary) | `ollama pull qwen2.5-coder:14b` |
| `qwen2.5-coder:32b` | Complex architecture analysis, large refactors | `ollama pull qwen2.5-coder:32b` |
| `deepseek-coder-v2:16b` | Balanced code generation + doc writing | `ollama pull deepseek-coder-v2:16b` |
| `devstral:24b` | Multi-step reasoning, agentic tasks | `ollama pull devstral:24b` |
| `deepseek-r1:14b` | Complex state machine / timing logic reasoning | `ollama pull deepseek-r1:14b` |
| `qwen2.5-coder:1.5b` | IDE autocomplete (low latency) | `ollama pull qwen2.5-coder:1.5b` |

> **Two-tier architecture**: Use 1.5B for autocomplete (low latency), 14B+ for Chat/Debug/Doc (high quality)

### Ollama Modelfile (Firmware-Specific System Prompt)

Create `firmware-dev.Modelfile`:

```dockerfile
FROM qwen2.5-coder:14b
PARAMETER temperature 0.2
PARAMETER num_ctx 16384
SYSTEM """
You are a Senior Embedded Firmware Engineer specializing in C for resource-constrained systems.
Expertise: ARM Cortex-M, RISC-V, FreeRTOS, Zephyr, bare-metal, MISRA-C 2012.
Peripherals: UART, SPI, I2C, CAN, USB, DMA, ADC, Timers.

ALWAYS apply these constraints:
1. No dynamic memory allocation (no malloc/free) unless explicitly requested
2. Consider interrupt safety and re-entrancy for ALL shared resources
3. Check all return values; no silent error drops
4. Flag volatile omissions on ISR-shared variables
5. Warn if code could cause Hard Fault, stack overflow, or real-time violation

Response format:
1. [Code] in ```c blocks
2. [Safety/Hardware Notes] - critical trade-offs only
3. [Assumptions] - hardware assumptions made
4. [Edge Cases] - failure scenarios to test

Do NOT guess hardware register behavior. Say "check datasheet" if uncertain.
"""
```

Activate:
```bash
ollama create firmware-dev -f firmware-dev.Modelfile
ollama run firmware-dev
```

---

## Module 3: Code Flow Analysis Prompt Templates

### 3.1 Call Graph Analysis

```
You are a Senior Embedded Firmware Engineer. Analyze the execution flow of the following C code.

[Hardware]
- MCU: [e.g. STM32H7B3 @ 280MHz]
- RTOS: [e.g. FreeRTOS 10.5.1 / bare-metal]
- D-Cache: [enabled/disabled]

[Target Function] `[function_name]`

[Code]
```c
// Paste relevant .h and target function .c implementation
// Only 2-3 levels of dependencies needed, not the full codebase
```

Output format:
1. **Call Tree** (ASCII tree): label direct vs. indirect calls (function pointers)
2. **Shared Resources Table**: globals, statics, HW registers; check volatile correctness
3. **ISR Safety**: critical section coverage, race condition risks
4. **Stack Risk**: large local arrays, deep recursion; estimate max stack depth
5. **Issues List** (table): Severity | Location | Problem | Fix
```

### 3.2 Inter-Module Data Flow Analysis

```
Analyze the data flow between the following firmware modules:

[Module Interfaces (headers only)]
```c
// module_a.h
// module_b.h
```

Output:
1. Mermaid flowchart (label transfer method: direct call/callback/queue/shared buffer)
2. Boundary check completeness
3. Buffer overflow risk points
4. Caller-Callee table: Caller | Callee | Purpose | Side Effects
```

### 3.3 Bug Root Cause Analysis (RCA)

```
Firmware bug root cause analysis:

[Symptom] [e.g. Hard Fault every 2-3 hours under high load, during SPI DMA transfer]
[Environment] MCU: [model] / RTOS: [version] / Stack: [ISR/Task sizes]
[Already Ruled Out] [e.g. disabling DMA eliminates the issue]

[Suspicious Code]
```c
// Paste suspect code
```

Chain-of-Thought:
1. Trace normal execution path
2. Trace failure trigger conditions
3. Infer root cause from traces

Output:
- Root cause hypothesis (confidence: High/Medium/Low)
- Verification steps
- Fixed code
- Preventive recommendations
```

### 3.4 Static Analysis Triage

```
Static analyzer (Coverity/PC-lint/cppcheck) reported:
[Paste warning]

Relevant code:
```c
[Paste]
```

Hardware: [MCU model, D-Cache enabled?, DMA usage?]

Is this a true positive or false positive in this hardware context?
If true positive, describe the exact failure scenario and provide a fix.
```

---

## Module 4: Documentation Prompt Templates

### 4.1 Doxygen Comment Generation

```
You are an embedded firmware documentation engineer.

[STRICT CONSTRAINTS]
- ONLY add Doxygen comments. NEVER modify, refactor, or reorder any functional code.
- Use /** ... */ Javadoc style
- Document every function, struct, enum, global variable

[Doxygen Tag Rules]
- @file (only at top of .h files)
- @brief one-line summary (verb-first: "Transmit data...")
- @param[in] / @param[out] / @param[in,out] name description
- @return return value description (or @return None)
- @note HW register purpose, ISR context restrictions, thread safety
- @warning dangerous constraints (cannot call in ISR, must call init first, etc.)

[Code]
```c
// Paste code
```
```

### 4.2 Module Design Specification (SDS) Generation

```
Write a Software Design Specification section for this firmware module.

[Module Name] [e.g. CAN Bus Driver]
[Summary] [e.g. Non-blocking CAN transceive, supports CAN FD, uses FreeRTOS queue]
[Hardware] [MCU model, peripheral]
[Header Interface]
```c
// Paste .h
```

Generate these sections (technical terms in English):
1. **Purpose & Scope**: module goal and boundaries
2. **Architecture Overview**: Mermaid block diagram of module relationships
3. **Data Structures**: key struct descriptions (field purposes)
4. **API Reference table**: Name | Parameters | Returns | Thread Safety
5. **State Machine**: Mermaid stateDiagram if applicable
6. **Error Handling Strategy**: error code definitions and handling policy
7. **Memory Usage**: RAM/Flash usage estimation
8. **Known Limitations**: known constraints and workarounds
```

### 4.3 Technical Issue Explanation (for Non-Technical Audience)

```
Translate this technical issue for a non-technical manager (no firmware background):

[Technical Issue] [e.g. D-Cache not invalidated before DMA receive causes stale data]
[Audience] Project Manager / Customer

Write:
1. Plain language explanation (use analogy, 50 words max)
2. Impact (functionality / schedule / customer)
3. Solution (non-technical description of the fix)
4. Estimated fix timeline
5. Resources or decisions needed

No technical jargon.
```

---

## Module 5: Token Efficiency Techniques

### 5.1 Constraint-First Prompting

Put all **non-negotiable constraints** at the TOP of the prompt:

```
[MANDATORY CONSTRAINTS - DO NOT VIOLATE]
- Target: ARM Cortex-M4, C99, -O2
- Forbidden: malloc/free, floating point, recursion, global variables (static OK)
- Memory: RAM <= 32KB, Flash <= 256KB
- ISR Safety: all public APIs must be reentrant
- Style: snake_case, <=80 chars/line, return App_Status_t

[TASK]
Implement a circular buffer supporting DMA writes...
```

### 5.2 Minimalist Snippet Method

**Never paste the full file.** Only provide:

```c
/* Only include these three categories: */

// 1. Required type definitions
typedef struct { ... } Spi_HandleTypeDef;
typedef enum { SPI_OK=0, SPI_ERR=-1 } Spi_Status_t;

// 2. Problem function signature + implementation
Spi_Status_t Spi_DmaTransfer(Spi_HandleTypeDef *h, uint8_t *buf, uint16_t len);

// 3. Direct dependencies (signature only, no implementation)
// HAL_SPI_Transmit_DMA() - starts DMA, non-blocking, calls HAL_SPI_TxCpltCallback on completion
```

### 5.3 Phased Analysis (Large Codebase)

```
[Phase 1 - Architecture Map] (NO code, module names only)
Firmware module dependencies:
main.c -> [system_init, task_manager]
task_manager.c -> [sensor_task, comm_task, log_task]
sensor_task.c -> [driver_adc, driver_spi, ring_buffer]

Issue: comm_task random watchdog reset under high load. Identify most likely root cause module.

---
(After Phase 1 identifies ring_buffer)

[Phase 2 - Focus on Module]
Here is the complete ring_buffer.c: [paste]
Analyze ISR vs. task shared access safety.

---
(After specific function identified)

[Phase 3 - Precise Fix]
ring_buffer_write() specific race condition when called from ISR context.
Provide fixed code using critical section protection.
```

### 5.4 Session Context Card (Avoid Re-Explaining Environment)

Paste at the start of each new conversation:

```markdown
# [Project Name] Firmware Context

## Hardware
- MCU: STM32H7B3 @ 280MHz, ARM Cortex-M7, D-Cache enabled
- RTOS: FreeRTOS 10.5.1, heap_4.c, configTOTAL_HEAP_SIZE=64KB
- Compiler: arm-none-eabi-gcc 12.2, -O2, C99

## Code Standards
- Naming: snake_case, module prefix (uart_send, spi_init)
- Error codes: App_Status_t (APP_OK=0, APP_ERR=-1, APP_BUSY=-2)
- Forbidden: malloc/free, global IRQ mask > 10us
- ISR-shared variables must be volatile + critical section

## Module API Summary (NO code pasted)
- uart: uart_init(), uart_send_dma(), uart_recv_isr_hook()
- spi: spi_init(), spi_transfer(), spi_dma_start()
- ring_buffer: rb_init(), rb_push(), rb_pop(), rb_size()
```

### 5.5 Output Control Directives

| Scenario | Append to prompt |
|---|---|
| Code only | `Return only the C code. No explanation.` |
| Code + brief rationale | `Code first. One-sentence rationale only.` |
| Find issues | `List issues as table: Severity, Location, Fix.` |
| Show diff | `Show only changed lines in +/- diff format.` |

---

## Module 6: Continue.dev IDE Integration

Install VS Code extension: `Continue` (continue.dev)

```json
{
  "models": [
    {
      "title": "Firmware Dev (14B Chat)",
      "provider": "ollama",
      "model": "qwen2.5-coder:14b",
      "apiBase": "http://localhost:11434"
    }
  ],
  "tabAutocompleteModel": {
    "title": "Qwen2.5 1.5B (Autocomplete)",
    "provider": "ollama",
    "model": "qwen2.5-coder:1.5b",
    "apiBase": "http://localhost:11434"
  },
  "slashCommands": [
    {
      "name": "doxygen",
      "description": "Generate Doxygen for selected C code",
      "prompt": "Add complete Doxygen comments to this C firmware code. Do NOT modify any logic. Use @brief, @param[in/out], @return, @note for ISR safety, @warning for critical constraints."
    },
    {
      "name": "review",
      "description": "Embedded C code review",
      "prompt": "Review this embedded C code for: 1) ISR safety (volatile, race conditions), 2) Memory safety (buffer overflow, uninit vars), 3) MISRA-C 2012 violations, 4) Error handling gaps. Format as table: Severity | Location | Issue | Fix."
    },
    {
      "name": "flow",
      "description": "Analyze call graph and execution flow",
      "prompt": "Analyze the call graph of this firmware function. Output: 1) ASCII call tree with ISR/task labels, 2) shared resource table (volatile correct?), 3) stack depth estimate, 4) race condition risks."
    },
    {
      "name": "rca",
      "description": "Root cause analysis",
      "prompt": "Root cause analysis for this firmware bug. Chain-of-Thought: 1) Trace normal path, 2) Trace failure path, 3) Identify root cause with confidence level. Then: fix code + test verification steps."
    }
  ]
}
```

---

## Quick Reference: Task -> Tool Mapping

| What you need to do | Use |
|---|---|
| Understand unfamiliar code flow | This skill Module 3.1 (Call Graph template) |
| Analyze inter-module data flow | This skill Module 3.2 |
| Find bug root cause | This skill Module 3.3 (RCA template) |
| Triage static analysis warnings | This skill Module 3.4 |
| Generate Doxygen comments | This skill Module 4.1 |
| Write module design doc (SDS) | `doc-coauthoring` skill + this skill Module 4.2 |
| Explain tech issue to management | This skill Module 4.3 |
| Research tech selection (RTOS/MCU) | `deep-research` skill |
| Look up FreeRTOS/HAL API | `find-docs` skill |
| Convert PDF manual to Markdown | `markdownify-mcp` skill |
| Write weekly reports / bug reports | `internal-comms` skill |
| Save tokens | This skill Module 5 (5.1-5.5) |
| Avoid re-explaining environment | This skill Module 5.4 (Context Card) |

---

## Critical Warnings

WARNING: AI-generated firmware code MUST be manually reviewed, especially:
- Hardware register operations (cross-check against official datasheet)
- DMA transfer cache invalidate/clean sequences
- ISR execution time (must not exceed deadline)
- Any timing-critical logic

TIP: Local model privacy advantage: Ollama processes code locally only, no cloud upload.
Safe for firmware projects under NDA or containing trade secrets.

NOTE: Core mental model:
- You = Architect + Reviewer
- LLM = Junior Dev / Boilerplate Generator
- Datasheet = single source of truth; LLM only structures logic YOU have verified into code
---

## Module 10: Grenade.tw 2026 精選 Claude Skills & GitHub 開源專案對照與記錄

參考文章：[【2026】Claude Skills 怎麼選？精選 60 個工作流程與 GitHub 開源專案清單 (Grenade 手榴彈)](https://grenade.tw/blog/claude-skills-github-2026/)

將文章中精選的 60 個工具/Skill，針對 **C 語言韌體開發者** 的實務價值進行交叉對照與記錄：

### 1. 核心 IDE / 開發 Agent (Part 1)
- **Claude Code (#01)**: Anthropic CLI Agent，能讀取全專案、執行 C Makefile/CMake 測試與重構。
- **Cursor (#02)**: VS Code AI IDE，支援韌體 Codebase 全局對話與多檔案編輯。
- **Superpowers (#05)**: github.com/obra/superpowers — 20+ 個經過實戰驗證的 Claude Code Skills，含 TDD、Debug 與執行流程。
- **Spec Kit (#06)**: github.com/github/spec-kit — 規格驅動開發，先寫 SDS/SRS 規格再由 AI 生成 C 程式碼。

### 2. MCP 工具與上下文注入 (Part 3)
- **Context7 (#17)**: github.com/upstash/context7 — 自動將最新 FreeRTOS/Zephyr/CMSIS 文件注入 Context，避免舊 API 幻覺。
- **Task Master AI (#18)**: github.com/eyaltoledano/claude-task-master — 將大型韌體 PRD/SDS 拆解為條理分明的微任務流水線。
- **markdownify-mcp (#21)**: github.com/zcaceres/markdownify-mcp — 將晶片 Datasheet PDF、規格書轉成 Markdown 供模型閱讀。

### 3. 精選 Skills (Part 4)
- **PDF Processing (#23)**: nthropics/skills/tree/main/skills/pdf — 讀取與表格擷取晶片手冊。
- **Skill Creator (#25)**: nthropics/skills/tree/main/skills/skill-creator — 5 分鐘寫出新韌體專案專屬的 SKILL.md。
- **Context Optimization (#29)**: github.com/muratcankoylan/agent-skills-for-context-engineering — Context 壓縮與 Token 成本最佳化。
- **Deep Research Skill (#30)**: github.com/199-biotechnologies/claude-deep-research-skill — 八階段自動化技術選型與 MCU 評估。

### 4. 本地 AI 運行引擎 (Part 5)
- **Ollama (#31)**: github.com/ollama/ollama — 本地跑 Qwen2.5-Coder / DeepSeek-Coder，無 API 費用且程式碼不上雲端（離線 NDA 安全）。
- **vLLM (#35)**: github.com/vllm-project/vllm — 高吞吐量推論引擎。

### 5. 程式碼記憶與資源庫 (Part 8 & 9)
- **Codebase Memory MCP (#52)**: github.com/DeusData/codebase-memory-mcp — 將韌體 Codebase 轉為知識圖譜，跨 Session 記住架構。
- **Awesome Claude Skills (#53)**: github.com/travisvn/awesome-claude-skills — 社群精選 Skill 庫。
- **Anthropic Skills Repo (#54)**: github.com/anthropics/skills — 官方 Skill 參考標準。

---

---

## Module 11: 企業與團隊知識封裝指南 — AI 模型架構與執行規範 (Enterprise Knowledge & Skill Packaging Protocol)

> **Notice for AI Models (模型自我學習導引)**:
> 本模組旨在規範 AI 如何解析、構建與執行企業/團隊級別的知識庫（Knowledge Packaging）。AI 模型在讀取專案文檔或執行企業任務時，必須遵循以下「導航」架構，嚴格劃分 **背景 (Context)**、**護欄 (Guardrails)** 與 **工作流 (Workflows)**。
> 參考來源：[【Agent Skills 實戰入門 07】公司知識怎麼整理成 Skill (動詞實驗室)](https://verb.tw/tech/agent-skills-starter/agent-skills-07-enterprise-knowledge-packaging/)

### 1. 知識分類與權重架構 (Knowledge Classification & Priority)

模型在接收專案資料與執行指令時，必須將輸入解構為以下三種權重等級，並套用對應的執行策略：

| 類別 (Category) | 內容範例 | 模型執行策略 (Model Action Protocol) | 權重 (Priority) |
|---|---|---|:---:|
| **硬規則 (Guardrails / Hard Rules)** | • 不可使用 `malloc/free`<br>• 中斷遮蔽時間不可 > 10µs<br>• 金鑰與敏感 Memory 地址不可輸出<br>• 資訊不足時禁止自行補齊 | **Mandatory Enforcement (強制執行)**<br>若檢測到違規，必須立即中斷執行或發出一級警告 (Critical Error)。禁止妥協或自動容錯。 | 🔴 P0 (Highest) |
| **工作流 (Workflows & Steps)** | • 變更暫存器後必須驗證狀態旗標<br>• 修改 API 後需先更新 .h 再修 .c<br>• 條件分支處理順序 | **Sequential Execution (按序執行)**<br>依條件引導 (Conditional Flow) 依序讀取對應 Reference 檔案，嚴格按步驟驗證。 | 🟡 P1 (Medium) |
| **背景知識 (Context & Domain)** | • 專案歷史、架構縮寫<br>• 資料欄位意義與 Legacy Workaround<br>• 部門術語對照清單 | **Reference Only (僅供參考與對照)**<br>僅用於幫助理解上下文語意，絕對不可覆蓋或衝突 P0/P1 的規則。 | 🟢 P2 (Lowest) |

---

### 2. 資料域路由導航規範 (Data Domain Routing Protocol)

模型**不可**將所有專案文檔一次性加載至 Context Window 中。當收到具體任務時，模型必須先執行 **資料域 (Data Domain) 路由判斷**：

```
[輸入任務 Task]
   │
   ├── 判斷 1: 涉及底層驅動 / 暫存器操作？ ───► 僅讀取 references/driver_registers.md
   ├── 判斷 2: 涉及 RTOS 多任務 / ISR 存取？ ───► 僅讀取 references/rtos_concurrency.md
   ├── 判斷 3: 涉及安全規範 / MISRA 驗證？  ───► 僅讀取 references/safety_compliance.md
   └── 判斷 4: 涉及架構與 SDS 規格設計？  ───► 僅讀取 references/architecture_sds.md
```

---

### 3. AI 模型避錯與邊界協定 (AI Fail-Safe & Edge-Case Protocol)

當模型在執行企業/團隊任務時遭遇歧義或資訊缺失，必須遵守以下 **Fail-Safe 協定**：

1. **資訊不透明/缺失時 (Incomplete Context Protocol)**：
   * ❌ **Forbidden**: 自行預設參數、假定硬體行為、補全未說明的引腳/暫存器位址。
   * ✅ **Required**: 停止繼續生成 C 代碼，標註 `[CONTEXT_MISSING]` 並向使用者發出明確提問。

2. **新舊邏輯衝突時 (Conflict Resolution Protocol)**：
   * ❌ **Forbidden**: 混合舊規範 (Legacy Workaround) 與新規範 (Current Spec)。
   * ✅ **Required**: 優先採納 `Guardrails (P0)` 規則，並主動提示使用者該處存在 Legacy 衝突點。

3. **輸出邊界隔離 (Scope Boundary Protocol)**：
   * **內部除錯模式**：輸出包含全域變數位址、暫存器 Raw Value、Memory Dump、詳細 Log 堆疊。
   * **對外報告模式**：自動隱去內部敏感位址與晶片保密架構，轉化為非技術/管理層可讀的摘要。

---

### 4. 範例：AI 模型處理 Skill 的正確與錯誤模式 (Do's and Don'ts)

#### ❌ 錯誤模式（文字堆疊，無導航）：
> *"本 Skill 包含專案的所有 Wiki 文件。請閱讀 docs/ 裡面的所有檔案，並協助我撰寫驅動程式。"*
> **(嚴重問題：模型 Context 被不相關檔案填滿，導致推理延遲增加、出現舊 API 幻覺，且無法辨識何為強制護欄)**

#### ✅ 正確模式（導航 + 護欄 + 條件路由）：
> *"本 Skill 用於 UART 驅動開發。*
> *【硬限制 P0】禁止在 ISR 中使用阻塞式延遲 (delay)；*
> *【條件路由 P1】若涉及 DMA 傳輸，請優先讀取 `references/dma_cache_rules.md`；*
> *【背景 P2】如需確認暫存器欄位意義，請參考 `references/uart_map.md`。"*
