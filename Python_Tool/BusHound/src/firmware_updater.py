"""
firmware_updater.py — MCU 韌體更新引擎 (FirmwareUpdateEngine)
功能：
1. 載入指定資料夾中的 128-Byte 分塊韌體檔案，自然排序
2. 匯入 CDB 模板，動態更新 CDB[3] (MSB) 與 CDB[4] (LSB) 的 Address
3. 同步逐塊 Data-Out 傳輸，每塊確認 SCSI Status == 0x00 (GOOD) 才接續
4. 支援 Worker Thread 背景執行、中途 Abort、進度回呼
"""

import os
import re
import time
import threading

from backend_storage import (
    send_scsi_command, open_drive, close_drive,
    lock_drive, unlock_drive, parse_sense_data,
    SCSI_IOCTL_DATA_OUT, SCSI_STATUS_DICT,
)

CHUNK_SIZE = 128
ADDR_INCREMENT = 0x80


def natural_sort_key(s):
    """自然排序 key：將字串中的數字轉為整數比較，避免 chunk_10 排在 chunk_2 前面"""
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]


class FirmwareUpdateEngine:
    """MCU 韌體更新引擎"""

    def __init__(self):
        self.chunks = []           # list of bytes, 每個 128B
        self.file_names = []       # 對應的檔案名稱
        self.base_cdb = [0x00] * 16
        self.start_address = 0x0000

        self._abort = threading.Event()
        self._running = False
        self._thread = None

    # ------------------------------------------------------------------
    # 資料載入
    # ------------------------------------------------------------------
    def load_chunks(self, folder_path):
        """
        從指定資料夾載入所有 .bin 檔案，依自然排序。
        回傳 (成功: bool, 訊息: str)
        """
        if not os.path.isdir(folder_path):
            return False, f"資料夾不存在: {folder_path}"

        bin_files = [f for f in os.listdir(folder_path)
                     if f.lower().endswith('.bin')]
        if not bin_files:
            return False, "資料夾中沒有 .bin 檔案"

        bin_files.sort(key=natural_sort_key)

        self.chunks = []
        self.file_names = []
        warnings = []

        for fname in bin_files:
            fpath = os.path.join(folder_path, fname)
            with open(fpath, 'rb') as f:
                data = f.read()
            if len(data) != CHUNK_SIZE:
                warnings.append(f"⚠️ {fname}: 大小 {len(data)}B ≠ {CHUNK_SIZE}B")
            self.chunks.append(data)
            self.file_names.append(fname)

        end_addr = self.start_address + len(self.chunks) * ADDR_INCREMENT
        msg = (f"已載入 {len(self.chunks)} 個檔案 "
               f"(總大小: {sum(len(c) for c in self.chunks):,} Bytes, "
               f"預計結束 Address: 0x{end_addr:04X})")
        if warnings:
            msg += "\n" + "\n".join(warnings)

        return True, msg

    def load_cdb_template(self, cdb_data):
        """
        載入 CDB 模板 (list[int] 或 bytes，長度 16)
        """
        if isinstance(cdb_data, (bytes, bytearray)):
            cdb_data = list(cdb_data)
        if len(cdb_data) < 16:
            cdb_data = cdb_data + [0x00] * (16 - len(cdb_data))
        self.base_cdb = list(cdb_data[:16])

    @staticmethod
    def build_cdb(base_cdb, address):
        """
        以 base_cdb 為模板，將 address 寫入 Byte 3 (MSB) 與 Byte 4 (LSB)。
        回傳新的 16-byte list。
        """
        cdb = list(base_cdb)
        cdb[3] = (address >> 8) & 0xFF   # High Byte
        cdb[4] = address & 0xFF          # Low Byte
        return cdb

    # ------------------------------------------------------------------
    # 傳輸執行
    # ------------------------------------------------------------------
    def start(self, drive_num, progress_cb=None, log_cb=None, done_cb=None):
        """
        在背景執行緒啟動韌體更新。
        progress_cb(current_idx, total, address) — 進度回呼
        log_cb(msg_str) — 日誌回呼
        done_cb(success: bool, msg: str) — 完成回呼
        """
        if self._running:
            return
        if not self.chunks:
            if log_cb:
                log_cb("❌ 尚未載入韌體分塊檔案")
            return

        self._abort.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._worker,
            args=(drive_num, progress_cb, log_cb, done_cb),
            daemon=True,
        )
        self._thread.start()

    def abort(self):
        """請求中止傳輸"""
        self._abort.set()

    @property
    def is_running(self):
        return self._running

    def _worker(self, drive_num, progress_cb, log_cb, done_cb):
        """背景工作執行緒主迴圈"""
        def log(msg):
            if log_cb:
                log_cb(msg)

        handle = None
        lock_ok = False
        success = False
        final_msg = ""

        try:
            # 1. 開啟磁碟
            log(f"[FW Update] 開啟 PhysicalDrive{drive_num}...")
            handle = open_drive(drive_num)

            # 2. 獲取獨佔鎖定
            lock_ok, err = lock_drive(handle)
            if lock_ok:
                log("[FW Update] 磁碟獨佔鎖定成功 (FSCTL_LOCK_VOLUME)")
            else:
                log(f"[FW Update] ⚠️ 獨佔鎖定失敗 (Error={err})，繼續執行...")

            total = len(self.chunks)
            t_start = time.perf_counter()

            # 3. 逐塊傳輸
            for idx, chunk_data in enumerate(self.chunks):
                if self._abort.is_set():
                    final_msg = f"⚠️ 使用者已手動中止更新 (已完成 {idx}/{total} 塊)"
                    log(f"[FW Update] {final_msg}")
                    break

                addr = self.start_address + idx * ADDR_INCREMENT
                cdb = self.build_cdb(self.base_cdb, addr)
                cdb_hex = ' '.join(f'{b:02X}' for b in cdb)

                drive_label = f"PhysicalDrive{drive_num}"
                scsi_st, _, sense = send_scsi_command(
                    handle, cdb, CHUNK_SIZE, SCSI_IOCTL_DATA_OUT,
                    chunk_data, drive_label=drive_label,
                )

                status_str = SCSI_STATUS_DICT.get(scsi_st, "UNKNOWN")
                log(f"  Chunk {idx + 1:>3}/{total} (0x{addr:04X}): "
                    f"CDB[3..4]={cdb[3]:02X} {cdb[4]:02X} -> "
                    f"Status: 0x{scsi_st:02X} ({status_str})")

                if scsi_st != 0x00:
                    sense_info = parse_sense_data(list(sense)) if sense else "(none)"
                    final_msg = (f"❌ 傳輸失敗於 Chunk #{idx + 1} "
                                 f"(Address 0x{addr:04X})\n"
                                 f"   SCSI Status: 0x{scsi_st:02X} ({status_str})\n"
                                 f"   Sense: {sense_info}")
                    log(f"[FW Update] {final_msg}")
                    break

                if progress_cb:
                    progress_cb(idx + 1, total, addr)
            else:
                # for-else: 正常完成
                elapsed = time.perf_counter() - t_start
                final_msg = (f"✅ 韌體更新完成！共 {total} 塊 / "
                             f"{sum(len(c) for c in self.chunks):,} Bytes / "
                             f"耗時 {elapsed:.2f} 秒")
                log(f"[FW Update] {final_msg}")
                success = True

        except Exception as e:
            final_msg = f"❌ 發生例外錯誤: {str(e)}"
            log(f"[FW Update] {final_msg}")

        finally:
            if handle is not None:
                if lock_ok:
                    unlock_drive(handle)
                    log("[FW Update] 磁碟鎖定已釋放")
                close_drive(handle)
                log("[FW Update] 磁碟已關閉")
            self._running = False
            if done_cb:
                done_cb(success, final_msg)
