# HDU-daily-info-push（每日信息整合推送）

一个本地运行的「每日信息聚合器」：定时抓取**网站新文章**与**微信公众号新推文**，
自动分类、生成简短摘要，并产出可在电脑/手机浏览器直接打开的自包含网页（含「前往原文」按钮）。
同时提供安卓工程（WebView 壳），加载同一份网页，每日更新无需重新打包。

> 仓库：`https://github.com/Wujilun06/HDU-daily-info-push`
> 运行入口在 `daily_digest/` 子目录，详细的运行/部署手册见 `daily_digest/README.md`。

---

## 1. 简介

- **用途**：把分散在「杭电计算机学院官网各板块」与「多个微信公众号」的每日更新，
  集中成一份带分类、带摘要、带原文链接的信息页，方便快速浏览。
- **多端可用**：生成的是单个 `index.html`（自包含，CSS/JS 内联），电脑/手机浏览器直接打开，
  也可通过局域网/内网穿透供手机访问，或作为 PWA 添加到主屏幕。
- **公众号多源可插拔**：支持「微信读书通道 / RSS 代理 / 手动导入」三种获取方式，按账号配置。
- **规则 + LLM 混合摘要**：配置了 API Key 用大模型做摘要，没有则自动回退到免费离线抽取式摘要。
- **完全本地**：数据不出本机，可离线运行（demo 模式）。

---

## 2. 原理

### 2.1 用到的编程语言与第三方库

| 类别 | 内容 |
|------|------|
| 编程语言 | **Python 3.11+**（本项目未使用 3.13 的新特性，3.11 即可） |
| 核心依赖 | `requests`（抓取）、`pyyaml`（配置）、`beautifulsoup4`(bs4)（正文/列表解析）、`openai`（可选，摘要） |
| 浏览器兜底 | `playwright` + Chromium（当 urllib 抓取被微信读书风控时，用真实浏览器带登录态同源请求） |
| 第三方服务 | 微信读书（WeRead，用于获取公众号文章）、可选 WeRSS 等 RSS 代理平台 |

### 2.2 数据流与工作原理

```
信息源(config.yaml)
   │
   ├─ website_html  ──► fetcher 拉取官网列表页 HTML ──► 按板块分类
   ├─ weread        ──► wechat_weread.py 经微信读书接口/浏览器抓取公众号文章
   ├─ wechat_rss    ──► 解析云端 RSS 代理 feed（如 WeRSS）
   └─ wechat_manual ──► 读取 manual_links.txt 手动导入链接
        │
        ▼
   main.py：去重 → classifier 关键词分类 → summarizer 摘要（LLM 可插拔）
        │
        ▼
   generator.py：渲染自包含 output/index.html（含「前往原文」按钮）
        │
        ▼
   serve.py（局域网）/ scheduler.py（定时）/ 任务计划程序（每天 08:00、20:00）
```

- **公众号抓取为何走微信读书通道**：公众号没有公开 RSS。本项目用「微信读书」里对应公众号的
  `MP_WXS_xxxx` 标识作为 `mp_id`，经由微信读书的取数接口拿到「标题 + 原文链接 + 日期」。
  早期曾尝试「搜狗微信抓取」与「本地 docker 部署 we-mp-rss」，前者反爬脆弱、后者未被使用，
  均已弃用（docker 容器已删除，见第 5 节）。
- **风控告警规则**：微信读书接口偶发 `-2041`（请求频率/风控）、`-2014`（限频）、`-2003`（参数格式）。
  `-2041` 时自动退避并切换到 Playwright 浏览器同源请求兜底；批量模式只启动一次浏览器、
  账号间留足间隔（`account_interval`），显著降低限频概率。

---

## 3. 具体实现方式

### 3.1 目录结构

