"""关键词规则分类：命中关键词「最多」的类别胜出；无命中则归入兜底类。"""


def _default_category(categories):
    for c in categories:
        if not c.get("keywords"):
            return c["name"]
    return "其他"


def classify(article, categories):
    """按标题+摘要命中关键词的数量打分，取最高分者；并列或零命中归兜底类。

    若抓取源已声明 category（如官网按板块直接定类），则直接采用，跳过关键词匹配。
    """
    if article.get("category"):
        return article["category"]
    text = (article.get("title", "") + " " + article.get("snippet", "")).lower()
    best, best_score = None, 0
    for cat in categories:
        kws = cat.get("keywords", [])
        if not kws:
            continue
        score = sum(1 for kw in kws if kw.lower() in text)
        if score > best_score:
            best, best_score = cat["name"], score
    return best if best else _default_category(categories)
