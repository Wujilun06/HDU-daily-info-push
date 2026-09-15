# 每日信息整合推送

一个本地运行的「每日信息聚合器」：定时抓取指定网站的新文章与指定公众号的新推文，
自动分类，并对每篇文章生成简短摘要；点击文章可查看摘要并一键「前往原文」。

- **多端可用**：生成的是自包含网页，电脑/手机浏览器直接打开即可。
- **公众号多源可插拔**：支持 RSS 代理 / 搜狗抓取 / 手动导入 三种获取方式，按账号配置。
- **规则 + LLM 混合摘要**：有 API key 用大模型做摘要，没有则自动回退到免费离线摘要。
- **完全本地**：数据不出本机，可离线运行（demo 模式）。

## 目录结构

```
daily_digest/
├── config.yaml        # 主配置：信息源 / 分类规则 / LLM / 调度
├── main.py            # 主程序（--once 抓取一次 / --demo 离线样例）
├── scheduler.py       # 进程内定时循环（可选）
├── serve.py           # 本地静态服务器（供手机局域网访问）
├── fetcher.py         # 多源抓取（RSS / 公众号代理 / 搜狗 / 手动）
├── classifier.py      # 关键词规则分类
├── summarizer.py      # 摘要（LLM 可插拔 + 抽取式兜底）
├── content_extract.py # 正文/标题提取
├── generator.py       # 生成自包含 index.html
├── manual_links.txt   # 手动导入链接清单（每行一个 URL）
├── run.bat            # Windows 一键运行（供任务计划程序调用）
├── requirements.txt
└── output/index.html  # 每次运行生成的网页
```

## 1. 安装

```bash
cd daily_digest
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
pip install -r requirements.txt
```

> 本项目使用 Python 3.11+。若 `python` 指向系统旧版本，请改用 `python3`。

## 2. 配置（config.yaml）

### 2.1 监控网站（RSS 最稳）

```yaml
- id: "ruanyifeng"
  name: "阮一峰的网络日志"
  type: "website_rss"
  url: "https://www.ruanyifeng.com/blog/atom.xml"
  enabled: true
```

绝大多数博客/新闻站都提供 RSS（通常 `/feed`、`/atom.xml`、`/rss.xml`）。
找不到时可用 `https://www.rssbus.com/rss-generator/` 等工具生成。

### 2.2 监控公众号（任选一种）

