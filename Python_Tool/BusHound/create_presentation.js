const pptxgen = require('pptxgenjs');
const path = require('path');

const pptx = new pptxgen();

// 設定 16:9 投影片 (10" x 5.625")
pptx.layout = 'LAYOUT_16x9';

// 色彩定義 (嚴格符合 pptxgenjs 規則：無 # 符號、無 8 碼)
const C_BG_DARK = '0F172A';      // 深邃海軍藍
const C_BG_LIGHT = 'F8FAFC';     // 柔和淺灰白
const C_CARD_BG = 'FFFFFF';      // 卡片純白背景
const C_CARD_BORDER = 'CBD5E1';  // 邊框淺灰
const C_TEXT_DARK = '0F172A';    // 主要文字
const C_TEXT_MUTED = '64748B';   // 次要說明文字
const C_PRIMARY = '0284C7';      // 科技湛藍
const C_PRIMARY_LIGHT = 'E0F2FE';// 湛藍淺底
const C_SUCCESS = '10B981';      // 翡翠綠
const C_SUCCESS_LIGHT = 'D1FAE5';// 綠色淺底
const C_WARNING = 'F59E0B';      // 琥珀橘
const C_WARNING_LIGHT = 'FEF3C7';// 橘色淺底
const C_DANGER = 'EF4444';       // 緋紅
const C_DANGER_LIGHT = 'FEE2E2'; // 紅色淺底
const C_NAVY_CARD = '1E293B';    // 深色內容卡片

// 圖片路徑
const IMG_HEADER = path.join(__dirname, 'assets', 'screenshot_header.png');
const IMG_TAB1 = path.join(__dirname, 'assets', 'screenshot_tab1_scsi.png');
const IMG_TAB2 = path.join(__dirname, 'assets', 'screenshot_tab2_vuc.png');
const IMG_TAB3 = path.join(__dirname, 'assets', 'screenshot_tab3_sniffer.png');

// 輔助函式：新增標準內容頁 Header
function addHeader(slide, category, title, pageNum) {
    slide.addShape(pptx.ShapeType.roundRect, {
        x: 0.8, y: 0.35, w: 1.8, h: 0.3,
        fill: { color: C_PRIMARY_LIGHT },
        line: { color: C_PRIMARY, width: 1 },
        rectRadius: 0.15
    });
    slide.addText(category, {
        x: 0.8, y: 0.35, w: 1.8, h: 0.3,
        fontSize: 10, fontFace: 'Arial', bold: true,
        color: C_PRIMARY, align: 'center', valign: 'middle', margin: 0
    });

    slide.addText(title, {
        x: 2.7, y: 0.3, w: 6.0, h: 0.4,
        fontSize: 18, fontFace: 'Arial', bold: true,
        color: C_TEXT_DARK, valign: 'middle', margin: 0
    });

    slide.addText(`BusHound Tool Guide  |  Page ${pageNum}`, {
        x: 6.5, y: 5.25, w: 2.7, h: 0.3,
        fontSize: 9, fontFace: 'Arial',
        color: C_TEXT_MUTED, align: 'right', margin: 0
    });
}

