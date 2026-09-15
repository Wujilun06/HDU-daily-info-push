"""用真实 Chromium 带登录态渲染公众号书页，并拦截其接口返回。

目的：绕过 urllib 调 /web/mp/articles 触发的 -2041 风控——真实浏览器
发出的请求头/指纹与官方客户端一致，通常不被风控。
"""
import json
import os
import sys

import re

from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIE_FILE = os.path.join(BASE, "wechat_weread_cookies.json")
MP_ID = sys.argv[1] if len(sys.argv) > 1 else "MP_WXS_3248232042"
# 若传入的是完整分享链接，直接用；否则拼成 web/book 路径
if MP_ID.startswith("http"):
    TARGET_URL = MP_ID
else:
    TARGET_URL = f"https://weread.qq.com/web/book/{MP_ID}"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

with open(COOKIE_FILE, encoding="utf-8") as f:
    cookies = json.load(f).get("cookies", [])


def main():
    captured = []

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(user_agent=UA)
        try:
            ctx.add_cookies(cookies)
        except Exception as e:  # noqa: BLE001
            print("[warn] add_cookies:", e)

        page = ctx.new_page()

        def on_response(resp):
            u = resp.url
            if "weread.qq.com" in u:
                try:
                    body = resp.text()
                except Exception:  # noqa: BLE001
                    body = ""
                captured.append((u, resp.status, body[:6000]))

        page.on("response", on_response)

        print("[*] 打开书页:", TARGET_URL)
        try:
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:  # noqa: BLE001
            print("[warn] goto:", e)
        page.wait_for_timeout(6000)

        # 滚动触发分页/懒加载
        for _ in range(5):
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(1500)

        # 从已渲染 DOM 抽取原文链接与标题
        html = page.content()
        dom_links = sorted(set(
            re.findall(r'https?://mp\.weixin\.qq\.com/s/[A-Za-z0-9_-]+', html)))
        titles = page.eval_on_selector_all(
            "a, [class*='title'], [class*='Title']",
            "els => els.map(e => (e.textContent||'').trim()).filter(t=>t.length>4)")
        print(f"[DOM] 含 mp.weixin 原文链接 {len(dom_links)} 条")
        for l in dom_links[:15]:
            print("    ", l)
        print(f"[DOM] 候选标题 {len(titles)} 个（前 20）")
        for t in titles[:20]:
            print("    -", t[:50])

        print(f"\n[API] 共捕获 {len(captured)} 个 weread 接口响应：")
        for i, (u, st, body) in enumerate(captured):
            print(f"  ({i}) {st}  {u[:120]}")
            if "MP_WXS" in body or "originalId" in body or "reviews" in body \
               or "mpInfo" in body:
                print("       -> 含文章/号特征，长度", len(body))
                for k in ("originalId", "reviewId", "mpInfo", "title",
                          "createTime", "bookId"):
                    idx = body.find(k)
                    if idx >= 0:
                        print("         ", body[idx:idx + 90].replace("\n", " "))
        b.close()


if __name__ == "__main__":
    main()
