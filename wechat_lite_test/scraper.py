#!/usr/bin/env python3
"""
微信公众号文章爬虫 - 批量获取文章列表
纯标准库实现，无第三方依赖
"""
import json
import os
import sys
import time
import argparse
import urllib.request
import urllib.parse
from datetime import datetime
from collections import defaultdict

def parse_args():
    parser = argparse.ArgumentParser(description='微信公众号文章爬虫')
    parser.add_argument('--cookie', required=True, help='微信 Cookie 字符串')
    parser.add_argument('--biz', required=True, help='公众号 __biz 参数')
    parser.add_argument('--output', default='./articles.json', help='输出 JSON 文件路径')
    parser.add_argument('--offset', type=int, default=0, help='分页偏移量')
    parser.add_argument('--count', type=int, default=10, help='每次请求数量')
    parser.add_argument('--all', action='store_true', default=True, help='获取全部文章')
    parser.add_argument('--delay', type=float, default=0.5, help='请求间隔（秒）')
    return parser.parse_args()

def build_headers(cookie, biz):
    """构建请求头"""
    return {
        'Cookie': cookie,
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 26_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.70(0x18004624) NetType/WIFI Language/zh_CN',
        'Referer': 'https://mp.weixin.qq.com/',
        'X-Requested-With': 'XMLHttpRequest',
    }

def fetch_articles(cookie, biz, offset=0, count=10):
    """获取单页文章"""
    # 提取必要参数
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
    
    # 构建 URL
    base_url = f"https://mp.weixin.qq.com/mp/profile_ext?action=getmsg&__biz={biz}&f=json&offset={offset}&count={count}&is_ok=1&scene=126&sessionid={int(time.time())}"
    for k, v in params.items():
        base_url += f"&{k}={v}"
    
    try:
        req = urllib.request.Request(base_url, headers=build_headers(cookie, biz))
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        if data.get('ret') != 0:
            print(f"API 返回错误: ret={data.get('ret')}, errmsg={data.get('errmsg')}")
            return None, 0, 0
        
        general_msg_list = json.loads(data.get('general_msg_list', '{"list":[]}'))
        articles = general_msg_list.get('list', [])
        msg_count = data.get('msg_count', 0)
        can_continue = data.get('can_msg_continue', 0)
        
        return articles, msg_count, can_continue
    except Exception as e:
        print(f"请求失败: {e}")
        return None, 0, 0

def parse_articles(raw_articles):
    """解析文章列表"""
    articles = []
    
    for item in raw_articles:
        comm_msg = item.get('comm_msg_info', {})
        app_msg = item.get('app_msg_ext_info', {})
        
        dt_timestamp = comm_msg.get('datetime', 0)
        dt = datetime.fromtimestamp(dt_timestamp)
        
        # 主文章
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
        
        # 多图文子文章
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
    """去重"""
    seen = set()
    unique = []
    for a in articles:
        key = (a['title'], a['date'])
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique

def main():
    args = parse_args()
    
    print(f"开始抓取公众号文章...")
    print(f"__biz: {args.biz}")
    print(f"输出文件: {args.output}")
    
    all_raw_articles = []
    offset = args.offset
    max_offset = 1000  # 防止无限循环
    
    while offset < max_offset:
        print(f"正在获取 offset={offset} ...", end='')
        raw_articles, msg_count, can_continue = fetch_articles(args.cookie, args.biz, offset, args.count)
        
        if raw_articles is None:
            print(" 失败，停止")
            break
        
        if not raw_articles and offset > 0:
            print(" 已无更多文章")
            break
        
        all_raw_articles.extend(raw_articles)
        print(f" 获取到 {len(raw_articles)} 条")
        
        if not can_continue or msg_count == 0:
            break
        
        offset += args.count
        time.sleep(args.delay)
    
    # 解析文章
    articles = parse_articles(all_raw_articles)
    articles = deduplicate(articles)
    
    # 按时间倒序
    articles.sort(key=lambda x: x['datetime'], reverse=True)
    
    # 保存
    out_dir = os.path.dirname(args.output) or '.'
    os.makedirs(out_dir, exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 完成！共获取 {len(articles)} 篇文章")
    print(f"📁 已保存到: {args.output}")

if __name__ == '__main__':
    main()