// ==========================================
// SLIDE 1: 封面 (Dark Theme)
// ==========================================
{
    const slide = pptx.addSlide();
    slide.background = { color: C_BG_DARK };

    slide.addShape(pptx.ShapeType.roundRect, {
        x: 0.8, y: 0.7, w: 8.4, h: 4.2,
        fill: { color: C_NAVY_CARD },
        line: { color: '334155', width: 1.5 },
        rectRadius: 0.2
    });

    slide.addShape(pptx.ShapeType.roundRect, {
        x: 1.2, y: 1.1, w: 2.5, h: 0.35,
        fill: { color: C_PRIMARY },
        rectRadius: 0.15
    });
    slide.addText("STORAGE DEBUG TOOL", {
        x: 1.2, y: 1.1, w: 2.5, h: 0.35,
        fontSize: 10, fontFace: 'Arial', bold: true,
        color: 'FFFFFF', align: 'center', valign: 'middle', margin: 0
    });

    slide.addText("BusHound Python\n系統操作與圖文手冊", {
        x: 1.2, y: 1.6, w: 7.6, h: 1.3,
        fontSize: 30, fontFace: 'Arial', bold: true,
        color: 'FFFFFF', lineSpacingMultiple: 1.1, margin: 0
    });

    slide.addText("Windows SCSI Pass-Through (SPTD) 與 64-Byte VUC 特權指令深度除錯工具", {
        x: 1.2, y: 3.0, w: 7.6, h: 0.4,
        fontSize: 13, fontFace: 'Arial',
        color: '94A3B8', margin: 0
    });

    const features = [
        { label: "⚡ 原生 Win32 直通", desc: "IOCTL_SCSI_PASS_THROUGH 免安裝驅動" },
        { label: "🛡️ 獨佔保護與解鎖", desc: "FSCTL_LOCK + AP_Key 3-step 序列" },
        { label: "📊 即時封包解析", desc: "CDB / Sense Key / Hexdump 全紀錄" }
    ];

    features.forEach((feat, idx) => {
        const xPos = 1.2 + idx * 2.6;
        slide.addShape(pptx.ShapeType.roundRect, {
            x: xPos, y: 3.6, w: 2.4, h: 0.9,
            fill: { color: '0F172A' },
            line: { color: '1E293B', width: 1 },
            rectRadius: 0.1
        });
        slide.addText(feat.label, {
            x: xPos + 0.1, y: 3.68, w: 2.2, h: 0.28,
            fontSize: 10.5, fontFace: 'Arial', bold: true,
            color: C_PRIMARY, margin: 0
        });
        slide.addText(feat.desc, {
            x: xPos + 0.1, y: 3.98, w: 2.2, h: 0.45,
            fontSize: 8.5, fontFace: 'Arial',
            color: 'CBD5E1', lineSpacingMultiple: 1.1, margin: 0
        });
    });
}

// ==========================================
// SLIDE 2: 系統整體架構與模組劃分
// ==========================================
{
    const slide = pptx.addSlide();
    slide.background = { color: C_BG_LIGHT };
    addHeader(slide, "系統架構", "模組職責劃分與 3 大核心分頁", 2);

    slide.addShape(pptx.ShapeType.roundRect, {
        x: 0.8, y: 0.9, w: 4.0, h: 4.2,
        fill: { color: C_CARD_BG },
        line: { color: C_CARD_BORDER, width: 1 },
        rectRadius: 0.15
    });
    slide.addShape(pptx.ShapeType.roundRect, {
        x: 1.0, y: 1.1, w: 3.6, h: 0.38,
        fill: { color: C_PRIMARY_LIGHT },
        rectRadius: 0.1
    });
    slide.addText("🖥️ 前端介面層 (src/BusHound.py)", {
        x: 1.0, y: 1.1, w: 3.6, h: 0.38,
        fontSize: 11.5, fontFace: 'Arial', bold: true,
        color: C_PRIMARY, align: 'center', valign: 'middle', margin: 0
    });
    slide.addText([
        { text: "• Global Header", bold: true },
        { text: "：實體磁碟動態掃描與選擇下拉清單\n", color: C_TEXT_MUTED },
        { text: "• Tab 1 (16-Byte SCSI)", bold: true },
        { text: "：標準 CDB 編輯、長度輸入、Data-In/Out 載入與 Hexdump\n", color: C_TEXT_MUTED },
        { text: "• Tab 2 (64-Byte VUC)", bold: true },
        { text: "：AP_Key 認證序列、獨佔鎖定切換與長度自動計算\n", color: C_TEXT_MUTED },
        { text: "• Tab 3 (Packet Sniffer)", bold: true, color: C_PRIMARY },
        { text: "：即時封包表格監聽、Hexdump 檢視與 CSV 匯出\n", color: C_TEXT_MUTED },
        { text: "• UAC 自提權", bold: true },
        { text: "：啟動時自動檢查 Admin 並以 runas 提權", color: C_TEXT_MUTED }
    ], {
        x: 1.1, y: 1.65, w: 3.4, h: 3.2,
        fontSize: 9.5, fontFace: 'Arial', color: C_TEXT_DARK,
        lineSpacingMultiple: 1.15, margin: 0
    });

    slide.addShape(pptx.ShapeType.roundRect, {
        x: 5.2, y: 0.9, w: 4.0, h: 4.2,
        fill: { color: C_CARD_BG },
        line: { color: C_CARD_BORDER, width: 1 },
        rectRadius: 0.15
    });
    slide.addShape(pptx.ShapeType.roundRect, {
        x: 5.4, y: 1.1, w: 3.6, h: 0.38,
        fill: { color: C_SUCCESS_LIGHT },
        rectRadius: 0.1
    });
    slide.addText("⚙️ 後端核心引擎 (src/backend_storage.py)", {
        x: 5.4, y: 1.1, w: 3.6, h: 0.38,
        fontSize: 11.5, fontFace: 'Arial', bold: true,
        color: C_SUCCESS, align: 'center', valign: 'middle', margin: 0
    });
    slide.addText([
        { text: "• SPTD 通訊核心", bold: true },
        { text: "：64-bit 自然 8-byte 對齊 (56B) SPTD_WITH_SENSE 結構體\n", color: C_TEXT_MUTED },
        { text: "• 磁碟安全控制", bold: true },
        { text: "：CreateFileW 握柄管理與 FSCTL_LOCK_VOLUME 獨佔鎖定\n", color: C_TEXT_MUTED },
        { text: "• 協定智能解析", bold: true },
        { text: "：標準 SCSI Opcode、VUC 0x06 特殊序列與 18B Sense Key/ASC/ASCQ\n", color: C_TEXT_MUTED },
        { text: "• PacketLogger", bold: true, color: C_SUCCESS },
        { text: "：Thread-safe 封包歷程記錄、即時 Callback 與 CSV 匯出", color: C_TEXT_MUTED }
    ], {
        x: 5.5, y: 1.65, w: 3.4, h: 3.2,
        fontSize: 9.5, fontFace: 'Arial', color: C_TEXT_DARK,
        lineSpacingMultiple: 1.15, margin: 0
    });
}

