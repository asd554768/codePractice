const pptxgen = require('pptxgenjs');
const path = require('path');
const fs = require('fs');

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_16x9';

// 色彩系統定義
const C_BG_DARK = '0F172A';      // 深海軍藍
const C_BG_LIGHT = 'F8FAFC';     // 柔和淺灰白
const C_CARD_BG = 'FFFFFF';      // 純白
const C_CARD_BORDER = 'E2E8F0';  // 邊框淺灰
const C_TEXT_DARK = '0F172A';    // 主標題文字
const C_TEXT_MUTED = '64748B';   // 次要文字
const C_PRIMARY = '0284C7';      // 科技湛藍
const C_PRIMARY_LIGHT = 'E0F2FE';// 湛藍淺底
const C_SUCCESS = '10B981';      // 翡翠綠
const C_SUCCESS_LIGHT = 'D1FAE5';// 翡翠綠淺底
const C_WARNING = 'F59E0B';      // 琥珀橘
const C_WARNING_LIGHT = 'FEF3C7';// 橘色淺底
const C_DANGER = 'EF4444';       // 緋紅
const C_DANGER_LIGHT = 'FEE2E2'; // 紅色淺底
const C_NAVY_CARD = '1E293B';    // 深色終端卡片

// 圖片路徑
const IMG_TAB4 = path.join(__dirname, 'assets', 'screenshot_tab4_fw_update.png');

// 輔助函式：新增標準內容頁 Header
function addHeader(slide, category, title, pageNum) {
    slide.addShape(pptx.ShapeType.roundRect, {
        x: 0.8, y: 0.35, w: 2.0, h: 0.3,
        fill: { color: C_PRIMARY_LIGHT },
        line: { color: C_PRIMARY, width: 1 },
        rectRadius: 0.15
    });
    slide.addText(category, {
        x: 0.8, y: 0.35, w: 2.0, h: 0.3,
        fontSize: 10, fontFace: 'Arial', bold: true,
        color: C_PRIMARY, align: 'center', valign: 'middle', margin: 0
    });

    slide.addText(title, {
        x: 2.9, y: 0.3, w: 6.0, h: 0.4,
        fontSize: 18, fontFace: 'Arial', bold: true,
        color: C_TEXT_DARK, valign: 'middle', margin: 0
    });

    slide.addText(`MCU Firmware Update Test Report  |  Page ${pageNum}`, {
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
        x: 0.8, y: 0.8, w: 2.8, h: 0.35,
        fill: { color: '1E3A8A' },
        line: { color: '3B82F6', width: 1 },
        rectRadius: 0.15
    });
    slide.addText('QA & FUNCTIONAL TEST REPORT', {
        x: 0.8, y: 0.8, w: 2.8, h: 0.35,
        fontSize: 10, fontFace: 'Arial', bold: true,
        color: '93C5FD', align: 'center', valign: 'middle'
    });

    slide.addText('SCSI MCU 韌體更新功能\n單元測試與實際成效驗證報告', {
        x: 0.8, y: 1.3, w: 8.4, h: 1.5,
        fontSize: 28, fontFace: 'Arial', bold: true,
        color: 'FFFFFF', lineSpacing: 36
    });

    slide.addText('全面性單元測試 (84 項全數 PASS)  |  28KB 韌體分塊傳輸  |  CDB Address 自動遞增與狀態確認', {
        x: 0.8, y: 2.9, w: 8.4, h: 0.4,
        fontSize: 12, fontFace: 'Arial',
        color: '94A3B8'
    });

    // 關鍵指標摘要卡片
    const metrics = [
        { label: '單元測試總數', val: '84 項', sub: 'PASS 率 100%', col: C_SUCCESS },
        { label: '韌體分塊驗證', val: '224 塊', sub: '28,672 Bytes (28KB)', col: C_PRIMARY },
        { label: 'Address 遞增', val: '+0x80', sub: '0x0000 → 0x6F80', col: C_WARNING },
        { label: '通訊狀態確認', val: '0x00 GOOD', sub: '同步無阻塞確認', col: 'A855F7' }
    ];

    metrics.forEach((m, idx) => {
        const xPos = 0.8 + idx * 2.15;
        slide.addShape(pptx.ShapeType.roundRect, {
            x: xPos, y: 3.5, w: 2.0, h: 1.4,
            fill: { color: C_NAVY_CARD },
            line: { color: '334155', width: 1 },
            rectRadius: 0.1
        });
        slide.addText(m.label, {
            x: xPos + 0.1, y: 3.6, w: 1.8, h: 0.25,
            fontSize: 9, fontFace: 'Arial', color: '94A3B8', align: 'center'
        });
        slide.addText(m.val, {
            x: xPos + 0.1, y: 3.85, w: 1.8, h: 0.5,
            fontSize: 20, fontFace: 'Arial', bold: true, color: m.col, align: 'center'
        });
        slide.addText(m.sub, {
            x: xPos + 0.1, y: 4.4, w: 1.8, h: 0.35,
            fontSize: 8.5, fontFace: 'Arial', color: 'CBD5E1', align: 'center'
        });
    });

    slide.addText('BusHound Storage Debug Tool v2.5  |  執行環境: Windows 10/11 x64  |  測試日期: 2026-08', {
        x: 0.8, y: 5.15, w: 8.4, h: 0.3,
        fontSize: 9, fontFace: 'Arial', color: '64748B'
    });
}

