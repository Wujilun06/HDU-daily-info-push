#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""方案② 集成测试（合成数据，离线）。

验证 fetch_wechat_cookie 能：
  - 从 biz_url 正确解析 __biz
  - 读取 cookie、通过校验、调用抓取
  - 把 wechat_lite 的输出映射成与官网源同格式的 article dict
  - 与 main.py 的 naive 时间口径兼容
"""
import os
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import fetcher
import cookie_helper
import wechat_lite

# ---- mock 网络层 ----
FAKE_ARTICLES = [
    {"title": "测试推文A", "date": "2026-09-14", "datetime": datetime.now(),
     "url": "https://mp.weixin.qq.com/s/AAAA", "author": "x", "digest": "摘要A", "cover": ""},
    {"title": "测试推文B", "date": "2026-09-13", "datetime": datetime.now() - timedelta(days=1),
     "url": "https://mp.weixin.qq.com/s/BBBB", "author": "y", "digest": "摘要B", "cover": ""},
]


def test_biz_from_url():
    biz = wechat_lite.extract_biz_from_url(
        "https://mp.weixin.qq.com/s?__biz=MjM5MDQwNzcwMA==&mid=1&idx=1")
    assert biz == "MjM5MDQwNzcwMA==", biz
    print("[ok] extract_biz_from_url")


def test_fetch_wechat_cookie():
    # 覆盖网络相关函数
    cookie_helper.load_cookie = lambda cf: ("fake_cookie", "test")
    cookie_helper.validate_cookie = lambda c, b=None: (True, "ok")
    wechat_lite.fetch_account = lambda cookie, biz, max_messages=20, delay=1.0, cutoff_date=None: (
        list(FAKE_ARTICLES), "成功获取 2 篇")

    src = {
        "id": "wx_test", "name": "测试号", "site": "微信公众号",
        "type": "wechat_cookie",
        "biz_url": "https://mp.weixin.qq.com/s?__biz=MjM5MDQwNzcwMA==&mid=1&idx=1",
        "category": "公众号推文", "max_messages": 20,
    }
    out = fetcher.fetch_wechat_cookie(src)
    assert len(out) == 2, out
    a0 = out[0]
    for k in ("title", "link", "source", "site", "source_id", "published", "category"):
        assert k in a0, f"缺少字段 {k}"
    assert a0["source"] == "测试号"
    assert a0["site"] == "微信公众号"
    assert a0["category"] == "公众号推文"
    assert a0["link"] == "https://mp.weixin.qq.com/s/AAAA"
    assert isinstance(a0["published"], datetime)
    print(f"[ok] fetch_wechat_cookie 映射正确，产出 {len(out)} 篇")


def test_skip_without_biz():
    cookie_helper.load_cookie = lambda cf: ("fake_cookie", "test")
    cookie_helper.validate_cookie = lambda c, b=None: (True, "ok")
    wechat_lite.fetch_account = lambda *a, **k: ([], "无")
    # 既没有 biz 也没有 biz_url
    src = {"id": "wx_x", "name": "X", "type": "wechat_cookie",
           "biz_url": "", "category": "公众号推文"}
    out = fetcher.fetch_wechat_cookie(src)
    assert out == [], out
    print("[ok] 缺 biz/biz_url 时优雅跳过")


if __name__ == "__main__":
    test_biz_from_url()
    test_fetch_wechat_cookie()
    test_skip_without_biz()
    print("\n✅ 全部方案②集成测试通过")
