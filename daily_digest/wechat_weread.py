#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号抓取 · 微信读书通道（标题 + 原文链接 + 日期）
======================================================

为什么走这条路
--------------
抓公众号的常规做法（mp/profile_ext?action=getmsg）要求「微信客户端会话 cookie」
（wap_sid2/pass_ticket），只能靠手机抓包获得，且 1~4 小时就失效；
而登录「微信公众平台后台」又需要一个公众号账号。
微信读书把公众号当成一种「书」来承载（bookId 形如 MP_WXS_xxxx），
它的网页版只需要用**你现有的微信扫码一次**即可，无需公众号账号、无需抓包。

机制（接口契约来自 we-mp-rss 的 weread 通道实现，已实测端点存在）
------------------------------------------------------------------
  1) 搜索： GET https://weread.qq.com/web/search/global?keyword=<名称>
            → books[] 中 bookId 以 MP_WXS_ 开头的即公众号，取得 mpId
  2) 列表： GET https://weread.qq.com/web/mp/articles?mpId=<mpId>&offset=<n>
            → reviews[].subReviews[].review{
                  reviewId, createTime,
                  mpInfo{title, originalId}
              }
  3) 原文链接 = https://mp.weixin.qq.com/s/<originalId>   ← 是真·原文地址
  4) 兜底： GET https://weread.qq.com/api/mp/cover?mpId=<mpId>
            → 仅返回最新一篇（列表接口风控时用）

用法
----
  python wechat_weread.py login                 # 扫码登录（手机微信扫，存登录态）
  python wechat_weread.py status                # 查看登录态是否可用
  python wechat_weread.py resolve 杭电图书馆      # 搜出公众号的 mpId
  python wechat_weread.py list MP_WXS_xxxx 2    # 拉取最近文章（2 页）
  python wechat_weread.py selftest              # 离线自检（合成数据，不联网）

依赖：标准库 + （仅 login 需要）playwright
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(BASE_DIR, "wechat_weread_cookies.json")

SEARCH_URL = "https://weread.qq.com/web/search/global"
ARTICLES_URL = "https://weread.qq.com/web/mp/articles"
COVER_URL = "https://weread.qq.com/api/mp/cover"
ARTICLE_PREFIX = "https://mp.weixin.qq.com/s/"
ANCHOR_URL = "https://weread.qq.com/"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