// ==========================================
// SLIDE 2: 測試總覽與品質指標 (Executive Summary)
// ==========================================
{
    const slide = pptx.addSlide();
    slide.background = { color: C_BG_LIGHT };
    addHeader(slide, 'TEST SUMMARY', '測試總覽與品質保證指標', 2);

    // 左欄：測試分佈卡片 (4 大測試套件)
    slide.addShape(pptx.ShapeType.roundRect, {
        x: 0.8, y: 0.85, w: 4.1, h: 4.25,
        fill: { color: C_CARD_BG },
        line: { color: C_CARD_BORDER, width: 1 },
        rectRadius: 0.15
    });
    slide.addText('📊 測試套件架構分佈 (84/84 PASS)', {
        x: 1.0, y: 1.0, w: 3.7, h: 0.3,
        fontSize: 13, fontFace: 'Arial', bold: true, color: C_TEXT_DARK
    });

    const suites = [
        { name: 'test_firmware.py (新增)', count: '43 項', desc: '排序/Address計算/CDB組裝/Worker/GUI', col: C_SUCCESS },
        { name: 'test_backend.py', count: '23 項', desc: 'SPTD結構/協定解析/PacketLogger/Lock', col: C_PRIMARY },
        { name: 'test_simulation.py', count: '10 項', desc: '虛擬硬體端到端/Fault Injection模擬', col: '8B5CF6' },
        { name: 'test_gui.py', count: '8 項', desc: 'Tab 1/2/3 介面狀態與事件防呆邏輯', col: C_WARNING }
    ];

    suites.forEach((s, idx) => {
        const yPos = 1.45 + idx * 0.85;
        slide.addShape(pptx.ShapeType.roundRect, {
            x: 1.0, y: yPos, w: 3.7, h: 0.72,
            fill: { color: C_BG_LIGHT },
            line: { color: 'E2E8F0', width: 1 },
            rectRadius: 0.08
        });
        slide.addText(s.name, {
            x: 1.15, y: yPos + 0.08, w: 2.5, h: 0.25,
            fontSize: 10, fontFace: 'Arial', bold: true, color: C_TEXT_DARK
        });
        slide.addText(s.count, {
            x: 3.65, y: yPos + 0.08, w: 0.9, h: 0.25,
            fontSize: 10, fontFace: 'Arial', bold: true, color: s.col, align: 'right'
        });
        slide.addText(s.desc, {
            x: 1.15, y: yPos + 0.35, w: 3.4, h: 0.3,
            fontSize: 8.5, fontFace: 'Arial', color: C_TEXT_MUTED
        });
    });

    // 右欄：品質指標與核心亮點
    slide.addShape(pptx.ShapeType.roundRect, {
        x: 5.1, y: 0.85, w: 4.1, h: 4.25,
        fill: { color: C_CARD_BG },
        line: { color: C_CARD_BORDER, width: 1 },
        rectRadius: 0.15
    });
    slide.addText('🌟 韌體更新功能核心驗證結論', {
        x: 5.3, y: 1.0, w: 3.7, h: 0.3,
        fontSize: 13, fontFace: 'Arial', bold: true, color: C_TEXT_DARK
    });

    const highlights = [
        { title: '✅ 100% 自然排序保證', desc: '採用 Regex 自然排序演算法，徹底消除 chunk_10 排在 chunk_2 前面之傳統字串排序缺陷。' },
        { title: '✅ 精確 16-bit Address 映射', desc: 'CDB[3] (MSB) 與 CDB[4] (LSB) 每塊精確累加 0x80，224 塊無一偏差（0x0000 → 0x6F80）。' },
        { title: '✅ 嚴謹狀態機與即時中斷', desc: '逐塊驗證 SCSI Status == 0x00 (GOOD)，遇 Check Condition 立即中斷並抓取 Sense Data。' },
        { title: '✅ 非同步背景工作線程', desc: 'Worker Thread 傳輸不卡死 GUI，所有介面回呼透過 root.after() 保證執行緒安全。' }
    ];

    highlights.forEach((h, idx) => {
        const yPos = 1.45 + idx * 0.85;
        slide.addText(h.title, {
            x: 5.3, y: yPos, w: 3.7, h: 0.25,
            fontSize: 10.5, fontFace: 'Arial', bold: true, color: C_PRIMARY
        });
        slide.addText(h.desc, {
            x: 5.3, y: yPos + 0.25, w: 3.7, h: 0.5,
            fontSize: 9, fontFace: 'Arial', color: C_TEXT_MUTED, lineSpacing: 12
        });
    });
}

