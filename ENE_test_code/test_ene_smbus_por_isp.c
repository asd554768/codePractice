/**
 * @file test_ene_smbus_por_isp.c
 * @brief ENE SMBus POR (Mask ROM) ISP 單元測試
 */

#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <string.h>

/* 直接引入主程式原始碼以進行白箱測試 (White-box testing)，可以直接存取 static 變數 s_hal */
#include "ene_smbus_por_isp.c"

/* =========================================================================
 * 1. 模擬硬體環境狀態 (Mock State)
 * ========================================================================= */
static uint8_t mock_flash[4096];
static uint8_t mock_page_buffer[32];
static uint32_t mock_addr_ptr = 0;
static uint8_t mock_isp_status = 0;
static bool is_unlocked = false;

/* 模擬硬體 Reset 與時序狀態 */
static bool is_mcu_in_reset = false;
static uint32_t simulated_time_ms = 0;
static uint32_t por_release_time_ms = 0;

/* =========================================================================
 * 2. 實作 HAL 介面的 Mock 函式
 * ========================================================================= */
static void mock_set_mcu_reset_pin(bool assert_reset) {
    is_mcu_in_reset = assert_reset;
    if (assert_reset) {
        // MCU 被拉低 Reset，鎖死，重置解鎖狀態
        is_unlocked = false;
        printf("[Mock] MCU RST# asserted (GND).\n");
    } else {
        // MCU 放開 Reset，進入 POR 窗口，記錄放開時間
        por_release_time_ms = simulated_time_ms;
        printf("[Mock] MCU RST# de-asserted (3.3V). POR Window Opens!\n");
    }
}

static void mock_delay_ms(uint32_t ms) {
    simulated_time_ms += ms;
}

static int mock_smbus_write_byte(uint8_t slave_addr, uint8_t reg, uint8_t data) {
    if (slave_addr != 0x38) return -1;
    if (is_mcu_in_reset) return -1; // 處於硬體 Reset 期間，SMBus 無法通訊

    switch (reg) {
        case 0x7F: // Unlock 密碼
            if (data == 0xAA) {
                // 檢查是否在 POR 窗口內 (假設為 20ms)
                uint32_t elapsed = simulated_time_ms - por_release_time_ms;
                if (elapsed <= 20) {
                    is_unlocked = true;
                    printf("[Mock] 解鎖成功！時序落在 POR 窗口內 (延遲: %u ms)\n", elapsed);
                } else {
                    printf("[Mock] 解鎖失敗！超過 POR 窗口 (延遲: %u ms)\n", elapsed);
                }
            } 
            break;
        case 0x80: mock_addr_ptr = (mock_addr_ptr & 0x00FFFF) | (data << 16); break;
        case 0x81: mock_addr_ptr = (mock_addr_ptr & 0xFF00FF) | (data << 8);  break;
        case 0x82: mock_addr_ptr = (mock_addr_ptr & 0xFFFF00) | data;         break;
        case 0x85: // ISP CMD 觸發
            if (!is_unlocked) return -1;
            if (data == 0x01) { // Erase
                memset(&mock_flash[mock_addr_ptr], 0xFF, 512);
                mock_isp_status = 0x80; // BUSY
            } else if (data == 0x02) { // Page Program
                memcpy(&mock_flash[mock_addr_ptr], mock_page_buffer, 32);
                mock_isp_status = 0x80; // BUSY
            } else if (data == 0x80) { // Reset MCU
                is_unlocked = false;
                printf("[Mock] 收到重啟 MCU 指令。\n");
            }
            break;
    }
    return 0;
}

static int mock_smbus_read_byte(uint8_t slave_addr, uint8_t reg, uint8_t *val) {
    if (slave_addr != 0x38) return -1;
    if (reg == 0x85) {
        *val = mock_isp_status;
        mock_isp_status = 0; // 讀取一次後清零
    }
    return 0;
}

static int mock_smbus_write_block(uint8_t slave_addr, uint8_t reg, const uint8_t *buf, uint8_t len) {
    if (slave_addr != 0x38) return -1;
    if (reg == 0x84 && len == 32) {
        memcpy(mock_page_buffer, buf, 32);
    }
    return 0;
}

/* 注入的 HAL 結構體 */
static const ene_por_hal_t test_hal = {
    .write_byte        = mock_smbus_write_byte,
    .read_byte         = mock_smbus_read_byte,
    .write_block       = mock_smbus_write_block,
    .delay_ms          = mock_delay_ms,
    .set_mcu_reset_pin = mock_set_mcu_reset_pin
};

/* =========================================================================
 * 3. 測試案例 (Test Cases)
 * ========================================================================= */

void test_por_unlock_success() {
    printf("\n=== 測試案例: POR 窗口內及時解鎖 ===\n");
    s_hal = &test_hal; // 白箱測試，直接注入 HAL
    simulated_time_ms = 0;
    
    // 呼叫解鎖函式 (內部會呼叫 reset 拉低、拉高，並在 0ms 延遲下馬上送解鎖碼)
    assert(ene_por_isp_unlock() == ENE_SUCCESS);
    assert(is_unlocked == true);
    printf("[PASS] POR Unlock Success Test\n");
}

void test_por_unlock_timeout() {
    printf("\n=== 測試案例: POR 窗口超時 (模擬 OS 排程延遲) ===\n");
    s_hal = &test_hal;
    is_unlocked = false;
    
    // 手動重現超時情境
    mock_set_mcu_reset_pin(true);
    mock_delay_ms(10);
    mock_set_mcu_reset_pin(false);
    
    // 模擬 Windows OS 突然切換 Thread 導致延遲 30ms (超過 20ms 窗口)
    mock_delay_ms(30); 
    
    // 此時再送解鎖碼應該失效
    mock_smbus_write_byte(0x38, 0x7F, 0x55);
    mock_smbus_write_byte(0x38, 0x7F, 0xAA);
    
    assert(is_unlocked == false);
    printf("[PASS] POR Unlock Timeout Test\n");
}

void test_blank_chip_full_update() {
    printf("\n=== 測試案例: 空白晶片完整直刷流程 ===\n");
    uint8_t fw[4096];
    memset(fw, 0x99, sizeof(fw)); // 準備一份全是 0x99 的虛擬韌體
    
    // 清空模擬 Flash 狀態
    memset(mock_flash, 0xFF, sizeof(mock_flash)); 
    
    // 執行完整直刷流程 (含 POR 解鎖、抹除、分頁寫入)
    assert(ene_blank_chip_update_process(&test_hal, fw, sizeof(fw)) == ENE_SUCCESS);
    
    // 驗證模擬 Flash 是否確實被寫入 0x99
    assert(mock_flash[0] == 0x99);
    assert(mock_flash[4095] == 0x99);
    printf("[PASS] Blank Chip Full Update Test\n");
}

int main() {
    printf("--- 開始 ENE POR (Mask ROM) 燒錄架構單元測試 ---\n");
    test_por_unlock_success();
    test_por_unlock_timeout();
    test_blank_chip_full_update();
    printf("\n--- 所有測試皆順利通過！ ---\n");
    return 0;
}
