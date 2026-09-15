"""进程内定时循环：到达配置的 run_times 时刻即运行一次。

适合不想配置系统计划任务的场景；缺点是终端/进程需一直开着。
如需更稳健，请用系统「任务计划程序 / cron」调用 run.bat / main.py --once。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main as M  # noqa: E402


def main():
    cfg = M.load_config(M.DEFAULT_CONFIG)
    run_times = cfg.get("settings", {}).get("run_times", ["08:00", "20:00"])
    print("定时聚合已启动，将在以下时刻运行：", run_times)
    last_run = ""
    while True:
        now = time.localtime()
        current = f"{now.tm_hour:02d}:{now.tm_min:02d}"
        if current in run_times and current != last_run and now.tm_sec < 3:
            last_run = current
            print(f"\n=== 触发运行 {current} ===")
            try:
                M.run(cfg, demo=False)
            except Exception as e:  # noqa: BLE001
                print(f"[error] run failed: {e}")
        time.sleep(20)


if __name__ == "__main__":
    main()
