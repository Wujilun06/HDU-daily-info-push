#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
轻量微信公众号文章抓取（纯标准库，无第三方依赖）。

机制
----
通过 mp.weixin.qq.com 的 profile_ext 接口获取某公众号的历史文章列表：
  1. action=home   取主页，从中实时解析出动态令牌 appmsg_token（极短效，必须每次重新取）
  2. action=getmsg 分页拉取文章（offset 递增，最新在前）

前置条件（由使用方提供）：
  - cookie：登录态字符串，需包含 pass_ticket 等（见 cookie_helper.py）
  - __biz ：公众号唯一标识，可从任意一篇该号文章链接的 &__biz= 参数取得

输出：归一化文章字典列表，字段与 fetcher.py 的 website_html 源对齐，
      便于直接并入每日信息流。
"""
import json
import re
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from http.cookiejar import CookieJar, Cookie

PROFILE_HOME = "https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz={biz}"
PROFILE_MSG = (
    "https://mp.weixin.qq.com/mp/profile_ext?action=getmsg&__biz={biz}"
    "&f=json&offset={offset}&count={count}&is_ok=1&scene=126"
    "&sub_action=list_ex&sessionid={sessionid}"
)
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 26_3_1 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
      "MicroMessenger/8.0.70(0x18004624) NetType/WIFI Language/zh_CN")


def extract_biz_from_url(url):
    """从文章/主页链接里解析 __biz 参数。"""
    if not url:
        return None
    m = re.search(r"[?&]__biz=([^&]+)", url)
    if m:
        return urllib.parse.unquote(m.group(1))
    return None


def _add_cookie(jar, name, value, domain="mp.weixin.qq.com"):
    """把用户提供的 cookie 键值对预置进 cookiejar，让后续请求自动携带。"""
    try:
        c = Cookie(
            version=0, name=name, value=value, port=None, port_specified=False,
            domain=domain, domain_specified=True, domain_initial_dot=False,
            path="/", path_specified=True, secure=False, expires=None,
            discard=False, comment=None, comment_url=None, rest={},
            rfc2109=False,
        )
        jar.set_cookie(c)
    except Exception:  # noqa: BLE001
        pass


def _build_jar(cookie_str):
    """把 'k1=v1; k2=v2' 形式的 cookie 字符串解析进 CookieJar。"""
    jar = CookieJar()
    for item in (cookie_str or "").split(";"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            _add_cookie(jar, k.strip(), v.strip())
    return jar


def _build_opener(jar):
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def _get_json(opener, url, cookie_str):
    req = urllib.request.Request(url, headers={
        "Cookie": cookie_str,
        "User-Agent": UA,
        "Referer": "https://mp.weixin.qq.com/",
        "X-Requested-With": "XMLHttpRequest",
    })
    with opener.open(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


def fetch_appmsg_token(opener, cookie_str, biz):
    """访问主页，从返回内容里实时解析动态令牌 appmsg_token。

    返回 (token, errmsg)。token 为空代表未取得（cookie 可能已失效）。
    """
    url = PROFILE_HOME.format(biz=biz)
    try:
        req = urllib.request.Request(url, headers={
            "Cookie": cookie_str,
            "User-Agent": UA,
            "Referer": "https://mp.weixin.qq.com/",
        })
        with opener.open(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return "", f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return "", str(e)
    m = re.search(r"appmsg_token[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']", html)
    if m:
        return m.group(1), ""
    # 某些返回是 JSON（ret 非 0 表示未登录）
    try:
        data = json.loads(html)
        if data.get("ret") not in (0, None):
            return "", f"ret={data.get('ret')}:{data.get('errmsg')}"
    except Exception:  # noqa: BLE001
        pass
    return "", "无法从主页解析 appmsg_token（cookie 可能已失效）"


def fetch_messages(opener, cookie_str, biz, appmsg_token, offset, count):
    """拉取单页文章，返回 (raw_list, can_continue, ret, errmsg)。"""
    sessionid = int(time.time())
    url = PROFILE_MSG.format(biz=biz, offset=offset, count=count,
                             sessionid=sessionid)
    if appmsg_token:
        url += f"&appmsg_token={urllib.parse.quote(appmsg_token)}"
    # pass_ticket 等由 cookie 自动携带
    try:
        data = _get_json(opener, url, cookie_str)
    except Exception as e:  # noqa: BLE001
        return [], False, -1, f"请求失败: {e}"
    if data.get("ret") != 0:
        return [], False, data.get("ret", -1), data.get("errmsg", "未知错误")
    try:
        gml = json.loads(data.get("general_msg_list", '{"list":[]}'))
    except Exception:  # noqa: BLE001
        gml = {"list": []}
    raw = gml.get("list", [])
    can_continue = bool(data.get("can_msg_continue", 0)) and len(raw) > 0
    return raw, can_continue, 0, ""


def parse_messages(raw_list):
    """把原始消息列表解析为归一化文章字典（含多图文子文章）。"""
    out = []
    for item in raw_list:
        comm = item.get("comm_msg_info", {})
        app = item.get("app_msg_ext_info", {})
        ts = comm.get("datetime", 0)
        if not ts:
            continue
        dt = datetime.fromtimestamp(ts)  # 微信时间戳为东八区本地秒
        main_title = (app.get("title") or "").strip()
        if main_title:
            out.append(_mk(app, dt))
        for sub in app.get("multi_app_msg_item_list", []) or []:
            sub_title = (sub.get("title") or "").strip()
            if sub_title:
                out.append(_mk(sub, dt))
    return out


def _mk(msg, dt):
    url = (msg.get("content_url") or "").replace("&amp;", "&").strip()
    return {
        "title": (msg.get("title") or "").strip(),
        "date": dt.strftime("%Y-%m-%d"),
        "datetime": dt,
        "url": url,
        "author": msg.get("author", ""),
        "digest": msg.get("digest", ""),
        "cover": msg.get("cover", ""),
    }


def fetch_account(cookie_str, biz, max_messages=20, delay=1.0,
                 cutoff_date=None):
    """抓取某公众号文章，返回归一化文章列表（最新在前）。

    :param cookie_str: 登录态 cookie 字符串
    :param biz:        公众号 __biz
    :param max_messages: 最多抓取的消息条数（每条约对应一次推送，含多图文）
    :param delay:        分页间隔（秒），降低风控风险
    :param cutoff_date:  datetime，早于该日期的文章不再继续翻页（用于"每日新增"轻量抓取）
    :return: (articles, status)  status 为可读状态说明（含失败原因）
    """
    if not cookie_str or not biz:
        return [], "缺少 cookie 或 __biz"
    jar = _build_jar(cookie_str)
    opener = _build_opener(jar)
    token, err = fetch_appmsg_token(opener, cookie_str, biz)
    if not token:
        return [], f"获取 appmsg_token 失败: {err}"
    articles = []
    offset = 0
    count = 10
    fetched_msgs = 0
    while fetched_msgs < max_messages:
        raw, can_continue, ret, errmsg = fetch_messages(
            opener, cookie_str, biz, token, offset, count)
        if ret != 0:
            return articles, f"接口返回错误(ret={ret}): {errmsg}"
        if not raw:
            break
        page = parse_messages(raw)
        # 按发布时间早停：本页最旧一篇已早于 cutoff 则停止翻页
        stop = False
        for a in page:
            if cutoff_date and a["datetime"] < cutoff_date:
                stop = True
                break
            articles.append(a)
        fetched_msgs += len(raw)
        offset += count
        if not can_continue or stop:
            break
        time.sleep(delay)
    articles.sort(key=lambda x: x["datetime"], reverse=True)
    return articles, f"成功获取 {len(articles)} 篇"


if __name__ == "__main__":
    # 简单自测：需要真实 cookie + biz，仅作手动验证用
    import sys
    if len(sys.argv) >= 3:
        c = fetch_account(sys.argv[1], sys.argv[2], max_messages=5)
        print(json.dumps(c, ensure_ascii=False, indent=2))
    else:
        print("usage: wechat_lite.py <cookie> <biz>")
