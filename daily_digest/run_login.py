import os
import sys
import traceback

BASE = r"E:\个人项目\每日信息整合推送\daily_digest"
os.chdir(BASE)
if BASE not in sys.path:
    sys.path.insert(0, BASE)

# 延长登录等待时间，给用户充足扫码窗口（默认 240s 太短）
os.environ["WEREAD_LOGIN_TIMEOUT"] = "1800"

LOG = os.path.join(BASE, "login_log.txt")
logf = open(LOG, "w", encoding="utf-8", buffering=1)
sys.stdout = logf
sys.stderr = logf


def run():
    try:
        import wechat_weread

        sys.argv = ["wechat_weread.py", "login"]
        wechat_weread.main()
    except Exception:
        traceback.print_exc(file=logf)
    finally:
        logf.flush()


if __name__ == "__main__":
    run()
