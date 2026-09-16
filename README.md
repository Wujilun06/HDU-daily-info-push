# HDU-daily-info-push（每日信息整合推送）

从指定网站与微信公众号定时抓取每日新文章、自动分类，并提供网页与安卓双端界面的信息整合推送项目。

> ⚠️ 本文档的「隐私与配置」部分为**重点**。本项目的完整使用文档（架构、部署、运行步骤等）仍在补充中。

---

## ⚠️ 隐私与配置说明（使用前必读）

本项目采用「**单一隐私文件**」约定：所有隐私内容（微信读书登录态、大模型 API Key）
都集中存放在仓库根目录的 **`private_config.json`** 中，**该文件已被 `.gitignore`
忽略，不会进入任何仓库、也不会被自动同步**。所有需要隐私的步骤都从这一份文件读取，
不再有零散的 cookie / key 文件。

### 1. 项目需要哪些隐私内容
- **微信读书登录态**（用于抓取微信公众号文章）：运行
  `python daily_digest/wechat_weread.py login` 用手机微信扫码，
  登录态会自动写入 `private_config.json` 的 `weread_cookies` 字段。
- **大模型 API Key**（可选，用于摘要）：把你的 Key 填进 `private_config.json`
  的 `llm_api_key` 字段。**不填则自动使用免费离线摘要**。

### 2. 如何准备 private_config.json
1. 复制模板：`cp private_config.example.json private_config.json`
2. （可选）在 `private_config.json` 填入 `llm_api_key`；
3. 运行 `python daily_digest/wechat_weread.py login` 完成微信读书扫码登录
   （自动写入 `weread_cookies`）。

> 没有 `private_config.json` 也能跑演示模式：`python daily_digest/main.py --demo`；
> 但真实抓取公众号需要其中存有微信读书登录态。

### 3. 安全建议（通用）
- `private_config.json` 已在 `.gitignore` 中，绝不要 `git add`。
- 推送前用 `git status` 确认无敏感文件被跟踪。
- 若曾把密钥误提交，立即作废对应凭证并改写历史后强制推送。

---

## 待补充
- 项目架构、模块说明、部署与运行步骤等完整文档将陆续补充。
