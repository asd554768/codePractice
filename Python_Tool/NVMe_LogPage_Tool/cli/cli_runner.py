"""CLI 命令行解析與執行。"""
import argparse
import sys
import os

from core.device_scanner import scan_nvme_devices
from runner.csv_parser import parse_csv, CsvTestCase
from runner.batch_runner import BatchRunner, BatchConfig, ErrorPolicy
from core.parsers import format_hex_dump

def run_cli():
    """CLI 主入口。"""
    parser = argparse.ArgumentParser(description="NVMe Get Log Page 工具 CLI")
    parser.add_argument("--scan", action="store_true", help="列出所有 NVMe 設備資訊")
    parser.add_argument("--device", type=int, help="設備號碼 (例如 1 表示 PhysicalDrive1)")
    parser.add_argument("--csv", type=str, help="CSV 腳本檔案路徑")
    parser.add_argument("--output", type=str, default="./results", help="輸出目錄 (預設 ./results)")
    parser.add_argument("--delay", type=int, default=0, help="測試間隔毫秒 (預設 0)")
    parser.add_argument("--error-policy", choices=["continue", "stop"], default="continue", help="錯誤策略 (預設 continue)")
    
    parser.add_argument("--lid", type=str, help="單次下發 Log ID (Hex 字串，例如 0x02)")
    parser.add_argument("--numd", type=str, help="單次下發 NUMD (Hex 或 Dec，例如 0x7F, 7F, 0)")
    parser.add_argument("--length", type=int, help="單次下發 長度(Bytes)")
    
    args = parser.parse_args()

    if args.scan:
        try:
            devices = scan_nvme_devices()
            if not devices:
                print("未找到任何 NVMe 設備。")
                return
            for d in devices:
                print(f"PhysicalDrive{d.drive_number} - {d.model} (SN: {d.serial}, FW: {d.firmware_rev}, {d.size_gb}GB)")
        except Exception as e:
            print(f"掃描設備失敗: {e}")
        return

    if args.device is None:
        print("錯誤: 必須指定 --device 參數。使用 --scan 查看設備。")
        sys.exit(1)

    if args.csv:
        # CSV 批次模式
        try:
            cases = parse_csv(args.csv)
        except Exception as e:
            print(f"解析 CSV 失敗: {e}")
            sys.exit(1)
            
        policy = ErrorPolicy.CONTINUE if args.error_policy == "continue" else ErrorPolicy.STOP
        config = BatchConfig(
            device_number=args.device,
            test_cases=cases,
            delay_ms=args.delay,
            error_policy=policy,
            output_dir=args.output
        )
        runner = BatchRunner(config)
        
        def on_res(res):
            status = "PASS" if res.success else "FAIL"
            print(f"[{status}] #{res.index} LID=0x{res.lid:02X} NUMD=0x{res.numd:02X} CDW10=0x{res.cdw10:08X} ({res.length_bytes}B) | Latency={res.latency_ms:.2f}ms")
            if not res.success and res.error_message:
                print(f"  Error: {res.error_message}")
        
        runner.on_result = on_res
        
        print(f"開始執行 CSV 批次測試，共 {len(cases)} 筆...")
        runner.start()
        # CLI 模式需同步等待完成
        runner._thread.join()
        print(f"執行完畢。結果已輸出至 {args.output}")
        
    elif args.lid and (args.numd or args.length):
        # 單次下發模式
        lid_val = int(args.lid, 16) if args.lid.startswith("0x") else int(args.lid)
        
        if args.numd:
            numd_val = int(args.numd, 16) if (args.numd.startswith("0x") or any(c in "abcdefABCDEF" for c in args.numd)) else int(args.numd)
            length_val = (numd_val + 1) * 4
        else:
            length_val = args.length
            numd_val = (length_val // 4) - 1
            
        case = CsvTestCase(
            index=1,
            lid=lid_val,
            numd=numd_val,
            length_bytes=length_val,
            lid_name="ManualTest"
        )
        
        config = BatchConfig(
            device_number=args.device,
            test_cases=[case],
            delay_ms=0,
            error_policy=ErrorPolicy.CONTINUE,
            output_dir=args.output
        )
        runner = BatchRunner(config)
        
        print(f"執行單次 Log Page: LID={args.lid}, NUMD=0x{numd_val:02X} ({length_val}B)")
        runner.start()
        runner._thread.join()
        
        results = runner.results
        if results:
            res = results[0]
            if res.success and res.data:
                print("--- 取得資料成功 ---")
                print(format_hex_dump(res.data))
            else:
                print(f"--- 取得資料失敗: {res.error_message} ---")
    else:
        print("錯誤: 必須提供 --csv 或 (--lid 和 --length) 參數進行測試。")
        parser.print_help()
        sys.exit(1)
