#!/usr/bin/env python3
"""
微信公众号文章爬虫 - 一键运行
获取文章 + 生成报告
纯标准库实现，无第三方依赖
"""
import os
import sys
import time
import json
import argparse
import urllib.request
from datetime import datetime
from collections import defaultdict

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

CATEGORIES = {
    '展会/峰会邀请': ['展会', '峰会', '邀请', '年会', '博览会', '论坛', '大会', '药机', '制药', '制药机械', '化工', '石油'],
    '放假通知': ['放假', '通知', '春节', '元旦', '中秋', '国庆', '圣诞'],
    '公司动态': ['WEBOWT在', '全球', '注册', '认证', '销售', '称重', '全球注册', '全球认证'],
    '节日祝福': ['快乐', '祝福', '元宵', '端午', '月圆', '圣诞', '元旦快乐', '春节'],
    '活动回顾': ['回顾', '精彩', '圆满', '成功', '感谢', '共赴', '聚势', '同行'],
    '产品/技术': ['产品', '技术', '解决方案', '系统', '设备'],
}

def parse_args():
    parser = argparse.ArgumentParser(description='微信公众号文章爬虫 - 一键运行')
    parser.add_argument('--cookie', required=True, help='微信 Cookie 字符串')
    parser.add_argument('--biz', required=True, help='公众号 __biz 参数')
    parser.add_argument('--name', default='公众号', help='公众号名称（用于输出文件）')
    parser.add_argument('--output-dir', default='./', help='输出目录')
    parser.add_argument('--delay', type=float, default=0.5, help='请求间隔（秒）')
    return parser.parse_args()

def build_headers(cookie):
    return {
        'Cookie': cookie,
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 26_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.70(0x18004624) NetType/WIFI Language/zh_CN',
        'Referer': 'https://mp.weixin.qq.com/',
        'X-Requested-With': 'XMLHttpRequest',
    }

def parse_articles(raw_articles):
    """解析文章列表"""
    articles = []
    for item in raw_articles:
        comm_msg = item.get('comm_msg_info', {})
        app_msg = item.get('app_msg_ext_info', {})
        
        dt_timestamp = comm_msg.get('datetime', 0)
        dt = datetime.fromtimestamp(dt_timestamp)
        
        title = app_msg.get('title', '')
        if not title:
            continue
            
        articles.append({
            'title': title,
            'date': dt.strftime('%Y-%m-%d'),
            'datetime': dt.isoformat(),
            'year': dt.year,
            'month': dt.month,
            'url': app_msg.get('content_url', '').replace('&amp;', '&'),
            'cover': app_msg.get('cover', ''),
            'author': app_msg.get('author', ''),
            'digest': app_msg.get('digest', ''),
            'type': 'multi' if app_msg.get('is_multi', 0) else 'single',
        })
        
        for sub_item in app_msg.get('multi_app_msg_item_list', []):
            sub_title = sub_item.get('title', '')
            if sub_title:
                articles.append({
                    'title': sub_title,
                    'date': dt.strftime('%Y-%m-%d'),
                    'datetime': dt.isoformat(),
                    'year': dt.year,
                    'month': dt.month,
                    'url': sub_item.get('content_url', '').replace('&amp;', '&'),
                    'cover': sub_item.get('cover', ''),
                    'author': sub_item.get('author', ''),
                    'digest': sub_item.get('digest', ''),
                    'type': 'sub-article',
                })
    return articles

def deduplicate(articles):
    seen = set()
    unique = []
    for a in articles:
        key = (a['title'], a['date'])
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique

def fetch_all_articles(cookie, biz, delay=0.5):
    """获取全部文章"""
    # 提取参数
    params = {}
    for item in cookie.split(';'):
        item = item.strip()
        if '=' in item:
            key, val = item.split('=', 1)
            key = key.strip()
            if key == 'pass_ticket':
                params['pass_ticket'] = val
            elif key == 'wxtokenkey':
                params['wxtoken'] = val
            elif key == 'appmsg_token':
                params['appmsg_token'] = val
            elif key == 'wxuin':
                params['wxuin'] = val
    
    all_raw = []
    offset = 0
    max_offset = 1000
    
    while offset < max_offset:
        print(f"  获取 offset={offset} ...", end='', flush=True)
        
        url = f"https://mp.weixin.qq.com/mp/profile_ext?action=getmsg&__biz={biz}&f=json&offset={offset}&count=10&is_ok=1&scene=126&sessionid={int(time.time())}"
        for k, v in params.items():
            url += f"&{k}={v}"
        
        try:
            req = urllib.request.Request(url, headers=build_headers(cookie))
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            
            if data.get('ret') != 0:
                print(f" 失败 (ret={data.get('ret')})")
                break
            
            general_msg_list = json.loads(data.get('general_msg_list', '{"list":[]}'))
            raw = general_msg_list.get('list', [])
            
            if not raw:
                print(" 已无更多")
                break
            
            all_raw.extend(raw)
            print(f" +{len(raw)}")
            
            if not data.get('can_msg_continue'):
                break
            
            offset += 10
            time.sleep(delay)
        except Exception as e:
            print(f" 错误: {e}")
            break
    
    return all_raw

def main():
    args = parse_args()
    
    print(f"\n📱 微信公众号文章爬虫")
    print(f"=" * 40)
    print(f"公众号: {args.name}")
    print(f"__biz:  {args.biz[:20]}...")
    print()
    
    # 1. 获取文章
    print(f"📥 第一步：获取文章列表")
    print("-" * 40)
    raw_articles = fetch_all_articles(args.cookie, args.biz, args.delay)
    
    if not raw_articles:
        print("❌ 获取文章失败")
        return
    
    articles = parse_articles(raw_articles)
    articles = deduplicate(articles)
    articles.sort(key=lambda x: x['datetime'], reverse=True)
    
    print(f"\n✅ 共获取 {len(articles)} 篇文章")
    
    # 2. 生成报告
    print(f"\n📊 第二步：生成统计报告")
    print("-" * 40)
    
    # 分类
    for a in articles:
        title = a['title']
        categorized = False
        for cat, keywords in CATEGORIES.items():
            for kw in keywords:
                if kw in title:
                    a['category'] = cat
                    categorized = True
                    break
            if categorized:
                break
        if not categorized:
            a['category'] = '其他'
    
    # 统计
    year_counts = defaultdict(int)
    cat_counts = defaultdict(int)
    ym_articles = defaultdict(list)
    
    for a in articles:
        year_counts[a['year']] += 1
        cat_counts[a['category']] += 1
        ym_articles[(a["year"], a["month"])].append(a)
    
    # 生成 Markdown
    report = f"""# {args.name} 公众号文章统计报告

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
    for (y, m), arts in sorted(ym_articles.items(), reverse=True):
        report += f"### {y}年{m:02d}月 ({len(arts)}篇)\n\n"
        for a in arts:
            report += f"- [{a['title']}]({a['url']})  `[{a['category']}]`\n"
        report += "\n"

    report += """
---

*由莫殇自动生成*
"""
    
    # 保存
    os.makedirs(args.output_dir, exist_ok=True)
    json_path = os.path.join(args.output_dir, f"{args.name}_articles.json")
    md_path = os.path.join(args.output_dir, f"{args.name}_report.md")
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n✅ 完成！")
    print(f"📁 文章数据: {json_path}")
    print(f"📁 统计报告: {md_path}")

if __name__ == '__main__':
    main()
