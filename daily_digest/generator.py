"""生成自包含的静态网页 output/index.html（手机/电脑均可直接打开）。"""
import json
import os
from datetime import datetime


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>__TITLE__</title>
<link rel="manifest" href="manifest.webmanifest">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#2563eb">
<style>
  :root{
    --bg:#f5f6f8; --card:#ffffff; --ink:#1f2329; --sub:#6b7280;
    --line:#e5e7eb; --accent:#2563eb; --accent-soft:#eff4ff;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
    line-height:1.6;-webkit-text-size-adjust:100%}
  header{padding:16px 16px 10px;background:var(--card);border-bottom:1px solid var(--line);
    position:sticky;top:0;z-index:5}
  h1{margin:0;font-size:20px}
  .meta{margin:4px 0 10px;color:var(--sub);font-size:13px}
  .toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:8px}
  .toolbar input{border:1px solid var(--line);background:#fff;color:var(--ink);
    padding:8px 10px;border-radius:8px;font-size:13px;outline:none}
  .toolbar input[type=text]{flex:1;min-width:130px}
  .toolbar input[type=date]{flex:none}
  .lbl{color:var(--sub);font-size:13px}
  .filters{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px}
  .filters button{border:1px solid var(--line);background:#fff;color:var(--ink);
    padding:6px 14px;border-radius:999px;font-size:13px;white-space:nowrap;cursor:pointer}
  .filters button.active{background:var(--accent);color:#fff;border-color:var(--accent)}
  main{max-width:820px;margin:0 auto;padding:14px 12px 60px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;
    margin-bottom:12px;overflow:hidden;transition:box-shadow .15s}
  .card.open{box-shadow:0 6px 18px rgba(0,0,0,.08)}
  .chead{padding:12px 14px;cursor:pointer;display:flex;gap:10px;align-items:flex-start}
  .ctitle{flex:1;font-weight:600;font-size:15.5px}
  .badge{flex:none;font-size:12px;color:#fff;background:var(--accent);
    padding:2px 9px;border-radius:999px;margin-top:2px}
  .csub{display:flex;justify-content:space-between;gap:10px;color:var(--sub);
    font-size:12.5px;padding:0 14px 10px;margin-top:-4px}
  .csub .src{text-align:right;color:var(--accent);font-weight:600}
  .cdetail{max-height:0;overflow:hidden;transition:max-height .25s ease;padding:0 14px}
  .card.open .cdetail{max-height:200px;padding:0 14px 14px}
  .orig{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;
    padding:9px 18px;border-radius:9px;font-size:14px;font-weight:600}
  .orig:active{opacity:.85}
  .empty{text-align:center;color:var(--sub);padding:40px 0;font-size:14px}
  .empty button{margin-top:14px;border:1px solid var(--accent);background:#fff;color:var(--accent);
    padding:8px 18px;border-radius:8px;font-size:14px;cursor:pointer}
  footer{text-align:center;color:var(--sub);font-size:12px;padding:0 0 30px}
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <p class="meta">生成时间：__DATE__ ｜ 共 <span id="cnt">0</span> 篇（默认显示当天新增）</p>
  <div class="toolbar">
    <input type="text" id="q" placeholder="搜索标题关键字…">
    <span class="lbl">起始日期</span><input type="date" id="dstart" title="起始日期">
    <span class="lbl">截止日期</span><input type="date" id="dend" title="截止日期">
  </div>
  <div class="filters" id="filters"></div>
</header>
<main id="list"></main>
<footer>每日信息整合推送 · 本地生成</footer>
<script>
const DATA = __DATA__;
const CATS = __CATS__;
const list = document.getElementById('list');
const filters = document.getElementById('filters');
const qEl = document.getElementById('q');
const dsEl = document.getElementById('dstart');
const deEl = document.getElementById('dend');
let active = '全部';

function todayStr(){
  const t=new Date();
  return t.getFullYear()+'-'+String(t.getMonth()+1).padStart(2,'0')+'-'+String(t.getDate()).padStart(2,'0');
}
function badgeColor(cat){
  let h=0; for(const ch of cat) h=(h*31+ch.charCodeAt(0))%360;
  return 'hsl('+h+',65%,45%)';
}
function esc(s){return (s||'').replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));}
function addedOf(a){return (a.added||'').slice(0,10);}

