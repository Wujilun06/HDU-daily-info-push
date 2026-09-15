"""公众号抓取自动重试：等限频冷却后重跑 main.py，直到公众号抓回数据。"""
import subprocess
import time
import re
import os

BASE = r"E:/个人项目/每日信息整合推送/daily_digest"
VENV = os.path.join(BASE, "venv", "Scripts", "python.exe")
MAIN = os.path.join(BASE, "main.py")


def count_weread(log):
    return sum(int(m) for m in re.findall(r"\[weread\] .*?: (\d+) 条", log))


for attempt in range(1, 4):
    wait = 300 * attempt  # 5 / 10 / 15 分钟递增冷却
    print(f"[retry] 第{attempt}次尝试前等待冷却 {wait}s ...", flush=True)
    time.sleep(wait)
    log_path = os.path.join(BASE, f"run_retry{attempt}.txt")
    with open(log_path, "w", encoding="utf-8") as f:
        subprocess.run([VENV, MAIN, "--once"], stdout=f, stderr=subprocess.STDOUT)
    log = open(log_path, encoding="utf-8").read()
    total = count_weread(log)
    print(f"[retry] 第{attempt}次完成, 公众号共 {total} 条", flush=True)
    if total > 0:
        print("[retry] 成功, 停止重试", flush=True)
        break
    print("[retry] 仍限频, 继续重试", flush=True)
print("[retry] 结束", flush=True)
