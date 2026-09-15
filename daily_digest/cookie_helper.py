#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号 Cookie 助手
========================

解决两件事：
  1. 校验 cookie 是否还有效（每次运行前自动检查，失效则提示重登）
  2. 自动抓取 cookie：Playwright 扫码登录一次，把登录态持久化到文件；
     之后每次运行自动加载，无需手动复制 cookie 字符串。
     （完全自动登录不可能——必须用手机扫二维码，这一步需人参与。）

用法
----
  python cookie_helper.py login     # 弹出二维码，手机微信扫码，自动保存
  python cookie_helper.py status    # 检查当前 cookie 是否有效
  python cookie_helper.py show      # 打印当前 cookie（调试用）
"""
import json
import os
import sys
import time

# 默认 cookie 存放位置（与 config.yaml 中 wechat_cookie 源的 cookie_file 对应）
DEFAULT_COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "wechat_cookies.json")

from wechat_lite import fetch_appmsg_token, _build_jar, _build_opener  # noqa: E402


def load_cookie(cookie_file=DEFAULT_COOKIE_FILE):
    """从文件读取 cookie 字符串。支持两种格式：
       - JSON（本助手保存，含 raw 字段）
       - 纯文本（DevTools 复制的原始 cookie 字符串）
    返回 (cookie_str, source_desc)。
    """
    if not os.path.exists(cookie_file):
        return "", f"文件不存在: {cookie_file}"
    try:
        with open(cookie_file, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and data.get("raw"):
            return data["raw"], "json(raw)"
        if isinstance(data, list):  # playwright cookies 列表
            raw = "; ".join(f"{c['name']}={c['value']}" for c in data)
            return raw, "json(list)"
    except (json.JSONDecodeError, KeyError):
        pass
    # 当作纯文本
    with open(cookie_file, encoding="utf-8") as f:
        return f.read().strip(), "text"


def save_cookie(cookies, cookie_file=DEFAULT_COOKIE_FILE, raw=None):
    """保存 cookie。cookies 为 playwright 的 cookie 列表；raw 为原始字符串。"""
    payload = {
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cookies": cookies,
        "raw": raw or "; ".join(f"{c['name']}={c['value']}" for c in cookies),
    }
    with open(cookie_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return cookie_file


def validate_cookie(cookie_str, biz_for_probe=None):
    """校验 cookie 是否有效：尝试从主页取得 appmsg_token。
    返回 (ok: bool, msg: str)。
    """
    if not cookie_str:
        return False, "无 cookie"
    jar = _build_jar(cookie_str)
    opener = _build_opener(jar)
    # 若未提供 biz，用首页探测即可（首页不需要 biz）
    probe_biz = biz_for_probe or "MjM5MDQwNzcwMA=="  # 任意非空占位
    token, err = fetch_appmsg_token(opener, cookie_str, probe_biz)
    if token:
        return True, "cookie 有效（可获取 appmsg_token）"
    return False, f"cookie 可能已失效: {err}"


def login_via_playwright(cookie_file=DEFAULT_COOKIE_FILE, timeout=180):
    """用 Playwright 打开 mp.weixin.qq.com 登录页，截图二维码，等待扫码，
    成功后把 cookie 持久化到文件。需要在本机先安装：
        pip install playwright && playwright install chromium
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("⚠️ 未检测到 Playwright。请先安装：")
        print("    pip install playwright")
        print("    playwright install chromium")
        return False

    print("🌐 正在打开微信公众平台登录页...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"))
        page = ctx.new_page()
        page.goto("https://mp.weixin.qq.com/", wait_until="domcontentloaded")

        # 定位二维码（在登录 iframe 内）
        qr_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "wechat_login_qr.png")
        try:
            frame = page.frame_locator("#login_frame")
            qr = frame.locator("img#js_qrcode")
            qr.wait_for(state="visible", timeout=30000)
            qr.screenshot(path=qr_path)
            print(f"📱 二维码已保存至：{qr_path}")
            print("   请用手机微信「扫一扫」该图片完成登录（需在 3 分钟内完成）。")
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ 未能定位二维码元素：{e}")
            print("   可能页面已自动登录，或布局有变化，继续等待登录状态...")

        try:
            # 登录成功后 URL 会跳转到 cgi-bin/home
            page.wait_for_url("**/cgi-bin/home**", timeout=timeout * 1000)
        except Exception:  # noqa: BLE001
            # 兜底：等待出现登录后才有的元素
            try:
                page.wait_for_selector("img.avatar, .account_name, #js_account",
                                       timeout=timeout * 1000)
            except Exception as e:  # noqa: BLE001
                print(f"❌ 等待登录超时：{e}")
                browser.close()
                return False

        cookies = ctx.cookies()
        browser.close()

        if not cookies:
            print("❌ 未获取到任何 cookie，登录可能未完成。")
            return False
        save_cookie(cookies, cookie_file)
        print(f"✅ 登录成功！cookie 已保存到：{cookie_file}")
        print(f"   （共 {len(cookies)} 条，建议每 1–3 天重新运行 login 刷新）")
        return True


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    cf = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_COOKIE_FILE
    if cmd == "login":
        login_via_playwright(cf)
    elif cmd == "status":
        cookie, src = load_cookie(cf)
        ok, msg = validate_cookie(cookie)
        print(f"来源: {src}")
        print(f"状态: {'✅ ' if ok else '❌ '}{msg}")
        sys.exit(0 if ok else 1)
    elif cmd == "show":
        cookie, src = load_cookie(cf)
        print(f"来源: {src}")
        print(cookie[:200] + ("..." if len(cookie) > 200 else ""))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