// ==========================================
// SLIDE 3: 啟動流程與全域磁碟配置 (含實體截圖)
// ==========================================
{
    const slide = pptx.addSlide();
    slide.background = { color: C_BG_LIGHT };
    addHeader(slide, "快速上手", "系統啟動與目標磁碟配置", 3);

    slide.addShape(pptx.ShapeType.roundRect, {
        x: 0.8, y: 0.85, w: 8.4, h: 1.2,
        fill: { color: C_CARD_BG },
        line: { color: C_PRIMARY, width: 1.5 },
        rectRadius: 0.1
    });
    slide.addImage({
        path: IMG_HEADER,
        x: 0.9, y: 0.95, w: 8.2, h: 0.95,
        sizing: { type: 'contain' }
    });

    const steps = [
        {
            num: "STEP 1", title: "管理員提權啟動",
            badge: "Admin UAC", badgeColor: C_DANGER_LIGHT, textColor: C_DANGER,
            desc: "雙擊 BusHound.exe 啟動，系統自動彈出 Windows UAC 提權確認，點擊「是」進入無黑視窗 GUI 介面。"
        },
        {
            num: "STEP 2", title: "自動/手動掃描",
            badge: "PowerShell CIM", badgeColor: C_PRIMARY_LIGHT, textColor: C_PRIMARY,
            desc: "啟動時自動透過 PowerShell CIM 掃描硬碟；若熱插拔外接裝置，點擊頂部「🔄 Rescan」即時重新整理清單。"
        },
        {
            num: "STEP 3", title: "選定目標裝置",
            badge: "Target Drive", badgeColor: C_SUCCESS_LIGHT, textColor: C_SUCCESS,
            desc: "由下拉選單選取待測硬碟（顯示磁碟編號與完整型號，如 PhysicalDrive1 - CT500MX500SSD1）。"
        }
    ];

    steps.forEach((step, idx) => {
        const xPos = 0.8 + idx * 2.9;
        slide.addShape(pptx.ShapeType.roundRect, {
            x: xPos, y: 2.2, w: 2.65, h: 2.9,
            fill: { color: C_CARD_BG },
            line: { color: C_CARD_BORDER, width: 1 },
            rectRadius: 0.15
        });

        slide.addShape(pptx.ShapeType.roundRect, {
            x: xPos + 0.15, y: 2.35, w: 1.0, h: 0.28,
            fill: { color: step.badgeColor },
            rectRadius: 0.08
        });
        slide.addText(step.num, {
            x: xPos + 0.15, y: 2.35, w: 1.0, h: 0.28,
            fontSize: 9.5, fontFace: 'Arial', bold: true,
            color: step.textColor, align: 'center', valign: 'middle', margin: 0
        });

        slide.addText(step.title, {
            x: xPos + 0.15, y: 2.7, w: 2.35, h: 0.3,
            fontSize: 12.5, fontFace: 'Arial', bold: true,
            color: C_TEXT_DARK, margin: 0
        });

        slide.addText(step.desc, {
            x: xPos + 0.15, y: 3.1, w: 2.35, h: 1.8,
            fontSize: 9, fontFace: 'Arial', color: C_TEXT_MUTED,
            lineSpacingMultiple: 1.2, margin: 0
        });
    });
}

