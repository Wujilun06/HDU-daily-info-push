"""多源抓取：website_rss / website_html / wechat_rss / wechat_manual。"""
import re
from datetime import datetime, timezone

import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from content_extract import fetch_html, extract_title


def _norm_link(url):
    """链接归一化：去掉 #fragment 与常见追踪参数，用于去重。"""
    url = (url or "").split("#")[0].strip()
    url = re.sub(r"[?&](utm_[^=&]+|spm|from|scene|subscene|variant|source)=[^&]*",
                 "", url)
    return url


def _strip_html(s):
    return BeautifulSoup(s or "", "html.parser").get_text(" ", strip=True)


def _ts(parsed):
    """feedparser time.struct_time -> 本地化 datetime（含时区）。"""
    if not parsed:
        return None
    try:
        return datetime(*parsed[:6], tzinfo=timezone.utc).astimezone()
    except Exception:  # noqa: BLE001
        return None


def _from_feed(source, feed_url):
    """通用：解析一个 RSS/Atom feed，返回文章字典列表。"""
    out = []
    d = feedparser.parse(feed_url)
    for entry in d.entries:
        link = _norm_link(entry.get("link", ""))
        if not link:
            continue
        snippet = ""
        if entry.get("summary"):
            snippet = _strip_html(entry["summary"])
        if entry.get("content"):
            snippet = _strip_html(entry["content"][0].get("value", ""))
        out.append({
            "title": (entry.get("title") or "").strip(),
            "link": link,
            "source": source["name"],
            "site": source.get("site", source["name"]),
            "source_id": source["id"],
            "published": _ts(entry.get("published_parsed") or
                            entry.get("updated_parsed")),
            "snippet": snippet,
            "category": source.get("category", ""),  # 预设分类优先
        })
    return out


def fetch_website_rss(source):
    return _from_feed(source, source["url"])


def fetch_wechat_rss(source):
    # 通用 RSS 解析：云端公众号 RSS 代理等也输出标准 RSS，复用同一逻辑
    return _from_feed(source, source["url"])


def fetch_wechat_manual(source):
    """手动导入：逐行读取 list_file 中的链接。"""
    out = []
    path = source.get("list_file")
    if not path:
        return out
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                link = line.strip()
                if not link or link.startswith("#"):
                    continue
                out.append({
                    "title": "",
                    "link": _norm_link(link),
                    "source": source["name"],
                    "site": source.get("site", source["name"]),
                    "source_id": source["id"],
                    "published": None,
                    "snippet": "",
                    "category": source.get("category", ""),
                })
    except FileNotFoundError:
        print(f"[warn] manual list not found: {path}")
    return out


def fetch_wechat_cookie(source):
    """② 轻量方案：用 cookie + __biz 抓单公众号文章列表（标题+链接）。

    依赖 wechat_lite.py（标准库实现）与 cookie_helper.py（cookie 管理）。
    配置示例见 config.yaml 的 wechat_cookie 源。
    """
    import os
    biz = source.get("biz") or ""
    if not biz or str(biz).startswith("REPLACE"):
        # 允许直接贴该号任意一篇文章链接，自动解析 __biz
        biz_url = source.get("biz_url") or ""
        try:
            from wechat_lite import extract_biz_from_url
            biz = extract_biz_from_url(biz_url) or ""
        except Exception:  # noqa: BLE001
            biz = ""
    if not biz:
        print(f"[warn] {source.get('id')} 未配置有效 __biz/biz_url，已跳过"
              f"（请在 config 填入真实 __biz 或该号任一文章链接）")
        return []
    # cookie 文件：优先源内 cookie_file，其次默认位置
    here = os.path.dirname(os.path.abspath(__file__))
    cookie_file = source.get("cookie_file") or os.path.join(here, "wechat_cookies.json")
    try:
        from cookie_helper import load_cookie, validate_cookie
        cookie, _ = load_cookie(cookie_file)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] {source.get('id')} 读取 cookie 失败: {e}")
        return []
    if not cookie:
        print(f"[warn] {source.get('id')} cookie 为空，请先运行 cookie_helper.py login")
        return []
    ok, msg = validate_cookie(cookie, biz)
    if not ok:
        print(f"[warn] {source.get('id')} cookie 校验未通过: {msg}（请重登）")
        return []
    try:
        from wechat_lite import fetch_account
        max_messages = source.get("max_messages", 20)
        arts, status = fetch_account(cookie, biz, max_messages=max_messages, delay=1.0)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] {source.get('id')} 抓取失败: {e}")
        return []
    out = []
    for a in arts:
        out.append({
            "title": a["title"],
            "link": _norm_link(a["url"]),
            "source": source["name"],
            "site": source.get("site", "微信公众号"),
            "source_id": source["id"],
            "published": a["datetime"],
            "snippet": a.get("digest", ""),
            "category": source.get("category", ""),
        })
    return out


