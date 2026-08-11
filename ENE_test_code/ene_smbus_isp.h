/**
 * @file ene_smbus_isp.h
 * @brief ENE RGB MCU SMBus ISP API 與 HAL 介面定義
 */
#ifndef ENE_SMBUS_ISP_H
#define ENE_SMBUS_ISP_H

#include <stdint.h>
#include <stdbool.h>

/* 頁面與區塊大小定義 */
#define ENE_FLASH_PAGE_SIZE         32
#define ENE_FLASH_SECTOR_SIZE       512

/* 錯誤碼定義 */
typedef enum {
    ENE_SUCCESS             =  0,
    ENE_ERR_INVALID_PARAM   = -1,
    ENE_ERR_SMBUS_I2C       = -2,
    ENE_ERR_TIMEOUT         = -3,
    ENE_ERR_VERIFY_FAILED   = -4,
    ENE_ERR_LOCKED          = -5,
    ENE_ERR_NO_HAL          = -6
} ene_status_t;

/* =========================================================================
 * 硬體抽象層 (HAL) 介面定義 (Dependency Injection)
 * ========================================================================= */
typedef struct {
    int (*write_byte)(uint8_t slave_addr, uint8_t reg, uint8_t data);
    int (*read_byte)(uint8_t slave_addr, uint8_t reg, uint8_t *val);
    int (*write_block)(uint8_t slave_addr, uint8_t reg, const uint8_t *buf, uint8_t len);
    void (*delay_ms)(uint32_t ms);
} ene_smbus_hal_t;

/* =========================================================================
 * API 宣告
 * ========================================================================= */
/**
 * @brief 註冊底層 HAL 介面
 */
ene_status_t ene_isp_init(const ene_smbus_hal_t *hal_impl);

ene_status_t ene_isp_unlock(void);
ene_status_t ene_isp_erase_sector(uint32_t sector_addr);
ene_status_t ene_isp_write_page(uint32_t page_addr, const uint8_t *data, uint8_t len);
ene_status_t ene_isp_reset_and_exit(void);
ene_status_t ene_firmware_update_process(const uint8_t *firmware_bin, uint32_t total_size);

#endif // ENE_SMBUS_ISP_H
