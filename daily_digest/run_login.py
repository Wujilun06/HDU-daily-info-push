import os
import sys

BASE = r"E:\个人项目\每日信息整合推送\daily_digest"
os.chdir(BASE)
if BASE not in sys.path:
    sys.path.insert(0, BASE)

# 延长登录等待时间，给用户充足扫码窗口（默认 240s 太短）
os.environ["WEREAD_LOGIN_TIMEOUT"] = "1800"

import wechat_weread

if __name__ == "__main__":
    # 等同于 `python wechat_weread.py login`
    sys.argv = ["wechat_weread.py", "login"]
    wechat_weread.main()