function renderFilters(){
  const cats = ['全部', ...CATS];
  filters.innerHTML = cats.map(c=>
    '<button data-c="'+c+'" class="'+(c===active?'active':'')+'">'+esc(c)+'</button>').join('');
  filters.querySelectorAll('button').forEach(b=>{
    b.onclick=()=>{active=b.dataset.c;renderFilters();renderList();};
  });
}
function pass(a){
  if(active!=='全部' && a.category!==active) return false;
  const kw=qEl.value.trim();
  if(kw && !(a.title||'').toLowerCase().includes(kw.toLowerCase())) return false;
  const d=addedOf(a);
  if(dsEl.value && d && d < dsEl.value) return false;
  if(deEl.value && d && d > deEl.value) return false;
  return true;
}
function clearDates(){ dsEl.value=''; deEl.value=''; renderList(); }
function renderList(){
  const items = DATA.filter(pass);
  document.getElementById('cnt').textContent = DATA.length;
  if(!items.length){
    list.innerHTML='<div class="empty">没有匹配的文章'+
      (dsEl.value||deEl.value?'<br><button onclick="clearDates()">清除日期筛选，显示全部</button>':'')+
      '</div>';
    return;
  }
  list.innerHTML = items.map((a,i)=>{
    const color=badgeColor(a.category);
    return '<div class="card" data-i="'+i+'">'
      +'<div class="chead" onclick="toggle('+i+')">'
        +'<div class="ctitle">'+esc(a.title)+'</div>'
        +'<span class="badge" style="background:'+color+'">'+esc(a.category)+'</span>'
      +'</div>'
      +'<div class="csub"><span>'+(a.published?esc(a.published):'')+'</span>'
        +'<span class="src">'+esc(a.site||a.source)+'</span></div>'
      +'<div class="cdetail" id="d'+i+'">'
        +'<a class="orig" href="'+esc(a.link)+'" target="_blank" rel="noopener" onclick="event.stopPropagation()">前往原文 →</a>'
      +'</div>'
    +'</div>';
  }).join('');
}
function toggle(i){
  const card=document.querySelector('.card[data-i="'+i+'"]');
  if(card) card.classList.toggle('open');
}
qEl.addEventListener('input', renderList);
dsEl.addEventListener('change', renderList);
deEl.addEventListener('change', renderList);
// 默认：日期筛选设为今天，只显示当天新增（生成日）
const _t0=todayStr();
dsEl.value=_t0; deEl.value=_t0;
renderFilters();
renderList();
</script>
</body>
</html>
"""


def generate(articles, cfg, out_dir):
    settings = cfg.get("settings", {})
    cats = [c["name"] for c in cfg.get("categories", [])]
    cats = list(dict.fromkeys(cats))  # 去重且保序

    today = datetime.now().strftime("%Y-%m-%d")
    data = []
    for a in articles:
        data.append({
            "title": a.get("title", ""),
            "link": a.get("link", ""),
            "source": a.get("source", ""),
            "site": a.get("site", ""),  # 站点/公众号级来源（右下角展示）
            "category": a.get("category", "其他"),
            "published": a.get("published_str", ""),
            "added": today,  # 本次推送日，作为“当天新增”口径
            "summary": a.get("summary", ""),  # 保留字段，前端默认不渲染
        })

    html = (_TEMPLATE
            .replace("__TITLE__", settings.get("site_title", "每日信息整合"))
            .replace("__DATE__", datetime.now().strftime("%Y-%m-%d %H:%M"))
            .replace("__COUNT__", str(len(data)))
            .replace("__CATS__", json.dumps(cats, ensure_ascii=False))
            .replace("__DATA__",
                     json.dumps(data, ensure_ascii=False).replace("</", "<\\/")))

    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    # PWA manifest：让手机浏览器可“添加到主屏幕”当作 App 安装
    manifest = {
        "name": settings.get("site_title", "每日信息整合"),
        "short_name": "信息整合",
        "start_url": "index.html",
        "display": "standalone",
        "background_color": "#f5f6f8",
        "theme_color": "#2563eb",
        "description": "每日信息整合推送",
    }
    with open(os.path.join(out_dir, "manifest.webmanifest"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return out_path
