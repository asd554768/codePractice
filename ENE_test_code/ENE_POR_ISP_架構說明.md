# ENE 無 Bootloader (POR Mask ROM) SMBus 燒錄架構說明

這份文件詳細解析了 ENE 晶片在 **「沒有 Flash Bootloader (完全空白片或死磚)」** 的極端情況下，如何透過硬體重置與 Mask ROM 窗口，強行使用 SMBus 進行底層韌體燒錄的運作原理與流程。

---

## 1. 核心觀念：Mask ROM 與 POR 偵聽窗口

當 ENE 晶片的 Flash 被清空或損壞時，晶片上電後 CPU 無法從 Flash 載入任何指令，傳統的 SMBus 軟體更新機制完全失效。為了防止晶片變為廢磚，ENE 在矽晶圓底層實作了以下救命機制：

1. **Mask ROM (唯讀硬體啟動碼)**：
   晶片出廠時，在矽晶圓上固化了一小段無法被抹除的唯讀記憶體。這段代碼是 ENE 的硬體底線，專門用來處理死磚救援。
2. **Power-On Reset (POR) 偵聽窗口**：
   當晶片接收到硬體 Reset (RST# 腳位從低電位拉高) 復位的瞬間，Mask ROM 會最先取得控制權。它會開啟一個**極短暫的計時窗口（約 20ms 到 50ms）**，在此期間監聽 SMBus 腳位。若超時未收到解鎖密碼，Mask ROM 就會把控制權交給 Flash（然後因為 Flash 壞掉而當機）。

---

## 2. 系統架構方塊圖 (Architecture Block Diagram)

在 POR Mask ROM 模式下，Host 端除了 SMBus 之外，還**必須具備控制 ENE 晶片 Reset 腳位 (RST#) 的物理能力**（例如透過主機板的 EC 控制，或外接燒錄器的 GPIO）。

```mermaid
blockDiagram
    block Host_PC {
        Update_Tool["POR Update Tool\n(Real-Time Thread)"]
        GPIO_Ctrl["GPIO/Reset Ctrl\n(Physical Line)"]
        SMBus_Ctrl["SMBus Master\n(I2C)"]
    }
    
    block ENE_MCU["ENE MCU (Blank / Bricked)"] {
        RST_Pin["RST# Pin"]
        SMBus_HW["SMBus HW Engine"]
        Mask_ROM["Mask ROM\n(Silicon Hardcoded)"]
        Flash_Engine["Flash HW Controller"]
        NV_Flash["NV Flash\n(Empty/Corrupted)"]
    }

    Update_Tool --> GPIO_Ctrl : Assert/De-assert
    Update_Tool --> SMBus_Ctrl : Send ISP Keys
    
    GPIO_Ctrl --> RST_Pin : Physical Reset Signal
    SMBus_Ctrl --> SMBus_HW : SMBus Clock/Data
    
    RST_Pin --> Mask_ROM : Triggers POR Window
    SMBus_HW --> Mask_ROM : 0x7F Unlock in < 20ms
    Mask_ROM --> Flash_Engine : Activates HW ISP
    Flash_Engine --> NV_Flash : Direct Erase/Write
```

---

## 3. POR 硬體極限搶佔流程圖 (POR Timing Flowchart)

以下是 `ene_smbus_por_isp.c` 在真實世界中與晶片互動的嚴格時序流程：

```mermaid
sequenceDiagram
    participant Host as Host (Programmer)
    participant RST as ENE RST# Pin
    participant ROM as ENE Mask ROM
    participant FSM as ENE HW Flash Engine

    Note over Host, FSM: 階段 1：硬體強制凍結與復位
    Host->>RST: 1. 拉低 (Assert GND)
    Note right of RST: MCU 完全停止運作 (Halted)
    Host->>Host: Delay 10ms 等待放電穩定
    
    Host->>RST: 2. 拉高 (De-assert 3.3V)
    RST->>ROM: 觸發 Power-On Reset (POR)
    
    Note over Host, ROM: 階段 2：生死 20 毫秒 - Mask ROM 偵聽窗口
    activate ROM
    Note right of ROM: ⏳ 倒數計時開始 (20ms~50ms)
    
    Host->>ROM: 3. 立即寫入 0x7F = 0x55 (SMBus)
    Host->>ROM: 4. 立即寫入 0x7F = 0xAA (SMBus)
    
    alt 在 20ms 內成功收到密碼
        ROM->>FSM: 解鎖成功，啟動 HW ISP 狀態機
        deactivate ROM
        Note right of FSM: 硬體引擎接管 SMBus 匯流排
    else 超過 20ms (Timeout)
        ROM->>ROM: 關閉偵聽，跳轉至 Flash
        deactivate ROM
        Note right of ROM: 💀 晶片死機 (Bricked)
    end
    
    Note over Host, FSM: 階段 3：硬體直連燒錄 (Bypass CPU)
    Host->>FSM: 5. 寫入 0x80~0x82 (Sector Address)
    Host->>FSM: 6. 寫入 0x85 = 0x01 (Trigger Erase)
    FSM-->>Host: Polling BUSY bit 直到為 0
    
    Host->>FSM: 7. 寫入 0x80~0x82 (Page Address)
    Host->>FSM: 8. 寫入 0x84 (32 Bytes Data)
    Host->>FSM: 9. 寫入 0x85 = 0x02 (Trigger Program)
    FSM-->>Host: Polling BUSY bit 直到為 0
    
    Note over Host, FSM: 階段 4：釋放與重啟
    Host->>FSM: 10. 寫入 0x85 = 0x80 (Reset MCU)
    FSM->>RST: 觸發軟重啟，載入全新韌體！
```

---

### ⚠️ 工程實務開發重點 (Critical Implementation Notes)

1. **嚴格的即時性 (Strict Real-Time Requirement)**
   在時序圖中的「階段 2」，從 `RST#` 拉高到送完 `0x55`、`0xAA` 密碼，中間的延遲容忍度極低。如果在 Windows OS 下執行，排程器剛好在拉高 Reset 後把執行緒 Context Switch 切換給其他程式，幾十毫秒後才切回來，Mask ROM 窗口就會關閉，導致解鎖失敗。因此，這類工具通常需要：
   - 提升 Process/Thread 優先級 (`SetPriorityClass`, `SetThreadPriority`)。
   - 確保 SMBus 底層 Driver 不要有額外的延遲設定。
2. **無需 CPU 參與的燒錄階段 (Zero CPU Overhead)**
   進入「階段 3」後，所有的 `Sector Erase` 與 `Page Program` 都是由硬體狀態機 (HW FSM) 執行，8051 CPU 是被掛起的。這確保了燒錄過程不受軟體 Bug 影響，極大提升了寫入的穩定性。