// ==========================================
// SLIDE 4: Tab 1 — 標準 SCSI (16-Byte) 操作 (含實際畫面)
// ==========================================
{
    const slide = pptx.addSlide();
    slide.background = { color: C_BG_LIGHT };
    addHeader(slide, "Tab 1 操作", "標準 16-Byte SCSI 指令操作與實際畫面", 4);

    slide.addShape(pptx.ShapeType.roundRect, {
        x: 0.8, y: 0.85, w: 4.1, h: 4.25,
        fill: { color: C_CARD_BG },
        line: { color: C_CARD_BORDER, width: 1 },
        rectRadius: 0.15
    });
    slide.addText("📝 指令配置 4 步驟", {
        x: 1.0, y: 1.0, w: 3.7, h: 0.3,
        fontSize: 13, fontFace: 'Arial', bold: true,
        color: C_PRIMARY, margin: 0
    });

    const t1Steps = [
        { title: "1. 選擇傳輸方向", desc: "選取 Data In (讀取) / Data Out (寫入) / No Data" },
        { title: "2. 設定 16-Byte CDB", desc: "在 16 格矩陣輸入 Hex 或點擊「載入 CDB .bin」" },
        { title: "3. 設定傳輸長度與 Buffer", desc: "輸入 Bytes 數；若為 Data Out 可載入 .bin 檔" },
        { title: "4. 執行與結果解析", desc: "點擊「EXECUTE SCSI CMD」發送；終端即時顯示 Opcode、狀態碼與 Hexdump" }
    ];

    t1Steps.forEach((s, idx) => {
        const yPos = 1.38 + idx * 0.82;
        slide.addShape(pptx.ShapeType.roundRect, {
            x: 1.0, y: yPos, w: 3.7, h: 0.72,
            fill: { color: C_BG_LIGHT },
            line: { color: C_CARD_BORDER, width: 0.5 },
            rectRadius: 0.08
        });
        slide.addText(s.title, {
            x: 1.12, y: yPos + 0.06, w: 3.5, h: 0.22,
            fontSize: 10, fontFace: 'Arial', bold: true,
            color: C_TEXT_DARK, margin: 0
        });
        slide.addText(s.desc, {
            x: 1.12, y: yPos + 0.28, w: 3.5, h: 0.4,
            fontSize: 8.5, fontFace: 'Arial', color: C_TEXT_MUTED,
            lineSpacingMultiple: 1.1, margin: 0
        });
    });

    slide.addShape(pptx.ShapeType.roundRect, {
        x: 5.1, y: 0.85, w: 4.1, h: 4.25,
        fill: { color: C_CARD_BG },
        line: { color: C_PRIMARY, width: 1.5 },
        rectRadius: 0.15
    });
    slide.addText("📸 實際操作畫面 (INQUIRY 0x12 執行結果)", {
        x: 5.25, y: 0.95, w: 3.8, h: 0.25,
        fontSize: 10, fontFace: 'Arial', bold: true,
        color: C_PRIMARY, align: 'center', margin: 0
    });
    slide.addImage({
        path: IMG_TAB1,
        x: 5.2, y: 1.25, w: 3.9, h: 3.75,
        sizing: { type: 'contain' }
    });
}

