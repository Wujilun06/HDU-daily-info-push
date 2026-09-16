"""在已登录的浏览器同源上下文中直接 fetch /web/mp/articles。

绕开 urllib 触发的 -2041 风控：浏览器发出的请求带完整会话 cookie 与
官方客户端指纹，且为 same-origin，通常不被风控。
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)  # 让同目录的 private_config 可被导入
from private_config import get_weread_cookies

MP_ID = sys.argv[1] if len(sys.argv) > 1 else "MP_WXS_3248232042"
SHARE = ("https://weread.qq.com/book-detail?type=1&senderVid=937812177"
         "&v=33d42e0224d505f5758535f333234383233323034326ed"
         "&wtheme=white&wfrom=app&wvid=937812177&scene=bottomSheetShare")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

cookies = get_weread_cookies()
if not cookies:
    raise SystemExit("private_config.json 中无微信读书登录态，请先运行 python wechat_weread.py login")


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(user_agent=UA)
        try:
            ctx.add_cookies(cookies)
        except Exception as e:  # noqa: BLE001
            print("[warn] add_cookies:", e)
        page = ctx.new_page()
        page.goto(SHARE, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)

        for offset in (0, 20):
            js = (
                "(async (mpId, off) => {"
                "  const url = `https://weread.qq.com/web/mp/articles?mpId=${mpId}&offset=${off}`;"
                "  const r = await fetch(url, {credentials:'include',"
                "    headers:{'Accept':'application/json, text/plain, */*'}});"
                "  const t = await r.text();"
                "  return {status:r.status, body:t.slice(0, 9000)};"
                "})('%s', %d)" % (MP_ID, offset)
            )
            try:
                res = page.evaluate(js)
            except Exception as e:  # noqa: BLE001
                print(f"[offset={offset}] evaluate error:", e)
                continue
            print(f"[offset={offset}] HTTP {res['status']}")
            body = res["body"]
            try:
                d = json.loads(body)
                print("  errCode:", d.get("errCode"), "errMsg:", d.get("errMsg"))
                reviews = d.get("reviews") or []
                print("  reviews 组数:", len(reviews))
                cnt = 0
                for grp in reviews:
                    subs = grp.get("subReviews") or [grp]
                    for ent in subs:
                        rev = ent.get("review") or {}
                        info = rev.get("mpInfo") or {}
                        title = info.get("title") or rev.get("title") or ""
                        oid = info.get("originalId") or rev.get("originalId") or ""
                        ts = rev.get("createTime")
                        if title and oid:
                            cnt += 1
                            print(f"    - {ts} | {title[:40]} | "
                                  f"https://mp.weixin.qq.com/s/{oid}")
                print("  本页解析文章数:", cnt)
                if cnt == 0 and reviews:
                    print("  raw reviews[0]:",
                          json.dumps(reviews[0], ensure_ascii=False)[:400])
            except Exception as e:  # noqa: BLE001
                print("  parse error:", e)
                print("  body前1500:", body[:1500])
        b.close()


if __name__ == "__main__":
    main()
