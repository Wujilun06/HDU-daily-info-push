"""摘要：优先用大模型；未配置 key 时回退到抽取式摘要（免费离线）。"""
import re

import requests

from content_extract import fetch_html, html_to_text, extract_title
from private_config import get_llm_api_key


def _extractive_summary(text, max_chars=160):
    """抽取式摘要：取正文前若干句，截断到 max_chars。"""
    sentences = re.split(r"(?<=[。！？.!?])", text or "")
    sentences = [s.strip() for s in sentences if s.strip()]
    out = ""
    for s in sentences:
        if len(out) + len(s) > max_chars:
            break
        out += s
    return (out or text or "")[:max_chars].strip()


def _llm_summary(text, cfg):
    """调用 OpenAI 兼容接口做摘要；失败返回 None。"""
    if not (cfg.get("enabled") and cfg.get("api_key")):
        return None
    if not text:
        return None
    prompt = (
        "请用 3-5 句话用中文归纳以下文章的核心内容，不要复述标题，"
        "保留关键数字与结论：\n\n" + text[:3000]
    )
    try:
        r = requests.post(
            cfg["base_url"].rstrip("/") + "/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": cfg.get("model", "gpt-4o-mini"),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
            timeout=cfg.get("timeout", 30),
        )
        if r.ok:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:  # noqa: BLE001
        print(f"[warn] llm summary failed: {e}")
    return None


def summarize(article, cfg):
    """返回 {'title':..., 'summary':...}。"""
    link = article["link"]
    title = (article.get("title") or "").strip()
    snippet = (article.get("snippet") or "").strip()

    # 已有足够长的摘要则不再抓全文，省时省流量
    text = snippet
    if len(snippet) < 60:
        html = fetch_html(link)
        if html:
            if not title:
                title = extract_title(html, title)
            text = html_to_text(html)

    if text:
        summary = _llm_summary(text, cfg) or _extractive_summary(text)
    else:
        summary = "（暂无摘要，请前往原文查看）"

    if not title:
        title = "(无标题)"
    return {"title": title, "summary": summary.strip()}
