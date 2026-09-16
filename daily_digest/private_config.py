"""统一读取项目根目录的 private_config.json（本地隐私文件，不入库）。

设计约定（见仓库根 README「隐私与配置」）：
  - 本项目**所有**需要使用隐私内容的步骤都从这里读取，不再各自维护独立
    的 cookie / key 文件。
  - private_config.json 已被 .gitignore 忽略，**绝不会进入版本控制**。
  - 提交模板为 private_config.example.json（含占位符，可入库）。

当前约定的隐私字段：
  - llm_api_key       : 大模型摘要用的 API Key（空则走抽取式兜底）
  - weread_cookies    : 微信读书登录态 cookie 列表（list[dict]）
  - weread_vid        : 微信读书 vid（冗余备份，便于排查）
  - weread_saved_at   : 登录态保存时间
  - weread_cookie_raw : cookie 的 raw 字符串备份（部分接口需要）
"""
import json
import os

# daily_digest/ -> 项目根目录（private_config.json 放在根目录）
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIVATE_CONFIG_PATH = os.path.join(_ROOT, "private_config.json")
PRIVATE_CONFIG_EXAMPLE = os.path.join(_ROOT, "private_config.example.json")


def exists():
    """private_config.json 是否已存在（本地）。"""
    return os.path.exists(PRIVATE_CONFIG_PATH)


def load_private_config():
    """读取 private_config.json，返回 dict；缺失或损坏时返回 {}。"""
    if not exists():
        return {}
    try:
        with open(PRIVATE_CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_private_config(data):
    """整体写回 private_config.json（调用方负责合并自有字段，避免互相覆盖）。"""
    with open(PRIVATE_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_llm_api_key():
    return load_private_config().get("llm_api_key", "") or ""


def get_weread_cookies():
    return load_private_config().get("weread_cookies") or []


def get_weread_vid():
    return load_private_config().get("weread_vid", "") or ""