def fetch_wechat_weread(source):
    """微信读书通道：用 mpId(形如 MP_WXS_xxxx) 抓单公众号文章（标题+原文链接+日期）。

    依赖 wechat_weread.py（扫码登录 + 文章列表接口，urllib/浏览器双通道兜底）。
    mpId 从用户在微信读书分享的链接里提取（见 wechat_weread.py 用法），
    填入 config 的 mp_id 字段即启用。
    """
    import os
    mp_id = source.get("mp_id") or ""
    if not mp_id or str(mp_id).startswith("REPLACE"):
        print(f"[warn] {source.get('id')} 未配置 mp_id（请在 config 填入 MP_WXS_xxxx，"
              f"可从微信读书分享链接里提取），已跳过")
        return []
    try:
        from wechat_weread import load_login, fetch_articles
        from private_config import exists as _pc_exists
        if not _pc_exists():
            print(f"[warn] {source.get('id')} 未找到 private_config.json，"
                  f"请先运行 python wechat_weread.py login")
            return []
        cookie, vid, desc = load_login()
        if not cookie:
            print(f"[warn] {source.get('id')} 登录态为空（{desc}），请重登")
            return []
        max_pages = source.get("max_pages", 3)
        arts, status = fetch_articles(mp_id, cookie, max_pages=max_pages)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] {source.get('id')} 抓取失败: {e}")
        return []
    print(f"[weread] {source.get('name')}（{mp_id}）: {status}")
    out = []
    for a in arts:
        out.append({
            "title": a["title"],
            "link": _norm_link(a["url"]),
            "source": source["name"],
            "site": source.get("site", "微信公众号"),
            "source_id": source["id"],
            "published": a["datetime"],
            "snippet": "",
            "category": source.get("category", ""),
        })
    return out


def _parse_date(s):
    """解析列表页中的日期文本，如 [2026-07-08] / 2026-07-08 10:00。"""
    if not s:
        return None
    s = s.strip().strip("[]()（）").replace("/", "-")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def fetch_website_html(source):
    """抓取官网列表页（如 cs.hdu.edu.cn 的 list.htm），解析文章条目。

    适用于无 RSS 的网站：通过 item_selector 定位列表项，从其中的 <a>
    取标题与链接，从 date_selector 取日期。默认适配杭电计算机学院官网。
    """
    out = []
    list_url = source["url"]
    html = fetch_html(list_url)
    if not html:
        return out
    soup = BeautifulSoup(html, "html.parser")
    base = source.get("base", list_url)
    item_sel = source.get("item_selector", "li")
    date_sel = source.get("date_selector", "span.date")
    banner_hint = source.get("banner_href_hint", "c6818")  # 跳过公共头条 banner
    for li in soup.select(item_sel):
        a = li.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        if "page.htm" not in href:          # 只要文章详情页
            continue
        if banner_hint and banner_hint in href:
            continue
        title = a.get_text(strip=True)
        if not title:
            continue
        link = _norm_link(urljoin(base, href))
        date_text = ""
        ds = li.select_one(date_sel)
        if ds:
            date_text = ds.get_text()
        pub = _parse_date(date_text)
        out.append({
            "title": title,
            "link": link,
            "source": source["name"],
            "site": source.get("site", source["name"]),
            "source_id": source["id"],
            "published": pub,
            "snippet": "",
            "category": source.get("category", ""),
        })
    max_items = source.get("max_items", 0)
    if max_items and len(out) > max_items:
        out = out[:max_items]
    return out


DISPATCH = {
    "website_rss": fetch_website_rss,
    "website_html": fetch_website_html,
    "wechat_rss": fetch_wechat_rss,
    "wechat_manual": fetch_wechat_manual,
    "wechat_cookie": fetch_wechat_cookie,
    "weread": fetch_wechat_weread,
}


def fetch_all(sources):
    """按配置抓取所有启用源，返回原始文章列表。"""
    out = []
    # 微信公众号（微信读书通道）改为「一次浏览器会话批量抓取」：
    # 只启动一次 Playwright，账号间留间隔，显著降低 -2014 限频，
    # 且浏览器同源请求能正确识别所有 mpId（urllib 通道会误报 -2003）。
    weread_sources = [s for s in sources
                      if s.get("enabled", True) and s.get("type") == "weread"]
    weread_cache = {}
    if weread_sources:
        try:
            from wechat_weread import fetch_wechat_weread_batch
            # 每账号最多 2 页（日常增量够用），账号间留 12s 间隔降低 -2014 限频
            res, st = fetch_wechat_weread_batch(weread_sources,
                                               max_pages=1,
                                               account_interval=15.0)
            weread_cache = res or {}
            print(f"[weread] 批量抓取: {st}（命中 {len(weread_cache)} 个源）")
        except Exception as e:  # noqa: BLE001
            print(f"[warn] weread 批量抓取失败: {e}")
    for s in sources:
        if not s.get("enabled", True):
            continue
        fn = DISPATCH.get(s.get("type"))
        if not fn:
            print(f"[warn] unknown source type: {s.get('type')} ({s.get('id')})")
            continue
        try:
            if s.get("type") == "weread":
                # 优先用批量结果；批量失败（异常/空）时回退到单源浏览器抓取
                if s["id"] in weread_cache:
                    arts = weread_cache[s["id"]]
                else:
                    arts = fn(s)
                print(f"[weread] {s.get('name')}（{s.get('mp_id')}）: {len(arts)} 条")
            else:
                arts = fn(s)
                print(f"[fetch] {s.get('id')}: {len(arts)} 条")
            out.extend(arts)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] source {s.get('id')} failed: {e}")
    return out
