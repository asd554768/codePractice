/**
 * @file ene_smbus_por_isp.c
 * @brief ENE SMBus Hardware ISP (Mask ROM / No Flash Bootloader) 韌體燒錄流程
 * 
 * 此份程式碼專注於展示「沒有 Flash Bootloader」時，
 * 如何透過硬體 Reset (POR) 觸發 Mask ROM 窗口並搶在 Timeout 前解鎖硬體狀態機。
 */

#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>

/* 頁面與區塊大小定義 */
#define ENE_FLASH_PAGE_SIZE         32
#define ENE_FLASH_SECTOR_SIZE       512

/* ENE SMBus 暫存器定義 */
#define ENE_SMBUS_7BIT_ADDR         0x38
#define ENE_REG_UNLOCK_KEY          0x7F
#define ENE_REG_ADDR_HIGH           0x80
#define ENE_REG_ADDR_MID            0x81
#define ENE_REG_ADDR_LOW            0x82
#define ENE_REG_DATA_PORT           0x84
#define ENE_REG_ISP_CMD             0x85

#define ENE_ISP_CMD_SECTOR_ERASE    0x01
#define ENE_ISP_CMD_PAGE_PROGRAM    0x02
#define ENE_ISP_CMD_RESET_MCU       0x80

#define ENE_STATUS_BUSY_BIT         (1 << 7)
#define ENE_STATUS_ERROR_BIT        (1 << 6)

/* 狀態碼 */
typedef enum {
    ENE_SUCCESS             =  0,
    ENE_ERR_SMBUS_I2C       = -1,
    ENE_ERR_TIMEOUT         = -2,
    ENE_ERR_VERIFY_FAILED   = -3,
    ENE_ERR_POR_WINDOW_FAIL = -4
} ene_status_t;

/* =========================================================================
 * 硬體抽象層 (HAL) - 新增對 MCU 實體 Reset 腳位的控制
 * ========================================================================= */
typedef struct {
    int (*write_byte)(uint8_t slave_addr, uint8_t reg, uint8_t data);
    int (*read_byte)(uint8_t slave_addr, uint8_t reg, uint8_t *val);
    int (*write_block)(uint8_t slave_addr, uint8_t reg, const uint8_t *buf, uint8_t len);
    void (*delay_ms)(uint32_t ms);
    
    /* 針對 Mask ROM 模式必須的實體重置控制 (控制 MCU RST# 腳位) */
    void (*set_mcu_reset_pin)(bool assert_reset); 
} ene_por_hal_t;

static const ene_por_hal_t *s_hal = NULL;

/* =========================================================================
 * 輔助函式：輪詢硬體狀態機 BUSY 旗標
 * ========================================================================= */
static ene_status_t ene_isp_wait_ready(uint32_t timeout_ms) {
    uint8_t status = 0;
    uint32_t count = 0;

    while (count < timeout_ms) {
        if (s_hal->read_byte(ENE_SMBUS_7BIT_ADDR, ENE_REG_ISP_CMD, &status) != 0) {
            return ENE_ERR_SMBUS_I2C;
        }
        if ((status & ENE_STATUS_BUSY_BIT) == 0) {
            if (status & ENE_STATUS_ERROR_BIT) return ENE_ERR_VERIFY_FAILED;
            return ENE_SUCCESS;
        }
        if (s_hal->delay_ms) s_hal->delay_ms(1);
        count++;
    }
    return ENE_ERR_TIMEOUT;
}

/* =========================================================================
 * 核心：Mask ROM POR (Power-On Reset) 硬體解鎖流程
 * ========================================================================= */
ene_status_t ene_por_isp_unlock(void) {
    int res = 0;
    
    // 1. 強制硬體 Reset (拉低 RST# 腳位)
    // 效果：讓 8051 CPU 完全停止，準備重新啟動 Mask ROM
    s_hal->set_mcu_reset_pin(true);
    s_hal->delay_ms(10); // 等待電壓放電穩定
    
    // 2. 釋放 Reset (拉高 RST# 腳位，觸發 Power-On Reset)
    // 效果：Mask ROM 開始執行，開啟極短暫的 SMBus 偵聽窗口 (約 20~50ms)
    s_hal->set_mcu_reset_pin(false);
    
    // 3. 【關鍵時序】必須在 Mask ROM 窗口關閉前，以最快速度送出密碼！
    // 實務上在 Windows 下可能需要提高執行緒優先權 (SetThreadPriority) 以避免被 OS 搶佔
    res |= s_hal->write_byte(ENE_SMBUS_7BIT_ADDR, ENE_REG_UNLOCK_KEY, 0x55);
    res |= s_hal->write_byte(ENE_SMBUS_7BIT_ADDR, ENE_REG_UNLOCK_KEY, 0xAA);
    
    if (res != 0) {
        return ENE_ERR_POR_WINDOW_FAIL; // 未能及時在窗口內解鎖
    }
    
    // 等待硬體狀態機切換至 ISP 模式
    return ene_isp_wait_ready(20);
}