// ==========================================
// SLIDE 3: 韌體更新架構與通訊狀態機
// ==========================================
{
    const slide = pptx.addSlide();
    slide.background = { color: C_BG_LIGHT };
    addHeader(slide, 'ARCHITECTURE', '韌體更新通訊架構與狀態機', 3);

    // 4 步驟卡片流程
    const steps = [
        { num: '01', title: '分塊檔案載入', desc: '指定資料夾掃描所有 .bin 檔案，以 natural_sort_key() 排序，校驗 128B 檔案大小。', col: C_PRIMARY },
        { num: '02', title: 'CDB 模板與地址組裝', desc: '載入 16-Byte CDB 模板，build_cdb() 動態計算 Address 寫入 CDB[3](高位) 與 CDB[4](低位)。', col: '8B5CF6' },
        { num: '03', title: '獨佔鎖定與 SPTD 傳輸', desc: '透過 FSCTL_LOCK_VOLUME 鎖定磁碟，非同步發送 128-Byte Data-Out 封包至 MCU。', col: C_WARNING },
        { num: '04', title: '狀態確認與地址累加', desc: '確認硬體回傳 0x00 (GOOD) 後 Address +0x80 遞增；若遇錯誤立即中斷並解鎖磁碟。', col: C_SUCCESS }
    ];

    steps.forEach((st, idx) => {
        const xPos = 0.8 + idx * 2.15;
        slide.addShape(pptx.ShapeType.roundRect, {
            x: xPos, y: 0.9, w: 2.0, h: 2.3,
            fill: { color: C_CARD_BG },
            line: { color: C_CARD_BORDER, width: 1 },
            rectRadius: 0.1
        });
        slide.addShape(pptx.ShapeType.roundRect, {
            x: xPos + 0.15, y: 1.05, w: 0.5, h: 0.35,
            fill: { color: st.col },
            rectRadius: 0.08
        });
        slide.addText(st.num, {
            x: xPos + 0.15, y: 1.05, w: 0.5, h: 0.35,
            fontSize: 12, fontFace: 'Arial', bold: true, color: 'FFFFFF', align: 'center', valign: 'middle'
        });
        slide.addText(st.title, {
            x: xPos + 0.15, y: 1.5, w: 1.7, h: 0.45,
            fontSize: 11, fontFace: 'Arial', bold: true, color: C_TEXT_DARK
        });
        slide.addText(st.desc, {
            x: xPos + 0.15, y: 2.0, w: 1.7, h: 1.1,
            fontSize: 8.5, fontFace: 'Arial', color: C_TEXT_MUTED, lineSpacing: 11
        });
    });

    // 下方：Address 遞增對照表與規格參數
    slide.addShape(pptx.ShapeType.roundRect, {
        x: 0.8, y: 3.4, w: 8.4, h: 1.7,
        fill: { color: C_NAVY_CARD },
        line: { color: '334155', width: 1 },
        rectRadius: 0.1
    });

    slide.addText('⚡ 28KB 韌體傳輸 Address 與 CDB 位元組對應範例 (Chunk Size = 128 Bytes, Increment = +0x80)', {
        x: 1.0, y: 3.5, w: 8.0, h: 0.25,
        fontSize: 10, fontFace: 'Arial', bold: true, color: '38BDF8'
    });

    const tblHeader = [
        { text: '分塊序號', options: { bold: true, color: 'FFFFFF', fill: { color: '1E293B' }, align: 'center', fontSize: 8.5 } },
        { text: '檔案名稱', options: { bold: true, color: 'FFFFFF', fill: { color: '1E293B' }, align: 'center', fontSize: 8.5 } },
        { text: 'Address (Hex)', options: { bold: true, color: 'FFFFFF', fill: { color: '1E293B' }, align: 'center', fontSize: 8.5 } },
        { text: 'CDB[3] (Addr High)', options: { bold: true, color: 'FFFFFF', fill: { color: '1E293B' }, align: 'center', fontSize: 8.5 } },
        { text: 'CDB[4] (Addr Low)', options: { bold: true, color: 'FFFFFF', fill: { color: '1E293B' }, align: 'center', fontSize: 8.5 } },
        { text: '傳輸長度', options: { bold: true, color: 'FFFFFF', fill: { color: '1E293B' }, align: 'center', fontSize: 8.5 } },
        { text: '預期狀態', options: { bold: true, color: 'FFFFFF', fill: { color: '1E293B' }, align: 'center', fontSize: 8.5 } }
    ];

    const tblRows = [
        ['Chunk 1', 'chunk_0.bin', '0x0000', '0x00', '0x00', '128 Bytes', '0x00 (GOOD)'],
        ['Chunk 2', 'chunk_1.bin', '0x0080', '0x00', '0x80', '128 Bytes', '0x00 (GOOD)'],
        ['Chunk 3', 'chunk_2.bin', '0x0100', '0x01', '0x00', '128 Bytes', '0x00 (GOOD)'],
        ['...', '...', '...', '...', '...', '128 Bytes', '0x00 (GOOD)'],
        ['Chunk 224', 'chunk_223.bin', '0x6F80', '0x6F', '0x80', '128 Bytes', '0x00 (GOOD)']
    ].map(row => row.map(cell => ({
        text: cell,
        options: { color: 'E2E8F0', fill: { color: '0F172A' }, align: 'center', fontSize: 8 }
    })));

    slide.addTable([tblHeader, ...tblRows], {
        x: 1.0, y: 3.8, w: 8.0, h: 1.15,
        colW: [0.9, 1.2, 1.1, 1.2, 1.2, 1.1, 1.3],
        border: { color: '334155', pt: 0.5 }
    });
}