// ==========================================
// SLIDE 5: Tab 2 — 特權解鎖與 64-Byte VUC (含實際畫面)
// ==========================================
{
    const slide = pptx.addSlide();
    slide.background = { color: C_BG_LIGHT };
    addHeader(slide, "Tab 2 操作", "AP_Key 特權解鎖與 64-Byte VUC 實際畫面", 5);

    slide.addShape(pptx.ShapeType.roundRect, {
        x: 0.8, y: 0.85, w: 4.1, h: 4.25,
        fill: { color: C_CARD_BG },
        line: { color: C_CARD_BORDER, width: 1 },
        rectRadius: 0.15
    });
    slide.addText("🛡️ 特權解鎖與 3 階段通訊流程", {
        x: 1.0, y: 1.0, w: 3.7, h: 0.3,
        fontSize: 13, fontFace: 'Arial', bold: true,
        color: C_DANGER, margin: 0
    });

    const t2Features = [
        {
            title: "1. AP_KEY 3-Step 解鎖認證",
            desc: "勾選後自動搜尋 AP_Key/ap_key.bin，發送 0xFE 0xC0 (送金鑰) -> 0xC1 (觸發) -> 0xC3 (讀取狀態)。"
        },
        {
            title: "2. Lock Device 獨佔防干擾",
            desc: "透過 Windows FSCTL_LOCK_VOLUME 獨佔鎖定磁碟，防止 OS 背景 I/O 破壞特權模式。"
        },
        {
            title: "3. 64-Byte VUC 傳輸序列",
            desc: "• Phase 1 (0xC0): 送 64B Payload\n• Phase 2 (0xC1/C2): 傳輸 Data-In/Out\n• Phase 3 (0xC3): 讀取韌體執行狀態"
        },
        {
            title: "4. 長度自動計算與安全上限",
            desc: "Offset 40~43 自動解析長度 (raw*4)，超大長度 (>256MB) 自動安全攔截。"
        }
    ];

    t2Features.forEach((f, idx) => {
        const yPos = 1.38 + idx * 0.88;
        slide.addShape(pptx.ShapeType.roundRect, {
            x: 1.0, y: yPos, w: 3.7, h: 0.8,
            fill: { color: C_BG_LIGHT },
            line: { color: C_CARD_BORDER, width: 0.5 },
            rectRadius: 0.08
        });
        slide.addText(f.title, {
            x: 1.12, y: yPos + 0.05, w: 3.5, h: 0.22,
            fontSize: 9.5, fontFace: 'Arial', bold: true,
            color: C_TEXT_DARK, margin: 0
        });
        slide.addText(f.desc, {
            x: 1.12, y: yPos + 0.26, w: 3.5, h: 0.5,
            fontSize: 8, fontFace: 'Arial', color: C_TEXT_MUTED,
            lineSpacingMultiple: 1.1, margin: 0
        });
    });

    slide.addShape(pptx.ShapeType.roundRect, {
        x: 5.1, y: 0.85, w: 4.1, h: 4.25,
        fill: { color: C_CARD_BG },
        line: { color: C_DANGER, width: 1.5 },
        rectRadius: 0.15
    });
    slide.addText("📸 實際操作畫面 (64-Byte VUC 與 AP_Key 執行)", {
        x: 5.25, y: 0.95, w: 3.8, h: 0.25,
        fontSize: 10, fontFace: 'Arial', bold: true,
        color: C_DANGER, align: 'center', margin: 0
    });
    slide.addImage({
        path: IMG_TAB2,
        x: 5.2, y: 1.25, w: 3.9, h: 3.75,
        sizing: { type: 'contain' }
    });
}

// ==========================================
// SLIDE 6: Tab 3 — Packet Sniffer (即時封包監控)
// ==========================================
{
    const slide = pptx.addSlide();
    slide.background = { color: C_BG_LIGHT };
    addHeader(slide, "Tab 3 操作", "即時封包監控與 Payload 詳細檢視", 6);

    slide.addShape(pptx.ShapeType.roundRect, {
        x: 0.8, y: 0.85, w: 4.1, h: 4.25,
        fill: { color: C_CARD_BG },
        line: { color: C_CARD_BORDER, width: 1 },
        rectRadius: 0.15
    });
    slide.addText("🔍 封包監聽與檢視 4 大亮點", {
        x: 1.0, y: 1.0, w: 3.7, h: 0.3,
        fontSize: 13, fontFace: 'Arial', bold: true,
        color: C_PRIMARY, margin: 0
    });

    const t3Features = [
        {
            title: "1. 全域自動監控與標籤",
            desc: "Tab 1 與 Tab 2 執行的所有指令自動錄製；以綠色 (Data-In)、橘色 (Data-Out) 與紅色 (Error) 標示方向與狀態。"
        },
        {
            title: "2. 毫秒級延遲與狀態分析",
            desc: "精確記錄時間戳記 (HH:MM:SS.mmm)、傳輸 Bytes 數、SCSI Status 及硬體回應延遲 (ms)。"
        },
        {
            title: "3. 點選檢視 CDB 與 Hexdump",
            desc: "點選上方任意封包，下方 Inspector 自動呈現完整 16-Byte CDB、Sense Data 解析與綠底高對比 Hexdump。"
        },
        {
            title: "4. CSV 匯出與 Payload 另存",
            desc: "支援一鍵「💾 匯出 CSV」完整記錄；點選特定封包可「💾 另存 Payload (.bin)」二進位檔案。"
        }
    ];

    t3Features.forEach((f, idx) => {
        const yPos = 1.38 + idx * 0.88;
        slide.addShape(pptx.ShapeType.roundRect, {
            x: 1.0, y: yPos, w: 3.7, h: 0.8,
            fill: { color: C_BG_LIGHT },
            line: { color: C_CARD_BORDER, width: 0.5 },
            rectRadius: 0.08
        });
        slide.addText(f.title, {
            x: 1.12, y: yPos + 0.05, w: 3.5, h: 0.22,
            fontSize: 9.5, fontFace: 'Arial', bold: true,
            color: C_TEXT_DARK, margin: 0
        });
        slide.addText(f.desc, {
            x: 1.12, y: yPos + 0.26, w: 3.5, h: 0.5,
            fontSize: 8, fontFace: 'Arial', color: C_TEXT_MUTED,
            lineSpacingMultiple: 1.1, margin: 0
        });
    });

    slide.addShape(pptx.ShapeType.roundRect, {
        x: 5.1, y: 0.85, w: 4.1, h: 4.25,
        fill: { color: C_CARD_BG },
        line: { color: C_PRIMARY, width: 1.5 },
        rectRadius: 0.15
    });
    slide.addText("📸 實際操作畫面 (Packet Sniffer & Inspector)", {
        x: 5.25, y: 0.95, w: 3.8, h: 0.25,
        fontSize: 10, fontFace: 'Arial', bold: true,
        color: C_PRIMARY, align: 'center', margin: 0
    });
    slide.addImage({
        path: IMG_TAB3,
        x: 5.2, y: 1.25, w: 3.9, h: 3.75,
        sizing: { type: 'contain' }
    });
}