```
每日信息整合推送/
├── README.md                 # 本文件（项目总览 + 维护手册）
├── private_config.json       # 【隐私，gitignore】微信读书登录态 + LLM api_key
├── private_config.example.json  # 【入库模板】占位符，复制为 private_config.json 后填真实值
├── .gitignore                # 仅忽略 private_config.json（单一隐私文件约定）
├── daily_digest/             # 运行核心
│   ├── README.md             # 运行级详细手册（安装/配置/运行/手机查看）
│   ├── config.yaml           # 主配置：信息源 / 分类规则 / LLM / 调度
│   ├── main.py               # 主程序（--once 抓取一次 / --demo 离线样例）
│   ├── scheduler.py          # 进程内定时循环
│   ├── serve.py              # 本地静态服务器（局域网访问）
│   ├── fetcher.py            # 多源抓取分发（website_html / weread / wechat_rss / wechat_manual）
│   ├── classifier.py         # 关键词规则分类
│   ├── summarizer.py         # 摘要（LLM 可插拔 + 抽取式兜底）
│   ├── content_extract.py    # 正文/标题提取
│   ├── generator.py          # 渲染自包含 index.html
│   ├── wechat_weread.py      # 微信读书登录态管理 + 文章抓取（urllib + Playwright 兜底）
│   ├── private_config.py     # 单一隐私文件读写模块
│   ├── run.bat               # Windows 任务计划程序调用的一键运行脚本
│   ├── requirements.txt
│   ├── manual_links.txt      # 手动导入链接（每行一个 URL）
│   ├── tests/                # 测试与调试脚本
│   └── output/index.html     # 每次运行生成的网页
└── android/                  # WebView 壳工程（加载 serve.py 提供的网址）
```

### 3.2 关键模块与扩展点

- **`fetcher.py` 的 `DISPATCH` 表**：新增抓取类型，只需写一个 `fetch_xxx(source)` 函数并注册进
  `DISPATCH`，主流程即自动调用，无需改动 `main.py`。
- **`config.yaml` 的 `sources`**：每个源可单独 `enabled: true/false`。新增官网板块 = 复制一个
  `website_html` 源、改 `url` 与 `category`；新增公众号 = 加一个 `weread` 源填 `mp_id`。
- **`classifier.py`**：按「关键词命中」顺序匹配，靠前的优先；`keywords: []` 的类作兜底。
  换成零样本分类模型（如 bge-m3 / 本地小模型）只需替换该模块。
- **`summarizer.py`**：`summarize(article, llm_cfg)` 有 API Key 走 LLM，无则抽取式兜底。
  `api_key` 从 `private_config.json` 读取（见第 4 节），不在 `config.yaml` 留密钥。

### 3.3 运行（速览，详见 `daily_digest/README.md`）

```bash
cd daily_digest
python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt

# 准备隐私文件（见第 4 节）后：
python main.py --once      # 按 config 真实抓取一次
python main.py --demo      # 用内置样例离线跑通（无需隐私）
python serve.py 8080       # 局域网查看
```

---

## 4. 可能用到的隐私权限和私人内容

本项目采用「**单一隐私文件**」约定：所有隐私集中存放在仓库根目录的 **`private_config.json`**，
该文件已被 `.gitignore` 忽略，**绝不进入仓库、也不被自动同步**。所有需要隐私的步骤都从这一份文件读取，
不再有零散的 `*.cookies.json` / `.env` / 单独的 key 文件。

| 隐私内容 | 用途 | 如何获得 |
|----------|------|----------|
| **微信读书登录态**（`weread_cookies` / `weread_vid`） | 抓取微信公众号文章 | `python daily_digest/wechat_weread.py login`，手机微信扫码，自动写入 `private_config.json` |
| **大模型 API Key**（`llm_api_key`，可选） | 生成摘要 | 手动填入 `private_config.json`；留空则自动使用免费离线摘要 |

**准备步骤**：
1. `cp private_config.example.json private_config.json`
2. （可选）在 `private_config.json` 填 `llm_api_key`
3. `python daily_digest/wechat_weread.py login` 完成扫码登录

> 没有 `private_config.json` 也能跑演示：`python daily_digest/main.py --demo`；
> 但真实抓取公众号需要其中存有微信读书登录态。
> 微信读书登录态通常可维持数周，失效时重跑 `login` 即可。

**安全底线**：
- `private_config.json` 已在 `.gitignore`，绝不要 `git add`。
- 推送前用 `git status` 确认无敏感文件被跟踪；若曾误提交，立即作废对应凭证并改写历史后强制推送。

---

## 5. 项目部署 / 开发过程中遇到的问题及解决方案（真实记录）

以下均为完善本项目时**实际踩过的坑**，后续维护可直接对照排查。

