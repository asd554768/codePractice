"""批次執行引擎模組。"""
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, List

from core.commands import GetLogPageCommand
from core.nvme_driver import NvmeDriver
from runner.csv_parser import CsvTestCase
from runner.reporter import Reporter


class ErrorPolicy(Enum):
    CONTINUE = "continue"  # 遇錯繼續
    STOP = "stop"          # 遇錯停止


@dataclass
class SingleResult:
    """單筆指令執行結果。"""
    index: int              # 序號 (1-based)
    lid: int
    lid_name: str
    numd: int               # NUMD (0-based)
    length_bytes: int
    cdw10: int = 0          # NVMe SQE CDW10 暫存器內容
    status_code: int = -1   # NVMe Status Code (0=成功)
    latency_ms: float = 0.0 # 執行耗時 (毫秒)
    success: bool = False   # True=PASS, False=FAIL
    data: Optional[bytes] = None # 回傳資料 (失敗時可能為 None)
    error_message: str = "" # 錯誤訊息 (成功時為空)


@dataclass
class BatchConfig:
    """批次執行配置。"""
    device_number: int                         # PhysicalDrive 編號
    test_cases: List[CsvTestCase]              # 測試案例
    delay_ms: int = 0                          # 每筆之間的間隔 (毫秒)
    error_policy: ErrorPolicy = ErrorPolicy.CONTINUE
    output_dir: str = ""                       # 輸出目錄 (空則自動建立)


class BatchRunner:
    """批次執行引擎。
    
    支援在背景執行緒運行，提供回呼函式通知 GUI 更新。
    """
    
    def __init__(self, config: BatchConfig):
        self._config = config
        self._results: List[SingleResult] = []
        self._is_running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._reporter: Optional[Reporter] = None
        
        # 回呼函式 (GUI 用)
        self.on_progress: Optional[Callable[[int, int], None]] = None          # (current, total)
        self.on_result: Optional[Callable[[SingleResult], None]] = None        # 每筆完成時
        self.on_complete: Optional[Callable[[List[SingleResult]], None]] = None # 全部完成時
        self.on_error: Optional[Callable[[str], None]] = None                  # 錯誤通知
    
    def start(self):
        """在背景執行緒啟動批次執行。"""
        if self._is_running:
            return
        self._stop_event.clear()
        self._results.clear()
        self._is_running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
    
    def stop(self):
        """請求停止執行。"""
        self._stop_event.set()
    
    @property
    def is_running(self) -> bool:
        return self._is_running
    
    @property
    def results(self) -> List[SingleResult]:
        return self._results.copy()
    
    @property
    def output_dir(self) -> str:
        """回傳實際的輸出目錄路徑。"""
        if self._reporter:
            return self._reporter.output_dir
        return self._config.output_dir
    
    def _run(self):
        """實際的批次執行邏輯 (在背景執行緒中)。"""
        try:
            reporter = Reporter(base_dir=self._config.output_dir)
            self._reporter = reporter
            total_cases = len(self._config.test_cases)
            
            try:
                with NvmeDriver(self._config.device_number) as driver:
                    for idx, test_case in enumerate(self._config.test_cases):
                        if self._stop_event.is_set():
                            break
                            
                        cmd = test_case.to_command()
                        
                        start_time = time.perf_counter()
                        data = None
                        status_code = -1
                        error_msg = ""
                        success = False
                        
                        try:
                            data, status_code = driver.get_log_page(cmd)
                            success = (status_code == 0)
                            if not success:
                                error_msg = f"NVMe Error Status: 0x{status_code:X}"
                        except Exception as e:
                            error_msg = str(e)
                            
                        end_time = time.perf_counter()
                        latency_ms = (end_time - start_time) * 1000.0
                        
                        result = SingleResult(
                            index=test_case.index,
                            lid=test_case.lid,
                            lid_name=test_case.lid_name,
                            numd=test_case.numd,
                            length_bytes=test_case.length_bytes,
                            cdw10=cmd.cdw10,
                            status_code=status_code,
                            latency_ms=latency_ms,
                            success=success,
                            data=data,
                            error_message=error_msg
                        )
                        self._results.append(result)
                        
                        reporter.save_single_result(result)
                        
                        if self.on_result:
                            self.on_result(result)
                            
                        if self.on_progress:
                            self.on_progress(idx + 1, total_cases)
                            
                        if not success and self._config.error_policy == ErrorPolicy.STOP:
                            break
                            
                        if idx < total_cases - 1 and self._config.delay_ms > 0:
                            # 避免 time.sleep 卡住停止請求，使用 wait 搭配 timeout
                            if self._stop_event.wait(self._config.delay_ms / 1000.0):
                                break
            except Exception as e:
                if not self._results and self._config.test_cases:
                    tc0 = self._config.test_cases[0]
                    result = SingleResult(
                        index=1,
                        lid=tc0.lid,
                        lid_name=tc0.lid_name,
                        numd=tc0.numd,
                        length_bytes=tc0.length_bytes,
                        cdw10=tc0.to_command().cdw10,
                        status_code=-1,
                        latency_ms=0.0,
                        success=False,
                        data=None,
                        error_message=str(e)
                    )
                    self._results.append(result)
                if self.on_error:
                    self.on_error(str(e))
            finally:
                reporter.write_summary(self._results)
            
            if self.on_complete:
                self.on_complete(self._results)
                
        except Exception as e:
            if self.on_error:
                self.on_error(str(e))
        finally:
            self._is_running = False
