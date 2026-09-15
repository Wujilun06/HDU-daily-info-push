# -*- coding: utf-8 -*-
"""探针：验证 mp/profile_ext 历史消息页是否可无登录获取数据。
不改动任何生产文件，仅输出诊断结论。
"""
import re
import sys

from playwright.sync_api import sync_playwright

ARTICLE = "https://mp.weixin.qq.com/s/n6IPdA0cF9YsA34BReEZEw"
WX_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
         "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
         "MicroMessenger/8.0.30(0x18001e2f) NetType/WIFI Language/zh_CN")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ---------- 阶段 1：文章页取 __biz ----------
        ctx = browser.new_context(user_agent=WX_UA)
        page = ctx.new_page()
        print("== 阶段1: 打开文章页 ==")
        try:
            page.goto(ARTICLE, wait_until="domcontentloaded", timeout=45000)
            html = page.content()
            print("  标题:", (page.title() or "")[:60])
            biz = ""
            for pat in (r'var\s+biz\s*=\s*"([^"]+)"',
                        r'__biz=([A-Za-z0-9+/=]+)',
                        r'"biz"\s*:\s*"([^"]+)"'):
                m = re.search(pat, html)
                if m:
                    biz = m.group(1)
                    print(f"  __biz 命中({pat}): {biz}")
                    break
            if not biz:
                print("  ❌ 未提取到 __biz；页面片段:", html[:300].replace("\n", " "))
            # 取作者/公众号名
            m = re.search(r'var\s+nickname\s*=\s*"([^"]*)"', html)
            if m:
                print("  公众号昵称:", m.group(1))
        except Exception as e:  # noqa: BLE001
            print("  ❌ 文章页打开失败:", e)
            biz = ""
        ctx.close()

        if not biz:
            browser.close()
            return

        # ---------- 阶段 2：profile_ext 历史消息页（无 cookie） ----------
        for label, ua in (("微信UA", WX_UA),
                          ("桌面UA", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                                     "Chrome/120.0.0.0 Safari/537.36")):
            ctx = browser.new_context(user_agent=ua)
            page = ctx.new_page()
            url = (f"https://mp.weixin.qq.com/mp/profile_ext?action=home"
                   f"&__biz={biz}&scene=124")
            print(f"== 阶段2[{label}]: {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3000)
                html = page.content()
                print("  标题:", (page.title() or "")[:60])
                print("  含'请在微信客户端打开':", "请在微信客户端打开" in html)
                print("  含'环境异常':", "环境异常" in html)
                print("  含'验证':", "验证" in html)
                print("  msgList 长度:", len(re.findall(r"var\s+msgList\s*=\s*'", html)))
                tok = re.search(r"appmsg_token\s*=\s*[\"']([^\"']+)[\"']", html)
                print("  appmsg_token:", (tok.group(1) if tok else "未找到"))
                n = len(re.findall(r'data-link="([^"]+)"', html))
                print("  文章链接数:", n)
                body = re.sub(r"<[^>]+>", " ", html)
                body = re.sub(r"\s+", " ", body).strip()
                print("  正文片段:", body[:260])
            except Exception as e:  # noqa: BLE001
                print("  ❌ 打开失败:", e)
            ctx.close()

        browser.close()


if __name__ == "__main__":
    sys.exit(main())
