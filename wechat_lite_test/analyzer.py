#!/usr/bin/env python3
"""
微信公众号文章分析器 - 生成统计报告
纯标准库实现，无第三方依赖
"""
import json
import argparse
from datetime import datetime
from collections import defaultdict

CATEGORIES = {
    '展会/峰会邀请': ['展会', '峰会', '邀请', '年会', '博览会', '论坛', '大会', '药机', '制药', '制药机械', '化工', '石油'],
    '放假通知': ['放假', '通知', '春节', '元旦', '中秋', '国庆', '圣诞'],
    '公司动态': ['WEBOWT在', '全球', '注册', '认证', '销售', '称重', '全球注册', '全球认证'],
    '节日祝福': ['快乐', '祝福', '元宵', '端午', '月圆', '圣诞', '元旦快乐', '春节'],
    '活动回顾': ['回顾', '精彩', '圆满', '成功', '感谢', '共赴', '聚势', '同行'],
    '产品/技术': ['产品', '技术', '解决方案', '系统', '设备'],
}

def categorize(title):
    """根据标题分类"""
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in title:
                return cat
    return '其他'

def parse_args():
    parser = argparse.ArgumentParser(description='微信公众号文章分析器')
    parser.add_argument('--input', required=True, help='文章 JSON 文件路径')
    parser.add_argument('--output', default='./report.md', help='输出 Markdown 报告路径')
    parser.add_argument('--name', default='公众号', help='公众号名称')
    return parser.parse_args()

def generate_report(articles, name):
    """生成 Markdown 报告"""
    # 分类
    for a in articles:
        a['category'] = categorize(a['title'])
    
    # 统计
    year_counts = defaultdict(int)
    cat_counts = defaultdict(int)
    ym_counts = defaultdict(int)
    
    for a in articles:
        year_counts[a['year']] += 1
        cat_counts[a['category']] += 1
        ym_counts[(a['year'], a['month'])] += 1
    
    # 生成报告
    report = f"""# {name} 公众号文章统计报告

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## 总览

| 项目 | 数值 |
|------|------|
| 总文章数 | {len(articles)} 篇 |
| 统计年份 | {min(a['year'] for a in articles)} - {max(a['year'] for a in articles)} |

---

## 年度发布统计

| 年份 | 文章数 | 占比 |
|------|--------|------|
"""
    for y in sorted(year_counts.keys()):
        pct = year_counts[y] / len(articles) * 100
        report += f"| {y} | {year_counts[y]} 篇 | {pct:.1f}% |\n"

    report += """
---

## 分类统计

| 分类 | 文章数 | 占比 |
|------|--------|------|
"""
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        pct = count / len(articles) * 100
        report += f"| {cat} | {count} 篇 | {pct:.1f}% |\n"

    report += """
---

## 完整文章列表

"""
    for (y, m), arts in sorted(ym_counts.items(), reverse=True):
        report += f"### {y}年{m:02d}月 ({len(arts)}篇)\n\n"
        for a in arts:
            report += f"- [{a['title']}]({a['url']})  `[{a['category']}]`\n"
        report += "\n"

    report += f"""
---

*由莫殇自动生成*
"""
    return report

def main():
    args = parse_args()
    
    # 读取文章
    with open(args.input, 'r', encoding='utf-8') as f:
        articles = json.load(f)
    
    # 生成报告
    report = generate_report(articles, args.name)
    
    # 保存
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✅ 报告已生成: {args.output}")

if __name__ == '__main__':
    main()