// ==========================================
// SLIDE 4: 實際 GUI 介面與功能展示 (含截圖)
// ==========================================
{
    const slide = pptx.addSlide();
    slide.background = { color: C_BG_LIGHT };
    addHeader(slide, 'GUI DEMO', '實際 GUI 介面與韌體更新執行成效', 4);

    // 左側：實際截圖展示
    if (fs.existsSync(IMG_TAB4)) {
        slide.addImage({
            path: IMG_TAB4,
            x: 0.8, y: 0.85, w: 5.2, h: 4.25
        });
    } else {
        slide.addShape(pptx.ShapeType.roundRect, {
            x: 0.8, y: 0.85, w: 5.2, h: 4.25,
            fill: { color: C_NAVY_CARD }
        });
        slide.addText('Tab 4 GUI Screenshot', {
            x: 0.8, y: 2.5, w: 5.2, h: 0.5,
            color: 'FFFFFF', align: 'center'
        });
    }

    // 右側：4 大介面功能解析
    const uiFeatures = [
        {
            title: '📁 韌體資料夾與統計',
            desc: '自動計算 224 個檔案、28,672 Bytes 總長度與 0x7000 預計結束 Address。'
        },
        {
            title: '⚙️ 16-Byte CDB 模板矩陣',
            desc: '直觀編輯 16 格 Hex CDB，B03/B04 標註 Addr H/L，支援 .bin 檔案快速匯入。'
        },
        {
            title: '🚀 即時進度條與狀態列',
            desc: '以 Progressbar 即時顯示 100.0% 完成進度、耗時 1.48s、結束 Address 0x6F80。'
        },
        {
            title: '📜 高對比 Terminal Log',
            desc: '黑底綠字 Consolas 視窗逐塊列出 Chunk 序號、Address、CDB[3..4] 與回傳狀態。'
        }
    ];

    uiFeatures.forEach((f, idx) => {
        const yPos = 0.85 + idx * 1.05;
        slide.addShape(pptx.ShapeType.roundRect, {
            x: 6.15, y: yPos, w: 3.05, h: 0.95,
            fill: { color: C_CARD_BG },
            line: { color: C_CARD_BORDER, width: 1 },
            rectRadius: 0.1
        });
        slide.addText(f.title, {
            x: 6.25, y: yPos + 0.08, w: 2.85, h: 0.25,
            fontSize: 10, fontFace: 'Arial', bold: true, color: C_PRIMARY
        });
        slide.addText(f.desc, {
            x: 6.25, y: yPos + 0.35, w: 2.85, h: 0.55,
            fontSize: 8.5, fontFace: 'Arial', color: C_TEXT_MUTED, lineSpacing: 11
        });
    });
}

