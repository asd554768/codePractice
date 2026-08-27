"""Windows UAC 管理員權限檢測與自動提權。"""
import ctypes
import sys
import os


def is_admin() -> bool:
    """檢查當前程序是否以管理員身分運行。"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def request_admin_elevation() -> bool:
    """若非管理員，觸發 UAC 提權對話框並重新啟動程式。
    
    Returns:
        True 表示已是管理員，False 表示已觸發提權（當前程序應退出）
    """
    if is_admin():
        return True
    
    # 使用 ShellExecuteW 以 "runas" 動詞重新啟動
    script = os.path.abspath(sys.argv[0])
    params = ' '.join(sys.argv[1:])
    
    # 判斷是 .exe 還是 .py
    if script.endswith('.exe'):
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", script, params, None, 1
        )
    else:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}" {params}', None, 1
        )
    
    return False
