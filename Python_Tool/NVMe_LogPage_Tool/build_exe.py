"""PyInstaller 一鍵打包腳本。

使用方式: python build_exe.py
"""
import subprocess
import sys
import os

def build():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(script_dir, "main.py")
    
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--uac-admin",           # 請求管理員權限
        "--name", "NVMe_LogPage_Tool_v13",  # 改名為 v13
        "--add-data", "test_cases;test_cases",
        main_script
    ]
    
    print(f"正在打包: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=script_dir, check=True)
    print("\n打包完成！執行檔位於 dist/NVMe_LogPage_Tool.exe")

if __name__ == "__main__":
    build()
