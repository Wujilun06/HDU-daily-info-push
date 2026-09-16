import os, re
p = 'E:/个人项目/每日信息整合推送/daily_digest/output/index.html'
html = open(p, encoding='utf-8', errors='replace').read()
times = re.findall(r'published:\s*"([^"]+)"', html)
print('总 published 条数:', len(times))
print('含 00:00 的条数:', sum(1 for t in times if '00:00' in t))
print('样例(前8):')
for t in times[:8]:
    print('  ', t)
print('全部为纯日期(YYYY-MM-DD)的条数:', sum(1 for t in times if re.fullmatch(r'\d{4}-\d{2}-\d{2}', t)))
print('index.html mtime:', os.path.getmtime(p))