/* =========================================================================
 * 後續燒錄流程：由 Mask ROM / 硬體引擎直接接管 Flash (與一般 ISP 相同)
 * ========================================================================= */
static ene_status_t ene_isp_set_address(uint32_t flash_addr) {
    int res = 0;
    res |= s_hal->write_byte(ENE_SMBUS_7BIT_ADDR, ENE_REG_ADDR_HIGH, (uint8_t)((flash_addr >> 16) & 0xFF));
    res |= s_hal->write_byte(ENE_SMBUS_7BIT_ADDR, ENE_REG_ADDR_MID,  (uint8_t)((flash_addr >> 8)  & 0xFF));
    res |= s_hal->write_byte(ENE_SMBUS_7BIT_ADDR, ENE_REG_ADDR_LOW,  (uint8_t)(flash_addr        & 0xFF));
    return (res == 0) ? ENE_SUCCESS : ENE_ERR_SMBUS_I2C;
}

ene_status_t ene_por_erase_sector(uint32_t sector_addr) {
    if (ene_isp_set_address(sector_addr) != ENE_SUCCESS) return ENE_ERR_SMBUS_I2C;
    if (s_hal->write_byte(ENE_SMBUS_7BIT_ADDR, ENE_REG_ISP_CMD, ENE_ISP_CMD_SECTOR_ERASE) != 0) {
        return ENE_ERR_SMBUS_I2C;
    }
    return ene_isp_wait_ready(50);
}

ene_status_t ene_por_write_page(uint32_t page_addr, const uint8_t *data) {
    if (ene_isp_set_address(page_addr) != ENE_SUCCESS) return ENE_ERR_SMBUS_I2C;
    if (s_hal->write_block(ENE_SMBUS_7BIT_ADDR, ENE_REG_DATA_PORT, data, ENE_FLASH_PAGE_SIZE) != 0) {
        return ENE_ERR_SMBUS_I2C;
    }
    if (s_hal->write_byte(ENE_SMBUS_7BIT_ADDR, ENE_REG_ISP_CMD, ENE_ISP_CMD_PAGE_PROGRAM) != 0) {
        return ENE_ERR_SMBUS_I2C;
    }
    return ene_isp_wait_ready(20);
}

/* =========================================================================
 * 完整韌體直刷流程 (不依賴 Flash 上的任何 Bootloader)
 * ========================================================================= */
ene_status_t ene_blank_chip_update_process(const ene_por_hal_t *hal, const uint8_t *firmware_bin, uint32_t total_size) {
    s_hal = hal;
    ene_status_t status;
    uint32_t offset = 0;

    // 1. 抓準時機，硬體 Reset 配合 Mask ROM 密碼解鎖
    status = ene_por_isp_unlock();
    if (status != ENE_SUCCESS) {
        printf("ERROR: 未能抓到 POR 窗口，或 SMBus 鎖死。\n");
        return status;
    }

    // 2. Erase All (由 Mask ROM 驅動 Hardware Flash Controller)
    for (offset = 0; offset < total_size; offset += ENE_FLASH_SECTOR_SIZE) {
        status = ene_por_erase_sector(offset);
        if (status != ENE_SUCCESS) return status;
    }

    // 3. Program All
    for (offset = 0; offset < total_size; offset += ENE_FLASH_PAGE_SIZE) {
        status = ene_por_write_page(offset, &firmware_bin[offset]);
        if (status != ENE_SUCCESS) return status;
    }

    // 4. Reset MCU 讓剛刷入的全新 App 啟動
    s_hal->write_byte(ENE_SMBUS_7BIT_ADDR, ENE_REG_ISP_CMD, ENE_ISP_CMD_RESET_MCU);
    return ENE_SUCCESS;
}
