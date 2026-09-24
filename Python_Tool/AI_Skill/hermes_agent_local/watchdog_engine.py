#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hermes Local Watchdog Runner (HMC Resilience Engine)
用途：守護地端多模型批次任務或大型 Code Review，防止 vLLM 推論卡死或逾時。
"""

import asyncio
import os
import sys
import time
from pathlib import Path


class ResilientWatchdogRunner:
    def __init__(self, role: str, workspace: Path, timeout: int = 180, max_retries: int = 3):
        self.role = role
        self.workspace = workspace
        self.timeout = timeout
        self.max_retries = max_retries

    async def run(self, prompt: str) -> bool:
        for attempt in range(1, self.max_retries + 1):
            print(f"🛡️ [Watchdog] 啟動角色 [{self.role}] (嘗試 {attempt}/{self.max_retries})...")
            
            # 呼叫地端 hermes CLI 執行指定 prompt
            proc = await asyncio.create_subprocess_exec(
                "hermes",
                "--prompt", prompt,
                "--cwd", str(self.workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            last_hb = time.time()

            async def monitor_stream(stream):
                nonlocal last_hb
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode('utf-8', errors='ignore').strip()
                    if decoded:
                        print(f"[{self.role}] {decoded}")
                        last_hb = time.time()  # 只要有輸出就刷新心跳

            m_task = asyncio.create_task(monitor_stream(proc.stdout))

            while proc.returncode is None:
                await asyncio.sleep(2)
                if proc.returncode is not None:
                    break
                if time.time() - last_hb > self.timeout:
                    print(f"🚨 [Timeout] [{self.role}] 超過 {self.timeout}s 無回應，強制中斷重啟！")
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
                    break

            await m_task
            if proc.returncode == 0:
                print(f"✅ [Watchdog] [{self.role}] 任務成功完成。")
                return True

            print(f"⚠️ [Watchdog] [{self.role}] 執行失敗或被強制中斷，準備重試...")

        print(f"❌ [Watchdog] [{self.role}] 已達最大重試次數 ({self.max_retries})，放棄執行。")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python watchdog_engine.py \"<prompt>\" [role]")
        sys.exit(1)

    target_prompt = sys.argv[1]
    target_role = sys.argv[2] if len(sys.argv) > 2 else "senior_c_eng"
    cwd = Path.cwd()

    runner = ResilientWatchdogRunner(role=target_role, workspace=cwd, timeout=120)
    success = asyncio.run(runner.run(target_prompt))
    sys.exit(0 if success else 1)