// ==========================================
// SLIDE 7: 狀態碼、Sense Data 與除錯排查
// ==========================================
{
    const slide = pptx.addSlide();
    slide.background = { color: C_BG_LIGHT };
    addHeader(slide, "錯誤排查", "SCSI 狀態碼與 Sense Data 解析指引", 7);

    const statusData = [
        { code: "0x00", name: "GOOD", meaning: "指令成功執行完成", color: C_SUCCESS_LIGHT, textCol: C_SUCCESS },
        { code: "0x02", name: "CHECK CONDITION", meaning: "裝置回傳錯誤，需解析 Sense Data", color: C_DANGER_LIGHT, textCol: C_DANGER },
        { code: "0x08", name: "BUSY", meaning: "硬體忙碌，請重試或增加逾時", color: C_WARNING_LIGHT, textCol: C_WARNING }
    ];

    statusData.forEach((st, idx) => {
        const xPos = 0.8 + idx * 2.9;
        slide.addShape(pptx.ShapeType.roundRect, {
            x: xPos, y: 0.85, w: 2.65, h: 1.0,
            fill: { color: st.color },
            rectRadius: 0.1
        });
        slide.addText(`${st.code} : ${st.name}`, {
            x: xPos + 0.15, y: 0.95, w: 2.35, h: 0.3,
            fontSize: 12, fontFace: 'Arial', bold: true,
            color: st.textCol, margin: 0
        });
        slide.addText(st.meaning, {
            x: xPos + 0.15, y: 1.3, w: 2.35, h: 0.45,
            fontSize: 9.5, fontFace: 'Arial', color: C_TEXT_DARK, margin: 0
        });
    });

    slide.addShape(pptx.ShapeType.roundRect, {
        x: 0.8, y: 2.05, w: 8.4, h: 3.05,
        fill: { color: C_CARD_BG },
        line: { color: C_CARD_BORDER, width: 1 },
        rectRadius: 0.15
    });
    slide.addText("🔍 常見 Sense Key 與排除建議", {
        x: 1.0, y: 2.2, w: 8.0, h: 0.3,
        fontSize: 12, fontFace: 'Arial', bold: true,
        color: C_TEXT_DARK, margin: 0
    });

    const senseKeys = [
        { key: "0x02 NOT READY", reason: "裝置尚未就緒或處於睡眠模式", action: "發送 START STOP UNIT (0x1B) 喚醒磁碟" },
        { key: "0x05 ILLEGAL REQUEST", reason: "CDB 欄位無效、LBA 超出範圍或未解鎖特權", action: "確認 AP_Key 是否先認證成功；檢查傳輸長度" },
        { key: "0x06 UNIT ATTENTION", reason: "裝置剛經歷重置 (Power-on Reset) 或匯流排重置", action: "重新發送一次相同指令即可清除此條件" },
        { key: "0x07 DATA PROTECT", reason: "磁碟處於防寫狀態 (Write-Protected)", action: "檢查硬碟開關或解除韌體唯讀保護" }
    ];

    senseKeys.forEach((sk, idx) => {
        const yPos = 2.6 + idx * 0.58;
        slide.addText(`• ${sk.key}`, {
            x: 1.0, y: yPos, w: 2.4, h: 0.25,
            fontSize: 10, fontFace: 'Arial', bold: true,
            color: C_PRIMARY, margin: 0
        });
        slide.addText(`原因: ${sk.reason}`, {
            x: 3.4, y: yPos, w: 2.8, h: 0.5,
            fontSize: 8.5, fontFace: 'Arial', color: C_TEXT_DARK, margin: 0
        });
        slide.addText(`處置: ${sk.action}`, {
            x: 6.3, y: yPos, w: 2.7, h: 0.5,
            fontSize: 8.5, fontFace: 'Arial', color: C_SUCCESS, margin: 0
        });
    });
}