**方式 A · RSS 代理（推荐，稳定）**
用 [WeRSS](https://werss.app) 等平台，粘贴公众号主页链接，拿到一个 feed 地址：
```yaml
- id: "wechat_via_rss"
  name: "某公众号"
  type: "wechat_rss"
  url: "https://werss.app/api/v1/你的FEED_ID/feed"
  enabled: true
```

**方式 B · 搜狗微信抓取（免费但脆弱，默认关闭）**
```yaml
- id: "wechat_sogou"
  name: "搜狗抓取"
  type: "wechat_sogou"
  account: "量子位"     # 公众号名称
  enabled: false
```
> 反爬严格，可能需要维护 cookie；生产环境不建议长期依赖。

**方式 C · 手动导入**
把文章链接逐行写进 `manual_links.txt`，配置：
```yaml
- id: "manual"
  name: "手动导入"
  type: "wechat_manual"
  list_file: "manual_links.txt"
  enabled: true
```

### 2.3 自动分类

在 `categories` 中按「关键词命中」配置，顺序靠前的优先匹配；`keywords` 为空的类作兜底：
```yaml
categories:
  - name: "技术"
    keywords: ["python", "ai", "机器学习", "开源"]
  - name: "财经"
    keywords: ["经济", "股票", "基金", "投资"]
  - name: "其他"
    keywords: []
```

### 2.4 大模型摘要（可选）

```yaml
llm:
  enabled: true
  base_url: "https://api.openai.com/v1"   # 任意 OpenAI 兼容端点
  api_key: "sk-..."
  model: "gpt-4o-mini"
```
不填 `api_key` 则自动使用**抽取式摘要**（取正文前几句），完全免费离线。

## 3. 运行

```bash
python main.py --demo     # 用内置样例离线跑通，生成 output/index.html
python main.py --once     # 按 config 真实抓取一次
python scheduler.py       # 进程内定时循环（按 run_times 触发）
```

## 4. 在手机上查看

**方式一 · 局域网（最简单）**
```bash
python serve.py 8080
```
电脑与手机连同一 WiFi，手机浏览器打开终端打印的 `http://电脑IP:8080`。

**方式二 · 内网穿透（不在同一网络也能看）**
用 frpc / ngrok 把 8080 端口映射出去：
```bash
ngrok http 8080        # 会得到公网地址，手机随时访问
```

**方式三 · 直接发文件**
`output/index.html` 是单文件，可直接通过微信/邮件/网盘发到手机打开。

## 5. 每天固定时间自动运行

### Windows · 任务计划程序
先创建 `run.bat`（已在目录内），然后以管理员身份执行一次：
```powershell
schtasks /create /tn "DailyDigest" `
  /tr "E:\个人项目\每日信息整合推送\daily_digest\run.bat" `
  /sc daily /st 08:00
```
（把路径换成你实际的目录；可再加一条 20:00 的任务。）

### macOS / Linux · cron
```cron
0 8,20 * * * cd /path/to/daily_digest && ./venv/bin/python main.py --once
```

### 或：直接用 scheduler.py
保留一个终端运行 `python scheduler.py`，它会在 `run_times` 设定的时刻自动运行。

## 6. 扩展建议

- **去重增强**：当前按链接去重，可再加「标题相似度」去重。
- **分类升级**：把 `classifier.py` 换成零样本分类模型（如 bge-m3 / 本地小模型）。
- **推送通知**：在 `main.py` 末尾加一段，把当日摘要通过 邮件/Server酱/企业微信 推送到手机。
- **增量更新**：把已处理链接写入 `seen.json`，下次只抓取新文章，避免重复摘要。

---

## 7. 已内置：杭电计算机学院官网

`config.yaml` 默认已配置计算机学院官网各板块（通知公告、学院新闻、本科教学、研究生教育、招生就业、党建思政、科研信息、学生工作），通过 `website_html` 源类型抓取列表页，并**按板块自动分类**（每个板块即一个分类）。列表页规律为 `https://cs.hdu.edu.cn/<栏目ID>/list.htm`。增删板块只需复制一个 `website_html` 源、改 `url` 与 `category`。

## 8. 手机安装：PWA 或 APK

- **PWA（零构建，推荐）**：`python serve.py 8080` 提供服务后，手机 Chrome 打开网页 → 菜单“添加到主屏幕”，即像 App 一样从桌面启动（生成时已带 `manifest.webmanifest`）。
- **APK（真·安装包）**：见 `android/` 下的 WebView 工程。App 只加载一个网址（你电脑生成的最新网页），所以**内容每日更新无需重新打包**。用 Android Studio 打开 `android/`，把 `strings.xml` 里的 `start_url` 改成 serve.py 的公网/局域网地址，Build APK 即可。

## 9. 接入公众号需要你提供什么

公众号没有公开 RSS，二选一即可接入：

1. **RSS 代理 feed 地址（稳定，推荐）**：在 [WeRSS](https://werss.app) 等平台用公众号主页生成 feed 地址，把地址给我（或填进 `config.yaml` 的 `wechat_rss` 源）。
2. **公众号名称（免费但脆弱）**：给我公众号名称，我用搜狗微信抓取（配置 `wechat_sogou`，反爬可能需维护 cookie）。

“很多公众号”的话，把清单（名称 + 是否愿意用 RSS 代理）发我，我一次性配好；也可以把文章链接逐行写进 `manual_links.txt` 做手动导入。