1. **公众号抓取被微信读书风控（-2041 / -2014 / -2003）**
   - 现象：`urllib` 请求频繁返回 `-2041`（风控）或 `-2014`（限频）。
   - 解决：`wechat_weread.py` 在 `-2041` 时自动退避并切换到 **Playwright 浏览器同源请求**
     （带完整会话与官方指纹，服务端能正确识别 `mpId`）；批量抓取只启动一次浏览器、
     账号间留 `account_interval` 间隔，显著降低限频。
2. **隐私文件曾被误提交到 GitHub（高危）**
   - 现象：早期把 `wechat_weread_cookies.json`（含 `wr_skey` 会话密钥、`vid`）提交进了仓库历史。
   - 解决：用户先退出微信读书作废凭证 → 补 `.gitignore` → `git rm --cached -r .` + `git add -A`
     重新索引 → `git commit --amend` + `git push -f` 重写远端历史彻底抹除。
   - 后续收敛为「单一 `private_config.json` 约定」，所有隐私只在那一个被忽略的文件里。
3. **公众号无公开 RSS，早期方案不可行**
   - 现象：搜狗微信抓取反爬严格、本地 `we-mp-rss` docker 容器未被任何代码引用。
   - 解决：统一改用「微信读书通道（`MP_WXS_xxxx`）」；删除未使用的
     `wechat_rss/we-mp-rss/docker-compose.yml` 与空目录；保留云端 RSS 代理（`wechat_rss` 源类型）
     作为可选补充。
4. **Git 推送时 SSH 无法解析域名**
   - 现象：Git Bash（MSYS）自带 `ssh` 因缺少 `resolv.conf` 无法解析 `github.com`。
   - 解决：用 Windows 自带 OpenSSH 推送：`git config --global core.sshCommand "C:/Windows/System32/OpenSSH/ssh.exe"`；
     本机统一走 `C:\Windows\System32\OpenSSH\ssh.exe -o StrictHostKeyChecking=accept-new`。
5. **含中文的 PowerShell 脚本解析失败**
   - 现象：`.ps1` 在 Windows PowerShell 5.1 下因无 BOM 按 GBK 解码中文 → `ParserError` / 字符串缺少终止符。
   - 解决：含中文的 `.ps1` 必须保存为 **UTF-8 带 BOM**；本工具 Write 默认产出无 BOM，需用
     `[System.IO.File]::WriteAllText($p,$c,(New-Object System.Text.UTF8Encoding -ArgumentList @($true)))` 补 BOM。
6. **Playwright 首次运行缺浏览器**
   - 现象：`ModuleNotFoundError` 或运行时报找不到 Chromium。
   - 解决：`pip install playwright && playwright install chromium`。
7. **遗留 legacy 隐私路径与「单一文件」原则冲突**
   - 现象：`cookie_helper.py` / `wechat_lite.py` / `tests/test_wechat_integration.py` 引用独立的
     `wechat_cookies.json`，与「全部隐私只在 private_config.json」冲突且不被调用。
   - 解决：已整体删除，仅保留活跃路径。

---

## 6. 致谢

- **微信读书（WeRead）**：提供公众号文章的取数通道（`MP_WXS_xxxx` 标识机制）。
- **WeRSS**（`https://werss.app`）：可选的公众号 RSS 代理平台，作为 `wechat_rss` 源的 feed 来源。
- **Playwright**：提供浏览器同源抓取兜底，解决微信读书风控问题。
- 项目架构参考了「本地信息聚合 + 自包含网页 + 多端查看」的常见实践。

---

## 附：后续开发与维护要点

- **新增信息源**：只改 `config.yaml`（不直接改代码）。官网板块复制 `website_html` 源；
  公众号加 `weread` 源并填 `mp_id`（从微信读书分享链接提取 `MP_WXS_xxxx`）。
- **扩展抓取类型**：在 `fetcher.py` 写 `fetch_xxx` 并注册进 `DISPATCH`。
- **摘要升级**：替换 `summarizer.py`，或接入更强的 LLM（改 `private_config.json` 的 `llm_api_key`
  与 `config.yaml` 的 `llm.base_url`/`llm.model`）。
- **增量更新**：当前按「本次抓取到的全部文章 + 生成日」展示；若需只显示相对上次真正新增，
  可在 `main.py` 恢复 `seen.json` 增量逻辑（代码注释已标注位置）。
- **隐私约定不可破坏**：任何新增隐私内容必须进 `private_config.json` 且 `.gitignore` 忽略；
  提交前用 `git status` 确认无敏感文件被跟踪。