// ==========================================
// SLIDE 8: 工程維護、單元測試與打包發布
// ==========================================
{
    const slide = pptx.addSlide();
    slide.background = { color: C_BG_LIGHT };
    addHeader(slide, "工程維護", "架構規範、41 項測試與 PyInstaller 打包", 8);

    slide.addShape(pptx.ShapeType.roundRect, {
        x: 0.8, y: 0.85, w: 4.1, h: 4.25,
        fill: { color: C_CARD_BG },
        line: { color: C_CARD_BORDER, width: 1 },
        rectRadius: 0.15
    });
    slide.addText("🧪 強制測試規範 (41 Tests PASS)", {
        x: 1.0, y: 1.05, w: 3.7, h: 0.3,
        fontSize: 12.5, fontFace: 'Arial', bold: true,
        color: C_SUCCESS, margin: 0
    });
    slide.addText([
        { text: "所有程式更新均須通過全套測試：\n\n", color: C_TEXT_MUTED },
        { text: "• tests/test_backend.py (23 項)\n", bold: true, color: C_TEXT_DARK },
        { text: "  - 64-bit SPTD (56B) 自然對齊與 IOCTL\n  - PacketLogger、CDB/Sense 解析與 CSV\n\n", color: C_TEXT_MUTED },
        { text: "• tests/test_gui.py (8 項)\n", bold: true, color: C_TEXT_DARK },
        { text: "  - Tab 1 / Tab 2 矩陣清空與安全長度\n  - Tab 3 Sniffer 開關、選取與 CSV 匯出\n\n", color: C_TEXT_MUTED },
        { text: "• tests/test_simulation.py (10 項)\n", bold: true, color: C_TEXT_DARK },
        { text: "  - 虛擬硬碟 LBA 讀寫迴圈與故障注入", color: C_TEXT_MUTED }
    ], {
        x: 1.0, y: 1.45, w: 3.7, h: 2.8,
        fontSize: 8.8, fontFace: 'Arial', lineSpacingMultiple: 1.15, margin: 0
    });

    slide.addShape(pptx.ShapeType.roundRect, {
        x: 1.0, y: 4.35, w: 3.7, h: 0.55,
        fill: { color: C_NAVY_CARD },
        rectRadius: 0.08
    });
    slide.addText("python -m unittest discover -s tests -p \"test_*.py\"", {
        x: 1.1, y: 4.35, w: 3.5, h: 0.55,
        fontSize: 8, fontFace: 'Courier New', color: '6EE7B7',
        valign: 'middle', margin: 0
    });

    slide.addShape(pptx.ShapeType.roundRect, {
        x: 5.1, y: 0.85, w: 4.1, h: 4.25,
        fill: { color: C_CARD_BG },
        line: { color: C_CARD_BORDER, width: 1 },
        rectRadius: 0.15
    });
    slide.addText("📦 一鍵發布為無黑視窗 EXE", {
        x: 5.3, y: 1.05, w: 3.7, h: 0.3,
        fontSize: 12.5, fontFace: 'Arial', bold: true,
        color: C_PRIMARY, margin: 0
    });
    slide.addText([
        { text: "發布時使用 PyInstaller 封裝為單一可執行檔：\n\n", color: C_TEXT_MUTED },
        { text: "• --onefile", bold: true, color: C_PRIMARY },
        { text: "：打包為獨立 BusHound.exe\n", color: C_TEXT_MUTED },
        { text: "• --windowed", bold: true, color: C_PRIMARY },
        { text: "：抑制背景 CMD 黑視窗\n", color: C_TEXT_MUTED },
        { text: "• --paths src", bold: true, color: C_PRIMARY },
        { text: "：將 backend_storage.py 納入打包\n\n", color: C_TEXT_MUTED },
        { text: "部署結構：", bold: true, color: C_TEXT_DARK },
        { text: "只需複製 BusHound.exe 與 AP_Key/ap_key.bin 即可於任意 Windows 10/11 運作。", color: C_TEXT_MUTED }
    ], {
        x: 5.3, y: 1.45, w: 3.7, h: 2.8,
        fontSize: 9, fontFace: 'Arial', lineSpacingMultiple: 1.15, margin: 0
    });

    slide.addShape(pptx.ShapeType.roundRect, {
        x: 5.3, y: 4.35, w: 3.7, h: 0.55,
        fill: { color: C_NAVY_CARD },
        rectRadius: 0.08
    });
    slide.addText("pyinstaller --onefile --windowed --paths src --name BusHound src/BusHound.py", {
        x: 5.4, y: 4.35, w: 3.5, h: 0.55,
        fontSize: 7.2, fontFace: 'Courier New', color: '93C5FD',
        valign: 'middle', margin: 0
    });
}

