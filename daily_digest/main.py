"""每日信息整合推送 —— 主程序。

用法：
  python main.py --once           # 立即抓取一次并生成网页
  python main.py --demo           # 用内置样例数据跑通流程（离线，便于验证）
  python main.py --config x.yaml  # 指定配置文件
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
import fetcher
import classifier
import summarizer
import generator

DEFAULT_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _demo_articles():
    """内置样例，离线验证用（snippet 已足够长，不会触发联网抓取）。"""
    return [
        {"title": "用 Python 实现一个轻量调度器", "link": "https://example.com/p1",
         "source": "样例源A", "source_id": "demo", "published": datetime.now(timezone.utc) - timedelta(hours=3),
         "snippet": "本文介绍了如何用 Python 的 schedule 库与线程实现一个每日定时任务。核心思路是把抓取、去重、分类、摘要拆成独立函数，主循环在固定时刻触发。文中给出了完整可运行的代码示例，并讨论了失败重试与日志记录的实践。"},
        {"title": "大模型推理成本为何居高不下", "link": "https://example.com/p2",
         "source": "样例源B", "source_id": "demo", "published": datetime.now(timezone.utc) - timedelta(hours=8),
         "snippet": "文章分析了当前大模型在推理阶段的算力消耗结构，指出 KV Cache 与注意力计算是主要开销。作者建议通过量化、批处理与缓存复用降低单位成本，并比较了几家云厂商的定价差异。"},
        {"title": "本周科技新闻：三款新机发布", "link": "https://example.com/p3",
         "source": "样例源C", "source_id": "demo", "published": datetime.now(timezone.utc) - timedelta(hours=20),
         "snippet": "本周多家厂商发布了新品手机，主打影像与续航。发布会现场公布了芯片规格与售价，市场反应两极分化。本文汇总了主要参数对比与首批评测结论。"},
        {"title": "经济观察：通胀回落但利率仍高", "link": "https://example.com/p4",
         "source": "样例源D", "source_id": "demo", "published": datetime.now(timezone.utc) - timedelta(days=1),
         "snippet": "最新数据显示通胀同比回落至目标区间附近，但央行表态维持高利率更久。投资机构调整了股票与债券的仓位，市场波动加剧。文章解读了货币政策路径对普通投资者的含义。"},
    ]


def run(cfg, demo=False):
    settings = cfg.get("settings", {})
    categories = cfg.get("categories", [])
    llm = cfg.get("llm", {})
    out_dir = settings.get("output_dir", "output")
    base = os.path.dirname(os.path.abspath(DEFAULT_CONFIG))
    out_dir = out_dir if os.path.isabs(out_dir) else os.path.join(base, out_dir)
    os.makedirs(out_dir, exist_ok=True)

    lookback = settings.get("lookback_days", 2)
    cutoff = datetime.now() - timedelta(days=lookback) if lookback else None

    raw = _demo_articles() if demo else fetcher.fetch_all(cfg.get("sources", []))

    # 去重（优先用源提供的稳定键，如搜狗 url= 哈希；否则退回归一化链接）
    dedup, articles = set(), []
    for a in raw:
        key = a.get("dedup_key") or a["link"]
        if key in dedup:
            continue
        dedup.add(key)
        # 统一为 naive 时间，避免时区比较报错
        if a.get("published"):
            a["published"] = a["published"].replace(tzinfo=None)
        if cutoff and a.get("published") and a["published"] < cutoff:
            continue
        articles.append(a)

    # 展示口径：直接展示本次抓取到的全部文章，并以“生成日”作为“当天新增”的口径。
    # 说明：官网各板块每日列表基本稳定，若按“跨运行链接去重(seen.json)”会令第二次起
    # 全部被判为旧文章而页面空白，故不再跨运行隐藏历史文章。
    # 如需仅显示相对上次真正新增的链接，可在此恢复 seen.json 增量逻辑。
    new_articles = articles

    # 分类 + 摘要
    for a in new_articles:
        a["category"] = classifier.classify(a, categories)
        s = summarizer.summarize(a, llm)
        a["title"] = s["title"] or a.get("title") or "(无标题)"
        a["summary"] = s["summary"]
        pub = a.get("published")
        if pub:
            # 网站列表页常只给日期、不给时间，解析后时间为 00:00:00。
            # 此时只显示日期，避免“所有文章都在 00:00 发布”的误导。
            if pub.hour == 0 and pub.minute == 0:
                a["published_str"] = pub.strftime("%Y-%m-%d")
            else:
                a["published_str"] = pub.strftime("%Y-%m-%d %H:%M")
        else:
            a["published_str"] = ""

    new_articles.sort(
        key=lambda x: x.get("published") or datetime.min,
        reverse=True,
    )

    out = generator.generate(new_articles, cfg, out_dir)
    print(f"[ok] 生成 {len(new_articles)} 篇文章 -> {out}")
    return out


def main():
    ap = argparse.ArgumentParser(description="每日信息整合推送")
    ap.add_argument("--once", action="store_true", help="立即抓取一次并生成网页")
    ap.add_argument("--demo", action="store_true", help="用内置样例离线跑通流程")
    ap.add_argument("--config", default=DEFAULT_CONFIG, help="配置文件路径")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.demo:
        run(cfg, demo=True)
    elif args.once:
        run(cfg, demo=False)
    else:
        # 默认等同 --once
        run(cfg, demo=False)


if __name__ == "__main__":
    main()
