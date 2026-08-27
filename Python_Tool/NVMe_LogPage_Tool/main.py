"""NVMe Get Log Page 批次工具 - 主入口。

雙模式啟動邏輯：
- 無 CLI 參數 -> 啟動 GUI 模式
- 有 CLI 參數 -> 啟動 CLI 模式
"""
import sys
import os

# 確保專案根目錄在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# 確保 windowed/noconsole 模式下 print 不會引發 NoneType 異常
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")


def main():
    # 1. 檢查管理員權限
    from gui.uac_helper import is_admin, request_admin_elevation
    if not is_admin():
        if not request_admin_elevation():
            sys.exit(0)
    
    # 2. 判斷模式
    if len(sys.argv) > 1:
        # CLI 模式
        from cli.cli_runner import run_cli
        run_cli()
    else:
        # GUI 模式
        from gui.app import NvmeLogPageApp
        app = NvmeLogPageApp()
        app.run()


if __name__ == "__main__":
    main()