// ==========================================
// SLIDE 5: 全面性單元測試 7 層覆蓋矩陣 (43 Tests)
// ==========================================
{
    const slide = pptx.addSlide();
    slide.background = { color: C_BG_LIGHT };
    addHeader(slide, 'TEST MATRIX', '韌體模組 43 項單元測試覆蓋矩陣', 5);

    const testCategories = [
        { cat: 'A. 自然排序 (Natural Sort)', count: '4 項', items: '基礎數值排序 (chunk_10 > chunk_2)、三位數字、大小寫不敏感、無數字退化', col: C_PRIMARY },
        { cat: 'B. Address 計算與 CDB 組裝', count: '8 項', items: '0x0000/0x0080/0x0100/0x6F80/0xFFFF 邊界、224塊序列、保留非Address位元組、回傳新list', col: '8B5CF6' },
        { cat: 'C. CDB 模板載入防呆', count: '5 項', items: 'list/bytes/bytearray 格式支援、不足 16B 自動補零、超過 16B 安全截斷', col: C_WARNING },
        { cat: 'D. 分塊資料夾載入', count: '9 項', items: '28KB完整載入、自然排序保證、檔名對應、異常大小警告、空/不存在路徑、非.bin過濾', col: C_SUCCESS },
        { cat: 'E. Worker Thread 模擬傳輸', count: '6 項', items: 'Mock SPTD 完整傳輸、CHECK CONDITION 立即中斷、Abort 中止、逐塊回呼與CDB驗證', col: C_DANGER },
        { cat: 'F. GUI Tab 4 元件互動', count: '9 項', items: 'Tab4框架存在、16格Entry預設值/清空/讀取/非法Hex轉換、進度條與起始Address', col: '0284C7' },
        { cat: 'G. 狀態機邊界保護', count: '2 項', items: '未載入 chunks 啟動防呆報錯、初始狀態屬性驗證', col: '64748B' }
    ];

    testCategories.forEach((tc, idx) => {
        const yPos = 0.85 + idx * 0.6;
        slide.addShape(pptx.ShapeType.roundRect, {
            x: 0.8, y: yPos, w: 8.4, h: 0.52,
            fill: { color: C_CARD_BG },
            line: { color: C_CARD_BORDER, width: 1 },
            rectRadius: 0.08
        });
        slide.addText(tc.cat, {
            x: 1.0, y: yPos + 0.06, w: 2.6, h: 0.22,
            fontSize: 9.5, fontFace: 'Arial', bold: true, color: C_TEXT_DARK
        });
        slide.addText(tc.count, {
            x: 3.6, y: yPos + 0.06, w: 0.8, h: 0.22,
            fontSize: 9.5, fontFace: 'Arial', bold: true, color: tc.col, align: 'center'
        });
        slide.addText(tc.items, {
            x: 4.5, y: yPos + 0.06, w: 4.5, h: 0.4,
            fontSize: 8.5, fontFace: 'Arial', color: C_TEXT_MUTED
        });
    });
}

