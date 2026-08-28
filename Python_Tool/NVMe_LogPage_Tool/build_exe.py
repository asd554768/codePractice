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
        "--name", "NVMe_LogPage_Tool_v17",  # 版本 v17 (含 Ring0 直通與 CDW10 全面支援)
        "--add-data", "test_cases;test_cases",
        "--add-data", "WinRing0x64.sys;.",
        main_script
    ]
    
    print(f"正在打包: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=script_dir, check=True)
    
    exe_name = "NVMe_LogPage_Tool_v17.exe"
    exe_path = os.path.join(script_dir, "dist", exe_name)
    zip_path = os.path.join(script_dir, "dist", "NVMe_LogPage_Tool_v17.zip")
    
    # 壓縮為 zip (包含 .exe, WinRing0x64.sys 與範例 test_cases)
    import zipfile
    print(f"\n正在壓縮成 {zip_path} ...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(exe_path):
            zf.write(exe_path, arcname=exe_name)
        sys_driver = os.path.join(script_dir, "WinRing0x64.sys")
        if os.path.exists(sys_driver):
            zf.write(sys_driver, arcname="WinRing0x64.sys")
        sample_csv = os.path.join(script_dir, "test_cases", "sample_test.csv")
        if os.path.exists(sample_csv):
            zf.write(sample_csv, arcname=os.path.join("test_cases", "sample_test.csv"))
            
    print(f"打包與壓縮完成！\n執行檔：{exe_path}\n壓縮檔：{zip_path}")

if __name__ == "__main__":
    build()