// ==========================================
// SLIDE 9: 操作快速指引 (Cheat-Sheet)
// ==========================================
{
    const slide = pptx.addSlide();
    slide.background = { color: C_BG_DARK };

    slide.addShape(pptx.ShapeType.roundRect, {
        x: 0.8, y: 0.6, w: 8.4, h: 4.4,
        fill: { color: C_NAVY_CARD },
        line: { color: '334155', width: 1.5 },
        rectRadius: 0.2
    });

    slide.addText("BusHound 操作快速指引 (Cheat-Sheet)", {
        x: 1.2, y: 0.85, w: 7.6, h: 0.4,
        fontSize: 22, fontFace: 'Arial', bold: true,
        color: 'FFFFFF', margin: 0
    });

    const tips = [
        { title: "1. 權限第一", desc: "SPTD 必須使用 Admin 權限，若未提權將無法開啟 PhysicalDrive 握柄。" },
        { title: "2. 謹慎寫入", desc: "Data Out 與寫入指令將直接改寫磁碟 Sector，測試前務必確認 Target Drive 編號。" },
        { title: "3. 善用鎖定", desc: "執行特權 VUC 或連續通訊時，務必勾選 Lock Device 避免 Windows OS 背景干擾。" },
        { title: "4. 封包監控", desc: "Tab 3 自動錄製所有自發指令，支援毫秒延遲分析、Hexdump 檢視與 CSV 匯出。" }
    ];

    tips.forEach((tip, idx) => {
        const xPos = (idx % 2 === 0) ? 1.2 : 5.1;
        const yPos = (idx < 2) ? 1.5 : 2.85;
        slide.addShape(pptx.ShapeType.roundRect, {
            x: xPos, y: yPos, w: 3.7, h: 1.15,
            fill: { color: '0F172A' },
            line: { color: '334155', width: 1 },
            rectRadius: 0.1
        });
        slide.addText(tip.title, {
            x: xPos + 0.15, y: yPos + 0.12, w: 3.4, h: 0.25,
            fontSize: 12, fontFace: 'Arial', bold: true,
            color: C_PRIMARY, margin: 0
        });
        slide.addText(tip.desc, {
            x: xPos + 0.15, y: yPos + 0.42, w: 3.4, h: 0.65,
            fontSize: 9.5, fontFace: 'Arial', color: 'CBD5E1',
            lineSpacingMultiple: 1.15, margin: 0
        });
    });

    slide.addText("BusHound Python Storage Debug Tool  •  Ready for Production", {
        x: 1.2, y: 4.35, w: 7.6, h: 0.3,
        fontSize: 10, fontFace: 'Arial', color: C_TEXT_MUTED,
        align: 'center', margin: 0
    });
}

// 輸出檔案路徑
const outputPath = path.join(__dirname, 'BusHound_Operation_Guide.pptx');
const fallbackPath = path.join(__dirname, 'BusHound_Operation_Guide_v2.pptx');

pptx.writeFile({ fileName: outputPath })
    .then(fileName => {
        console.log(`PPTX 成功產出至: ${fileName}`);
    })
    .catch(err => {
        if (err.code === 'EBUSY') {
            console.log(`主檔案被 PowerPoint 開啟鎖定中，改寫入至備用檔案: ${fallbackPath}`);
            pptx.writeFile({ fileName: fallbackPath })
                .then(f => console.log(`備用 PPTX 成功產出至: ${f}`))
                .catch(e => console.error('備用 PPTX 產出失敗:', e));
        } else {
            console.error('PPTX 產出失敗:', err);
            process.exit(1);
        }
    });