// ==========================================
// SLIDE 6: 異常攔截與防呆安全機制驗證
// ==========================================
{
    const slide = pptx.addSlide();
    slide.background = { color: C_BG_LIGHT };
    addHeader(slide, 'SAFETY & FAULT', '異常攔截與防呆安全機制驗證', 6);

    const safetyCards = [
        {
            title: '1. 檔案大小異常警告 (Size Mismatch)',
            tag: '防呆保護',
            tagCol: C_WARNING,
            detail: '當資料夾內混入非 128 Bytes 的分塊（如 64B 或 256B）時：\n• load_chunks() 會主動標註 ⚠️ 警告圖示與具體檔名\n• 介面標籤以紅色提示工程師確認\n• 避免因損毀檔案寫入錯誤長度導致 MCU 韌體損毀。',
            test: '已通過 test_abnormal_size_warning, test_oversized_chunk_warning'
        },
        {
            title: '2. Check Condition 立即中斷 (Error Halt)',
            tag: '故障保護',
            tagCol: C_DANGER,
            detail: '當 MCU 在第 N 塊回傳 0x02 (CHECK CONDITION) 或超時：\n• 傳輸迴圈立即 break 中斷，嚴格停止發送後續封包\n• 自動調用 parse_sense_data() 解析 Sense Key / ASC / ASCQ\n• 於 Terminal 顯示具體錯誤原因並彈窗警告。',
            test: '已通過 test_check_condition_stops_immediately'
        },
        {
            title: '3. 使用者手動中止 (User Abort)',
            tag: '操作保護',
            tagCol: C_PRIMARY,
            detail: '傳輸進行中點選 [⏹ 中止更新] 按鈕：\n• 透過 thread-safe threading.Event 觸發 _abort 旗標\n• 於當前 Chunk 完成後優雅退出迴圈\n• finally 區塊無條件執行 unlock_drive 與 close_drive 釋放鎖。',
            test: '已通過 test_abort_stops_transmission'
        }
    ];

    safetyCards.forEach((c, idx) => {
        const yPos = 0.85 + idx * 1.4;
        slide.addShape(pptx.ShapeType.roundRect, {
            x: 0.8, y: yPos, w: 8.4, h: 1.25,
            fill: { color: C_CARD_BG },
            line: { color: C_CARD_BORDER, width: 1 },
            rectRadius: 0.1
        });
        slide.addShape(pptx.ShapeType.roundRect, {
            x: 1.0, y: yPos + 0.12, w: 0.8, h: 0.24,
            fill: { color: c.tagCol },
            rectRadius: 0.05
        });
        slide.addText(c.tag, {
            x: 1.0, y: yPos + 0.12, w: 0.8, h: 0.24,
            fontSize: 8.5, fontFace: 'Arial', bold: true, color: 'FFFFFF', align: 'center', valign: 'middle'
        });
        slide.addText(c.title, {
            x: 1.9, y: yPos + 0.1, w: 5.0, h: 0.28,
            fontSize: 11, fontFace: 'Arial', bold: true, color: C_TEXT_DARK
        });
        slide.addText(c.detail, {
            x: 1.0, y: yPos + 0.42, w: 8.0, h: 0.55,
            fontSize: 8.5, fontFace: 'Arial', color: C_TEXT_MUTED, lineSpacing: 11
        });
        slide.addText('🧪 驗證單元測試: ' + c.test, {
            x: 1.0, y: yPos + 0.98, w: 8.0, h: 0.2,
            fontSize: 8, fontFace: 'Arial', bold: true, color: C_PRIMARY
        });
    });
}

