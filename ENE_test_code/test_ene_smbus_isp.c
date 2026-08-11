/**
 * @file test_ene_smbus_isp.c
 * @brief ENE SMBus ISP 單元測試 (基於 Dependency Injection)
 */

#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <string.h>
#include "ene_smbus_isp.h"

/* =========================================================================
 * 1. 模擬環境的內部狀態 (Mock State)
 * ========================================================================= */
static uint8_t mock_flash[4096];
static uint8_t mock_page_buffer[32];
static uint32_t mock_addr_ptr = 0;
static uint8_t mock_isp_status = 0;
static bool is_unlocked = false;

/* =========================================================================
 * 2. 實作 HAL 介面的 Mock 函式 (Mock Functions)
 * ========================================================================= */
static int mock_smbus_write_byte(uint8_t slave_addr, uint8_t reg, uint8_t data) {
    if (slave_addr != 0x38) return -1;

    switch (reg) {
        case 0x7F: // Unlock 密碼
            if (data == 0xAA) is_unlocked = true; 
            break;
        case 0x80: mock_addr_ptr = (mock_addr_ptr & 0x00FFFF) | (data << 16); break;
        case 0x81: mock_addr_ptr = (mock_addr_ptr & 0xFF00FF) | (data << 8);  break;
        case 0x82: mock_addr_ptr = (mock_addr_ptr & 0xFFFF00) | data;         break;
        case 0x85: // ISP CMD 觸發
            if (!is_unlocked) return -1;
            if (data == 0x01) { // Erase
                memset(&mock_flash[mock_addr_ptr], 0xFF, 512);
                mock_isp_status = 0x80; // 設為 BUSY
            } else if (data == 0x02) { // Page Program
                memcpy(&mock_flash[mock_addr_ptr], mock_page_buffer, 32);
                mock_isp_status = 0x80; // 設為 BUSY
            } else if (data == 0x80) { // Reset
                is_unlocked = false;
            }
            break;
    }
    return 0; // Success
}

static int mock_smbus_read_byte(uint8_t slave_addr, uint8_t reg, uint8_t *val) {
    if (slave_addr != 0x38) return -1;
    if (reg == 0x85) {
        *val = mock_isp_status;
        mock_isp_status = 0; // 模擬：讀取一次後假裝硬體已完成，BUSY 清零
    }
    return 0;
}

static int mock_smbus_write_block(uint8_t slave_addr, uint8_t reg, const uint8_t *buf, uint8_t len) {
    if (slave_addr != 0x38) return -1;
    if (reg == 0x84 && len == 32) {
        memcpy(mock_page_buffer, buf, 32); // 寫入 SRAM 緩衝區
    }
    return 0;
}

static void mock_delay_ms(uint32_t ms) {
    // 測試環境不需真正延遲，直接 return
}

/* =========================================================================
 * 3. 定義並實例化 HAL 結構體 (Dependency Injection Struct)
 * ========================================================================= */
static const ene_smbus_hal_t test_hal = {
    .write_byte  = mock_smbus_write_byte,
    .read_byte   = mock_smbus_read_byte,
    .write_block = mock_smbus_write_block,
    .delay_ms    = mock_delay_ms
};

/* =========================================================================
 * 4. 測試案例 (Test Cases)
 * ========================================================================= */

void test_initialization() {
    // 測試未注入 HAL 時應該報錯
    assert(ene_isp_init(NULL) == ENE_ERR_INVALID_PARAM);
    
    // 注入 Mock HAL 應該成功
    assert(ene_isp_init(&test_hal) == ENE_SUCCESS);
    printf("[PASS] Initialization Test\n");
}

void test_unlock_sequence() {
    is_unlocked = false;
    assert(ene_isp_unlock() == ENE_SUCCESS);
    assert(is_unlocked == true);
    printf("[PASS] Unlock Sequence Test\n");
}

void test_page_write() {
    uint8_t test_data[32];
    memset(test_data, 0x5A, 32); // 準備測試圖樣 0x5A
    
    // 對 0x0100 位址寫入 32 Bytes
    assert(ene_isp_write_page(0x0100, test_data, 32) == ENE_SUCCESS);
    
    // 斷言模擬的 Flash 內部確實被改寫了
    assert(mock_flash[0x0100] == 0x5A);
    assert(mock_flash[0x011F] == 0x5A);
    printf("[PASS] Page Write Execution Test\n");
}

void test_alignment_guard() {
    uint8_t test_data[32] = {0};
    
    // 測試未對齊的 Address (0x0105 不被 32 整除)，應該被擋下
    assert(ene_isp_write_page(0x0105, test_data, 32) == ENE_ERR_INVALID_PARAM);
    printf("[PASS] Alignment Guard Test\n");
}

int main() {
    printf("--- 開始 ENE SMBus ISP 單元測試 ---\n");
    test_initialization();
    test_unlock_sequence();
    test_page_write();
    test_alignment_guard();
    printf("--- 所有測試皆順利通過！ ---\n");
    return 0;
}
