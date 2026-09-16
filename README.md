# HDU-daily-info-push（每日信息整合推送）

从指定网站与微信公众号定时抓取每日新文章、自动分类，并提供网页与安卓双端界面的信息整合推送项目。

> ⚠️ 本文档的「隐私与配置」部分为**重点**。本项目的完整使用文档（架构、部署、运行步骤等）仍在补充中。

---

## ⚠️ 隐私与配置说明（使用前必读）

本仓库**曾**包含部分隐私 / 敏感内容，已在提交历史中移除并强制推送清理。**以下内容不会出现在仓库中，也不会被自动同步**，请在使用前自行在本地补齐：

### 1. 已从仓库移除的隐私内容
- `daily_digest/wechat_weread_cookies.json`：微信读书登录态凭证（含 `wr_skey` 会话密钥）。**切勿提交到任何仓库。**
- `daily_digest/weread_login_qr.png` / `weread_login_page.png`：微信读书登录二维码与页面截图。
- `daily_digest/*.txt` 运行日志（含本机用户路径、微信 `vid` 等）：`login_log.txt`、`run_log*.txt`、`run_retry*.txt`、`pip_install_log.txt`、`pw_install_log.txt`、`retry_log.txt`、`manual_links.txt`。
- `.workbuddy/` 工作日志（含本机路径与账号信息）。
- `wechat_rss/we-mp-rss/docker-compose.yml`：含部署用的数据库 / 服务密码，**已在本地保留、未入库**。

### 2. 使用前需要自行补齐（不纳入版本控制）
- **大模型 API Key**：编辑 `daily_digest/config.yaml` 中的 `llm.api_key`，填入你自己的 Key（仓库内该字段为空）。
- **微信读书登录态**：运行 `daily_digest/cookie_helper.py` 或按项目方式导出你本人的 `wechat_weread_cookies.json` 放到 `daily_digest/` 下（**不要提交**）。
- **微信源配置**：将 `config.yaml` 中的 `mp_id` 列表替换为你自己要抓取的公众号（原提交中的部分 ID 属于个人订阅源）。
- **部署密钥（可选）**：若部署 `wechat_rss`，在本地 `docker-compose.yml` 中填写数据库密码等服务密钥，并确保该文件已被 `.gitignore` 忽略。

### 3. 安全建议（通用）
- 任何含 token、密码、Cookie、私钥的文件都加入 `.gitignore`，绝不要 `git add`。
- 推送前用 `git status` 确认无敏感文件被跟踪。
- 若曾把密钥误提交，立即作废对应凭证（如退出登录），并改写历史后强制推送。

---

## 待补充
- 项目架构、模块说明、部署与运行步骤等完整文档将陆续补充。
