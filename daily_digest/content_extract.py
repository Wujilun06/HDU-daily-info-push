"""正文与标题提取：给定 URL 或 HTML，尽量取出干净的正文文本。"""
import re
import requests
from bs4 import BeautifulSoup

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def fetch_html(url, timeout=15):
    """抓取页面 HTML，失败返回 None。"""
    try:
        r = requests.get(url, headers=UA, timeout=timeout)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or r.encoding
        return r.text
    except Exception as e:  # noqa: BLE001
        print(f"[warn] fetch_html failed: {url} -> {e}")
        return None


def html_to_text(html):
    """从 HTML 中抽取正文纯文本（去掉脚本/样式/导航等噪声）。"""
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer",
                    "aside", "noscript", "svg", "iframe", "form"]):
        tag.decompose()
    main = soup.find(["article", "main"]) or soup.body or soup
    text = main.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:6000]


def extract_title(html, fallback=""):
    soup = BeautifulSoup(html or "", "html.parser")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return fallback