# --------------------------------------------------------------------------
# 登录态读写
# --------------------------------------------------------------------------
def load_login(cookie_file=COOKIE_FILE):
    """读取登录态，返回 (cookie_str, vid, 描述)。"""
    if not os.path.exists(cookie_file):
        return "", "", f"文件不存在: {cookie_file}"
    try:
        with open(cookie_file, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return "", "", f"读取失败: {e}"
    raw = data.get("raw") or "; ".join(
        f"{c['name']}={c['value']}" for c in data.get("cookies", []))
    return raw, data.get("vid", ""), f"已保存于 {data.get('saved_at', '?')}"


def save_login(cookies, cookie_file=COOKIE_FILE):
    vid = ""
    for c in cookies:
        if c.get("name") in ("wr_vid", "vid"):
            vid = c.get("value", "")
    payload = {
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "vid": vid,
        "cookies": cookies,
        "raw": "; ".join(f"{c['name']}={c['value']}" for c in cookies),
    }
    with open(cookie_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return vid


def _open(url, cookie="", extra_headers=None):
    headers = {
        "User-Agent": UA,
        "Referer": "https://weread.qq.com/",
        "Accept": "application/json, text/plain, */*",
        # 微信读书网页端固定头，缺失容易被 -2041 风控
        "appversion": "2.8.1.306656",
        "osversion": "Windows 10 (22621)",
        "Origin": "https://weread.qq.com",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    if extra_headers:
        headers.update(extra_headers)
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


# --------------------------------------------------------------------------
# 解析（纯函数，便于离线测试）
# --------------------------------------------------------------------------
def _article(title, original_id, ts, cover="", review_id=""):
    return {
        "title": (title or "").strip(),
        "url": ARTICLE_PREFIX + str(original_id or "").strip(),
        "datetime": datetime.fromtimestamp(int(ts)) if ts else None,
        "date": (datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
                 if ts else ""),
        "cover": cover or "",
        "aid": review_id or "",
    }


def parse_mp_articles(payload):
    """把 /web/mp/articles 的返回解析为归一化文章列表（最新在前）。

    返回 (articles, note)；note 说明被跳过的原因（无文章时有用）。
    """
    reviews = (payload or {}).get("reviews") or []
    if not reviews:
        return [], "返回中没有 reviews（该号可能未被微信读书收录）"
    out = []
    for group in reviews:
        subs = group.get("subReviews")
        # 兼容两种结构：subReviews 分组 / review 直接挂在顶层
        entries = subs if isinstance(subs, list) and subs else [group]
        for ent in entries:
            rev = ent.get("review") or {}
            info = rev.get("mpInfo") or {}
            title = info.get("title") or rev.get("title") or ""
            oid = info.get("originalId") or rev.get("originalId") or ""
            if not title or not oid:
                continue
            out.append(_article(title, oid, rev.get("createTime"),
                                cover=rev.get("pic") or info.get("pic") or "",
                                review_id=rev.get("reviewId", "")))
    out.sort(key=lambda a: a["datetime"] or datetime.min, reverse=True)
    return out, (f"解析出 {len(out)} 篇" if out else "reviews 结构解析后为空")


def parse_search_mp(payload):
    """从搜索结果里挑出公众号（bookId 以 MP_WXS_ 开头）。"""
    hits = []
    for b in (payload or {}).get("books", []) or []:
        info = b.get("bookInfo") or {}
        bid = str(info.get("bookId", ""))
        if bid.startswith("MP_WXS_") or "WXS" in bid.upper():
            hits.append({
                "mp_id": bid,
                "name": info.get("title", ""),
                "author": info.get("author", ""),
                "intro": (info.get("intro") or "")[:80],
            })
    return hits


# --------------------------------------------------------------------------
# 联网抓取
# --------------------------------------------------------------------------
def resolve_mp(keyword, cookie="", count=20):
    """按名称搜索公众号，返回候选列表。"""
    url = (f"{SEARCH_URL}?keyword={urllib.parse.quote(keyword)}"
           f"&maxIdx=0&fragmentSize=120&count={count}")
    return parse_search_mp(_open(url, cookie))


def fetch_articles_playwright(mp_id, cookie_file=COOKIE_FILE, max_pages=3,
                              page_interval=1.0, cutoff_date=None):
    """浏览器同源 fetch 兜底：用真实 Chromium 带登录态请求 /web/mp/articles。

    urllib 请求易被 -2041 风控；浏览器发出的请求带完整会话与官方指纹，
    冷却后通常不被风控。仅在 urllib 取数失败(-2041)时调用。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return [], "未安装 Playwright（pip install playwright && playwright install chromium）"
    if not os.path.exists(cookie_file):
        return [], f"登录态文件不存在: {cookie_file}"
    with open(cookie_file, encoding="utf-8") as f:
        cookies = json.load(f).get("cookies", [])
    if not mp_id:
        return [], "缺少 mpId"
    articles = []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            ctx = b.new_context(user_agent=UA)
            ctx.add_cookies(cookies)
            page = ctx.new_page()
            try:
                page.goto(ANCHOR_URL, wait_until="domcontentloaded", timeout=45000)
            except Exception:  # noqa: BLE001
                pass
            page.wait_for_timeout(3000)
            for pg in range(max_pages):
                off = pg * 20
                js = (
                    "(async (mpId, offset) => {"
                    "  const url = `https://weread.qq.com/web/mp/articles?mpId=${mpId}&offset=${offset}`;"
                    "  const r = await fetch(url, {credentials:'include',"
                    "    headers:{'Accept':'application/json, text/plain, */*'}});"
                    "  const t = await r.text();"
                    "  return {status:r.status, body:t};"
                    "})('%s', %d)" % (mp_id, off)
                )
                try:
                    res = page.evaluate(js)
                except Exception as e:  # noqa: BLE001
                    b.close()
                    return articles, f"浏览器请求失败: {e}"
                try:
                    d = json.loads(res["body"])
                except Exception:  # noqa: BLE001
                    b.close()
                    return articles, "浏览器返回非 JSON"
                code = d.get("errCode")
                if code not in (0, None):
                    b.close()
                    hint = "触发风控，稍后再试" if code == -2041 else ""
                    return articles, f"浏览器接口错误 errCode={code} {hint}".strip()
                items, _ = parse_mp_articles(d)
                if not items:
                    break
                stop = False
                for a in items:
                    if cutoff_date and a["datetime"] and a["datetime"] < cutoff_date:
                        stop = True
                        break
                    articles.append(a)
                if stop or len(items) < 20:
                    break
                page.wait_for_timeout(int(page_interval * 1000))
            b.close()
    except Exception as e:  # noqa: BLE001
        return articles, f"Playwright 异常: {e}"
    seen, uniq = set(), []
    for a in articles:
        if a["url"] in seen:
            continue
        seen.add(a["url"])
        uniq.append(a)
    return uniq, f"获取 {len(uniq)} 篇（浏览器）"


def fetch_articles(mp_id, cookie="", max_pages=3, page_interval=1.0,
                   cutoff_date=None):
    """拉取某公众号文章。返回 (articles, status)。

    :param cutoff_date: datetime，早于该日期的文章不再继续翻页（每日增量用）
    优先用 urllib；若被 -2041 风控，自动改用浏览器同源 fetch 兜底。
    """
    if not mp_id:
        return [], "缺少 mpId"
    articles = []
    book_referer = f"https://weread.qq.com/web/book/{urllib.parse.quote(mp_id)}"
    for page in range(max_pages):
        offset = page * 20
        url = f"{ARTICLES_URL}?mpId={urllib.parse.quote(mp_id)}&offset={offset}"
        try:
            payload = _open(url, cookie, extra_headers={"Referer": book_referer})
        except urllib.error.HTTPError as e:
            return articles, f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            return articles, f"请求失败: {e}"
        code = payload.get("errCode")
        if code not in (0, None):
            hint = { -2010: "登录态无效（请重新 login）",
                     -2012: "登录超时（请重新 login）",
                     -2041: "触发风控，稍后再试" }.get(code, "")
            if code == -2041 and page < 1:
                # 风控冷却：退避后重试一次（仅限首页，避免无限刷）
                time.sleep(45)
                continue
            if code == -2041:
                # urllib 被风控 → 改用浏览器同源 fetch 兜底
                arts2, st2 = fetch_articles_playwright(
                    mp_id, COOKIE_FILE, max_pages, page_interval, cutoff_date)
                if arts2:
                    return arts2, st2
            return articles, f"接口错误 errCode={code} {payload.get('errMsg', '')} {hint}".strip()
        page_items, note = parse_mp_articles(payload)
        if not page_items:
            if page == 0:
                return [], note
            break
        stop = False
        for a in page_items:
            if cutoff_date and a["datetime"] and a["datetime"] < cutoff_date:
                stop = True
                break
            articles.append(a)
        if stop or len(page_items) < 20:
            break
        time.sleep(page_interval)
    # 去重（同一篇可能重复出现）
    seen, uniq = set(), []
    for a in articles:
        if a["url"] in seen:
            continue
        seen.add(a["url"])
        uniq.append(a)
    return uniq, f"获取 {len(uniq)} 篇"


def fetch_wechat_weread_batch(sources, cookie_file=COOKIE_FILE, max_pages=3,
                              account_interval=6.0, page_interval=1.0,
                              cutoff_date=None):
    """一次浏览器会话，批量抓取多个公众号（标题 + 原文链接 + 日期）。

    相比「逐个源 urllib / 逐个源重启浏览器」，批量模式只启动一次
    Playwright，并在账号之间留足间隔（account_interval），显著降低
    -2014（请求频率过高）限频概率；同时规避 urllib 通道对部分 mp_id
    误报 -2003（参数格式错误）的问题——浏览器同源请求带完整会话指纹，
    服务端能正确识别 mpId。

    :param sources: list[dict]，每项需含 mp_id / id / name / category
    :return: ( {source_id: [article, ...]}, 描述 )
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {}, ("未安装 Playwright（pip install playwright && "
                    "playwright install chromium）")
    if not os.path.exists(cookie_file):
        return {}, f"登录态文件不存在: {cookie_file}"
    with open(cookie_file, encoding="utf-8") as f:
        cookies = json.load(f).get("cookies", [])
    mp_list = [(s.get("mp_id", ""), s) for s in sources if s.get("mp_id")]
    if not mp_list:
        return {}, "没有有效的 mp_id"
    results = {}
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            ctx = b.new_context(user_agent=UA)
            ctx.add_cookies(cookies)
            page = ctx.new_page()
            try:
                page.goto(ANCHOR_URL, wait_until="domcontentloaded", timeout=45000)
            except Exception:  # noqa: BLE001
                pass
            page.wait_for_timeout(3000)
            for mp_id, s in mp_list:
                articles = []
                try:
                    for pg in range(max_pages):
                        off = pg * 20
                        js = (
                            "(async (mpId, offset) => {"
                            "  const url = `https://weread.qq.com/web/mp/articles?mpId=${mpId}&offset=${offset}`;"
                            "  const r = await fetch(url, {credentials:'include',"
                            "    headers:{'Accept':'application/json, text/plain, */*'}});"
                            "  const t = await r.text();"
                            "  return {status:r.status, body:t};"
                            "})('%s', %d)" % (mp_id, off)
                        )
                        try:
                            res = page.evaluate(js)
                        except Exception as e:  # noqa: BLE001
                            print(f'[weread] {s.get("name")} 请求失败: {e}'); results[s['id']] = []
                            break
                        try:
                            d = json.loads(res["body"])
                        except Exception:  # noqa: BLE001
                            print(f'[weread] {s.get("name")} 浏览器返回非 JSON'); results[s['id']] = []
                            break
                        code = d.get("errCode")
                        if code not in (0, None):
                            hint = "触发风控，稍后再试" if code == -2041 else ""
                            print(f'[weread] {s.get("name")} 接口错误 errCode={code} {hint}'.strip()); results[s['id']] = []
                            break
                        items, _ = parse_mp_articles(d)
                        if not items:
                            break
                        stop = False
                        for a in items:
                            if cutoff_date and a["datetime"] and a["datetime"] < cutoff_date:
                                stop = True
                                break
                            articles.append(a)
                        if stop or len(items) < 20:
                            break
                        page.wait_for_timeout(int(page_interval * 1000))
                    seen, uniq = set(), []
                    for a in articles:
                        if a["url"] in seen:
                            continue
                        seen.add(a["url"])
                        uniq.append(a)
                    results[s["id"]] = uniq
                except Exception as e:  # noqa: BLE001
                    print(f'[weread] {s.get("name")} 异常: {e}'); results[s['id']] = []
                page.wait_for_timeout(int(account_interval * 1000))
            b.close()
    except Exception as e:  # noqa: BLE001
        return results, f"Playwright 异常: {e}"
    return results, "ok"


# --------------------------------------------------------------------------
# 扫码登录（Playwright，仅此一步需要浏览器）
# --------------------------------------------------------------------------
# 微信读书登录态可能的 cookie 名（任一出现即视为已登录），避免只认 wr_vid 漏判
_LOGIN_COOKIES = ("wr_vid", "wr_pf", "wxuin", "pass_ticket", "wap_sid2", "vid")


def _is_logged_in(cookies):
    return any(c.get("name") in _LOGIN_COOKIES and c.get("value")
               for c in cookies)


def _click_login(page):
    """点开登录入口（首页只有「登录」按钮，点了才出二维码）。"""
    for sel in ('a:has-text("登录")', 'button:has-text("登录")',
                'text="登录"', '.login_btn', '#login_btn', '.login-entry'):
        try:
            el = page.locator(sel).first
            if el.count() and el.is_visible():
                el.click(timeout=5000)
                print(f"[*] 已点击登录入口（{sel}）")
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _capture_qr(page, qr_path):
    """把当前页面的二维码截到 qr_path，返回是否截到。"""
    shot_ok = False
    for sel in ("iframe", "img[src*='qrcode']", "img[src*='qrconnect']",
                ".qr_code", ".login_dialog img", "canvas", ".qr-img"):
        try:
            el = page.locator(sel).first
            if el.count() and el.is_visible():
                el.screenshot(path=qr_path)
                shot_ok = True
                break
        except Exception:  # noqa: BLE001
            continue
    if not shot_ok:
        page.screenshot(path=qr_path)
    return shot_ok


def _qr_expired(page):
    """检测微信读书二维码是否已失效（避免无脑重载打断正在进行的扫码）。

    失效时页面通常会出现「已失效 / 已过期 / 重新扫码」等文案，或原二维码元素消失。
    """
    try:
        txt = page.inner_text("body") or ""
    except Exception:  # noqa: BLE001
        return False
    for kw in ("已失效", "已过期", "失效", "过期", "重新扫码", "点击刷新",
               "刷新二维码", "二维码过期"):
        if kw in txt:
            return True
    # 二维码元素消失也视为失效
    try:
        qr = page.locator("iframe, img[src*='qrcode'], img[src*='qrconnect'], "
                          ".qr_code, canvas")
        if qr.count() == 0 or not qr.first.is_visible():
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def login_via_playwright(cookie_file=COOKIE_FILE, timeout=None, headed=False):
    """打开微信读书登录二维码 → 手机微信扫码 → 保存登录态。

    无需公众号账号：任何微信用户扫码即可（本方案相对其他路线的最大优势）。
    - 二维码过期（约 5 分钟）会自动刷新，文件 weread_login_qr.png 始终最新；
    - 登录态检测放宽到多个微信读书 cookie，避免「扫了却没识别到」。
    等待时长可用环境变量 WEREAD_LOGIN_TIMEOUT 覆盖（秒，默认 240）。
    """
    if timeout is None:
        try:
            timeout = int(os.environ.get("WEREAD_LOGIN_TIMEOUT", "240"))
        except ValueError:
            timeout = 240
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[X] 未安装 Playwright：pip install playwright && playwright install chromium")
        return False

    qr_path = os.path.join(BASE_DIR, "weread_login_qr.png")
    page_shot = os.path.join(BASE_DIR, "weread_login_page.png")
    print("[*] 正在打开微信读书登录页 ...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        ctx = browser.new_context(user_agent=UA)
        page = ctx.new_page()
        try:
            page.goto("https://weread.qq.com/", wait_until="domcontentloaded",
                      timeout=45000)
        except Exception as e:  # noqa: BLE001
            print("[X] 打开失败:", e)
            browser.close()
            return False
        page.wait_for_timeout(3500)

        if not _is_logged_in(ctx.cookies()):
            _click_login(page)
            page.wait_for_timeout(3000)

        page.screenshot(path=page_shot)        # 整页留档
        _capture_qr(page, qr_path)             # 截二维码
        qr_shown_at = time.time()

        print("=" * 62)
        print("请用手机微信『扫一扫』打开下面这张图片完成登录")
        print(f"（图片路径：{qr_path}，二维码约 5 分钟有效，过期会自动刷新）")
        print("=" * 62)

        deadline = time.time() + timeout
        logged = False
        refresh_count = 0
        while time.time() < deadline:
            if _is_logged_in(ctx.cookies()):
                logged = True
                break
            # 仅当二维码确实失效（约 5 分钟后，或页面出现失效文案）才刷新，
            # 且至少等满 60 秒，避免重载打断正在进行的扫码确认。
            if time.time() - qr_shown_at > 60 and _qr_expired(page):
                refresh_count += 1
                try:
                    page.reload(wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2500)
                    if not _is_logged_in(ctx.cookies()):
                        _click_login(page)
                        page.wait_for_timeout(2500)
                    _capture_qr(page, qr_path)
                    qr_shown_at = time.time()
                    print(f"[*] 检测到二维码失效，已刷新（第 {refresh_count} 次）→ {qr_path}")
                except Exception as e:  # noqa: BLE001
                    print("[!] 刷新二维码失败，沿用旧图：", e)
            page.wait_for_timeout(2000)

        cookies = ctx.cookies()
        browser.close()

        if not logged and _is_logged_in(cookies):
            logged = True
        if not logged:
            print("[X] 等待扫码超时（未检测到登录态），请重跑 login 再扫一次")
            return False
        vid = next((c["value"] for c in cookies
                    if c.get("name") in ("wr_vid", "vid") and c.get("value")), "")
        save_login(cookies, cookie_file)
        print(f"[OK] 登录成功！vid={vid[:12]}... 登录态已保存到 {cookie_file}")
        print("     提示：登录态通常可维持数周；失效时重跑 login 即可。")
        return True


def status():
    cookie, vid, desc = load_login()
    print("登录态:", desc)
    if not cookie:
        print("状态: [X] 未登录（先运行 login）")
        return 1
    try:
        hits = resolve_mp("微信读书", cookie)
        print(f"状态: [OK] 可用（搜索接口正常返回，命中 {len(hits)} 个公众号结果）")
        return 0
    except Exception as e:  # noqa: BLE001
        print("状态: [X] 请求异常，可能需重新登录:", e)
        return 1


# --------------------------------------------------------------------------
# 离线自检（合成数据，验证字段映射，不联网）
# --------------------------------------------------------------------------
def selftest():
    payload = {"reviews": [{"subReviews": [
        {"review": {"reviewId": "MP_WXS_1_a", "createTime": 1778580003,
                    "mpInfo": {"title": "第一篇", "originalId": "abc~def"},
                    "pic": "https://example.test/1.jpg"}},
        {"review": {"reviewId": "MP_WXS_1_b", "createTime": 1778580002,
                    "mpInfo": {"title": "第二篇", "originalId": "xyz_123"}}},
    ]}]}
    arts, note = parse_mp_articles(payload)
    assert len(arts) == 2, note
    assert arts[0]["title"] == "第一篇", arts[0]
    assert arts[0]["url"] == "https://mp.weixin.qq.com/s/abc~def", arts[0]["url"]
    assert arts[1]["url"] == "https://mp.weixin.qq.com/s/xyz_123", arts[1]["url"]
    assert arts[0]["date"] == datetime.fromtimestamp(1778580003).strftime("%Y-%m-%d")
    # 兼容顶层 review 结构
    arts2, _ = parse_mp_articles({"reviews": [
        {"review": {"reviewId": "x", "createTime": 1778580001,
                    "mpInfo": {"title": "扁平结构", "originalId": "flat1"}}}]})
    assert len(arts2) == 1 and arts2[0]["url"].endswith("flat1"), arts2
    # 空返回
    empty, note2 = parse_mp_articles({"reviews": []})
    assert empty == [] and note2, note2
    # 搜索解析：只挑 MP_WXS_
    hits = parse_search_mp({"books": [
        {"bookInfo": {"bookId": "MP_WXS_3081621133", "title": "杭州电子科技大学"}},
        {"bookInfo": {"bookId": "3300014117", "title": "某本书"}}]})
    assert len(hits) == 1 and hits[0]["mp_id"] == "MP_WXS_3081621133", hits
    print("[OK] selftest 全部通过：字段映射、原文链接拼接、扁平/分组结构兼容、"
          "空返回、mpId 过滤 均正确")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "login":
        headed = "--headed" in sys.argv
        sys.exit(0 if login_via_playwright(headed=headed) else 1)
    if cmd == "status":
        sys.exit(status())
    if cmd == "resolve":
        if len(sys.argv) < 3:
            print("用法: python wechat_weread.py resolve <公众号名称>")
            sys.exit(2)
        cookie, _, _ = load_login()
        try:
            hits = resolve_mp(sys.argv[2], cookie)
        except Exception as e:  # noqa: BLE001
            print("搜索失败:", e)
            sys.exit(1)
        if not hits:
            print(f"未在微信读书找到公众号「{sys.argv[2]}」（可能未被收录）")
            sys.exit(1)
        for h in hits:
            print(f"  mpId={h['mp_id']}  {h['name']}  {h['intro']}")
        sys.exit(0)
    if cmd == "list":
        if len(sys.argv) < 3:
            print("用法: python wechat_weread.py list <mpId> [页数]")
            sys.exit(2)
        cookie, _, _ = load_login()
        pages = int(sys.argv[3]) if len(sys.argv) > 3 else 2
        arts, st = fetch_articles(sys.argv[2], cookie, max_pages=pages)
        print("状态:", st)
        for a in arts[:30]:
            print(f"  {a['date']}  {a['title'][:40]}  {a['url']}")
        sys.exit(0 if arts else 1)
    if cmd == "selftest":
        selftest()
        sys.exit(0)
    print(__doc__)


if __name__ == "__main__":
    main()
