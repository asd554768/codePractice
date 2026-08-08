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

# Firmware Dev AI Workflow Skill Pack

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