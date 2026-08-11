/**
 * @file ene_smbus_isp.c
 * @brief ENE RGB MCU SMBus ISP 韌體燒錄實作 (支援 HAL 依賴注入)
 */

#include <stdio.h>
#include <string.h>
#include "ene_smbus_isp.h"

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

/* 儲存外部注入的 HAL 函式指標 */
static const ene_smbus_hal_t *s_hal = NULL;

ene_status_t ene_isp_init(const ene_smbus_hal_t *hal_impl) {
    if (hal_impl == NULL || hal_impl->write_byte == NULL || 
        hal_impl->read_byte == NULL || hal_impl->write_block == NULL) {
        return ENE_ERR_INVALID_PARAM;
    }
    s_hal = hal_impl;
    return ENE_SUCCESS;
}

static ene_status_t ene_isp_wait_ready(uint32_t timeout_ms) {
    uint8_t status = 0;
    uint32_t count = 0;

    if (!s_hal) return ENE_ERR_NO_HAL;

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

ene_status_t ene_isp_unlock(void) {
    int res = 0;
    if (!s_hal) return ENE_ERR_NO_HAL;
    
    res |= s_hal->write_byte(ENE_SMBUS_7BIT_ADDR, ENE_REG_UNLOCK_KEY, 0x55);
    res |= s_hal->write_byte(ENE_SMBUS_7BIT_ADDR, ENE_REG_UNLOCK_KEY, 0xAA);

    if (res != 0) return ENE_ERR_SMBUS_I2C;
    return ene_isp_wait_ready(20);
}

static ene_status_t ene_isp_set_address(uint32_t flash_addr) {
    int res = 0;
    res |= s_hal->write_byte(ENE_SMBUS_7BIT_ADDR, ENE_REG_ADDR_HIGH, (uint8_t)((flash_addr >> 16) & 0xFF));
    res |= s_hal->write_byte(ENE_SMBUS_7BIT_ADDR, ENE_REG_ADDR_MID,  (uint8_t)((flash_addr >> 8)  & 0xFF));
    res |= s_hal->write_byte(ENE_SMBUS_7BIT_ADDR, ENE_REG_ADDR_LOW,  (uint8_t)(flash_addr        & 0xFF));
    return (res == 0) ? ENE_SUCCESS : ENE_ERR_SMBUS_I2C;
}

ene_status_t ene_isp_erase_sector(uint32_t sector_addr) {
    ene_status_t status;
    if (!s_hal) return ENE_ERR_NO_HAL;
    if (sector_addr % ENE_FLASH_SECTOR_SIZE != 0) return ENE_ERR_INVALID_PARAM;

    status = ene_isp_set_address(sector_addr);
    if (status != ENE_SUCCESS) return status;

    if (s_hal->write_byte(ENE_SMBUS_7BIT_ADDR, ENE_REG_ISP_CMD, ENE_ISP_CMD_SECTOR_ERASE) != 0) {
        return ENE_ERR_SMBUS_I2C;
    }
    return ene_isp_wait_ready(50);
}

ene_status_t ene_isp_write_page(uint32_t page_addr, const uint8_t *data, uint8_t len) {
    ene_status_t status;
    if (!s_hal) return ENE_ERR_NO_HAL;
    if (data == NULL || len != ENE_FLASH_PAGE_SIZE) return ENE_ERR_INVALID_PARAM;
    if (page_addr % ENE_FLASH_PAGE_SIZE != 0) return ENE_ERR_INVALID_PARAM;

    status = ene_isp_set_address(page_addr);
    if (status != ENE_SUCCESS) return status;

    if (s_hal->write_block(ENE_SMBUS_7BIT_ADDR, ENE_REG_DATA_PORT, data, len) != 0) {
        return ENE_ERR_SMBUS_I2C;
    }

    if (s_hal->write_byte(ENE_SMBUS_7BIT_ADDR, ENE_REG_ISP_CMD, ENE_ISP_CMD_PAGE_PROGRAM) != 0) {
        return ENE_ERR_SMBUS_I2C;
    }
    return ene_isp_wait_ready(20);
}

ene_status_t ene_isp_reset_and_exit(void) {
    if (!s_hal) return ENE_ERR_NO_HAL;
    s_hal->write_byte(ENE_SMBUS_7BIT_ADDR, ENE_REG_ISP_CMD, ENE_ISP_CMD_RESET_MCU);
    return ENE_SUCCESS;
}

ene_status_t ene_firmware_update_process(const uint8_t *firmware_bin, uint32_t total_size) {
    ene_status_t status;
    uint32_t offset = 0;

    status = ene_isp_unlock();
    if (status != ENE_SUCCESS) return status;

    for (offset = 0; offset < total_size; offset += ENE_FLASH_SECTOR_SIZE) {
        status = ene_isp_erase_sector(offset);
        if (status != ENE_SUCCESS) return status;
    }

    for (offset = 0; offset < total_size; offset += ENE_FLASH_PAGE_SIZE) {
        status = ene_isp_write_page(offset, &firmware_bin[offset], ENE_FLASH_PAGE_SIZE);
        if (status != ENE_SUCCESS) {
            ene_isp_reset_and_exit();
            return status;
        }
    }

    ene_isp_reset_and_exit();
    return ENE_SUCCESS;
}