// ==========================================
// SLIDE 7: 總結與交付物 (Conclusions & Deliverables)
// ==========================================
{
    const slide = pptx.addSlide();
    slide.background = { color: C_BG_DARK };

    slide.addShape(pptx.ShapeType.roundRect, {
        x: 0.8, y: 0.5, w: 2.0, h: 0.3,
        fill: { color: '1E3A8A' },
        line: { color: '3B82F6', width: 1 },
        rectRadius: 0.15
    });
    slide.addText('CONCLUSIONS', {
        x: 0.8, y: 0.5, w: 2.0, h: 0.3,
        fontSize: 10, fontFace: 'Arial', bold: true, color: '93C5FD', align: 'center', valign: 'middle'
    });

    slide.addText('專案總結與成果交付清單', {
        x: 2.9, y: 0.45, w: 6.0, h: 0.4,
        fontSize: 20, fontFace: 'Arial', bold: true, color: 'FFFFFF', valign: 'middle'
    });

    const deliverables = [
        {
            title: '1. 獨立模組化後端引擎',
            detail: 'src/firmware_updater.py 提供 FirmwareUpdateEngine 類別，支援自然排序載入、Address 動態組裝、Worker Thread 非同步傳輸與狀態確認。',
            status: '✅ 已整合完畢'
        },
        {
            title: '2. 專屬前端操作介面 (Tab 4)',
            detail: 'src/BusHound.py 新增「MCU FW Update」獨立分頁，包含資料夾統計、16格CDB模板、起始Address、進度條與黑底綠字Terminal Log。',
            status: '✅ 已完成發布'
        },
        {
            title: '3. 全面性單元測試套件',
            detail: 'tests/test_firmware.py 涵蓋 43 項測試，全專案累積 84/84 項測試全數通過（PASS 率 100%）。',
            status: '✅ 84/84 PASS'
        },
        {
            title: '4. 無黑視窗執行檔封裝',
            detail: '透過 PyInstaller 封裝為乾淨之 dist/BusHound.exe 並更新 BusHound.7z，支援 Windows 雙擊無 CMD 執行。',
            status: '✅ 7z 更新完畢'
        }
    ];

    deliverables.forEach((d, idx) => {
        const yPos = 1.05 + idx * 0.95;
        slide.addShape(pptx.ShapeType.roundRect, {
            x: 0.8, y: yPos, w: 8.4, h: 0.82,
            fill: { color: C_NAVY_CARD },
            line: { color: '334155', width: 1 },
            rectRadius: 0.1
        });
        slide.addText(d.title, {
            x: 1.0, y: yPos + 0.08, w: 5.5, h: 0.25,
            fontSize: 11, fontFace: 'Arial', bold: true, color: '38BDF8'
        });
        slide.addText(d.status, {
            x: 6.8, y: yPos + 0.08, w: 2.2, h: 0.25,
            fontSize: 10, fontFace: 'Arial', bold: true, color: C_SUCCESS, align: 'right'
        });
        slide.addText(d.detail, {
            x: 1.0, y: yPos + 0.35, w: 8.0, h: 0.4,
            fontSize: 8.5, fontFace: 'Arial', color: 'CBD5E1', lineSpacing: 11
        });
    });

    slide.addText('BusHound Storage Tool  |  Antigravity Quality Assurance Verified', {
        x: 0.8, y: 5.15, w: 8.4, h: 0.3,
        fontSize: 9, fontFace: 'Arial', color: '64748B'
    });
}

// 產出 PPTX 檔案
const outputPath = path.join(__dirname, 'BusHound_Firmware_Update_Test_Report.pptx');
const fallbackPath = path.join(__dirname, 'BusHound_Firmware_Update_Test_Report_v2.pptx');

pptx.writeFile({ fileName: outputPath })
    .then(() => {
        console.log(`測試報告 PPTX 成功產出至: ${outputPath}`);
    })
    .catch((err) => {
        console.warn(`寫入主要檔案失敗 (${err.message})，嘗試寫入備用檔案...`);
        pptx.writeFile({ fileName: fallbackPath })
            .then(() => {
                console.log(`測試報告 PPTX 備用檔案成功產出至: ${fallbackPath}`);
            })
            .catch((err2) => {
                console.error(`寫入備用檔案亦失敗: ${err2.message}`);
            });
    });
