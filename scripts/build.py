"""Build the static site into docs/ from data/*.json and content/.

Pages: index.html (guide + resource table), changelog.html, feed.xml (RSS of
the changelog), resources.json (machine-readable copy).
Validates data first and exits non-zero on any problem.
"""
from __future__ import annotations

import html
import json
import shutil
import sys
from email.utils import format_datetime
import datetime as dt

from common import CONTENT, DOCS, FORMATS, STATUSES, TYPES, TZ, load, norm_url, today

SITE_URL = "https://hustlyt.github.io/llm-internals-guide/"
REPO_URL = "https://github.com/hustlyt/llm-internals-guide"
TITLE = "深入学习大语言模型原理"

e = html.escape


# ---------- validation ----------

def validate(data: dict, log: list) -> list[str]:
    errs = []
    cats = {c["id"] for c in data["categories"]}
    ids, urls = set(), {}
    req = ["id", "title", "url", "category", "type", "format", "lang", "desc", "added"]
    for r in data["resources"]:
        rid = r.get("id", "?")
        for k in req:
            if not r.get(k):
                errs.append(f"{rid}: 缺少字段 {k}")
        if rid in ids:
            errs.append(f"{rid}: id 重复")
        ids.add(rid)
        if r.get("category") not in cats:
            errs.append(f"{rid}: 未知分类 {r.get('category')}")
        if r.get("type") not in TYPES:
            errs.append(f"{rid}: 未知类型 {r.get('type')}")
        if r.get("format") not in FORMATS:
            errs.append(f"{rid}: 未知形式 {r.get('format')}")
        if r.get("status", "ok") not in STATUSES:
            errs.append(f"{rid}: 未知状态 {r.get('status')}")
        if not str(r.get("url", "")).startswith("https://"):
            errs.append(f"{rid}: URL 必须是 https")
        k = norm_url(r.get("url", ""))
        if k in urls:
            errs.append(f"{rid}: URL 与 {urls[k]} 重复")
        urls[k] = rid
    for entry in log:
        for k in ("date", "summary"):
            if not entry.get(k):
                errs.append(f"changelog {entry.get('date')}: 缺少 {k}")
        for rid in entry.get("added", []):
            if rid not in ids:
                errs.append(f"changelog {entry['date']}: added 里的 {rid} 不在资料库中")
    return errs


# ---------- rendering ----------

def md_links(text: str) -> str:
    """Escape text, then turn [label](https://url) into links."""
    import re
    return re.sub(r"\[([^\]]+)\]\((https://[^)\s]+)\)",
                  lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', e(text))


def stars(n) -> str:
    if n is None:
        return "—"
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def badge(r: dict) -> str:
    parts = []
    if r.get("pick"):
        parts.append('<span class="badge pick">推荐</span>')
    if r.get("status") in ("broken", "redirect", "stale"):
        label = {"broken": "链接失效", "redirect": "已迁移", "stale": "久未更新"}[r["status"]]
        parts.append(f'<span class="badge warn">{label}</span>')
    return "".join(parts)


def resource_table(data: dict, new_ids: set) -> str:
    cats = data["categories"]
    rows = []
    for c in cats:
        items = [r for r in data["resources"]
                 if r["category"] == c["id"] and r.get("status") != "removed"]
        if not items:
            continue
        items.sort(key=lambda r: (not r.get("pick"), -(r.get("stars") or 0)))
        rows.append(f'<tr class="cat" data-c="{c["id"]}"><td colspan="5">{e(c["name"])}'
                    f'<span class="cnt">{len(items)}</span></td></tr>')
        for r in items:
            extra = "".join(f' · <a href="{e(x["url"])}">{e(x["label"])}</a>' for x in r.get("extra_links", []))
            isnew = r["id"] in new_ids
            new = ' <span class="badge new">新</span>' if isnew else ""
            tcls = {"official": "t-off", "ai": "t-ai"}.get(r["type"], "")
            note = f'<div class="note-sm">{e(r["note"])}</div>' if r.get("note") else ""
            search = " ".join([r["title"], r["desc"], r.get("note", ""), r.get("github") or "",
                               r["lang"], TYPES[r["type"]], FORMATS[r["format"]]]).lower()
            rows.append(
                f'<tr data-t="{r["type"]}" data-f="{r["format"]}" data-zh="{int("中文" in r["lang"])}" '
                f'data-new="{int(isnew)}" data-c="{c["id"]}" data-s="{e(search)}">'
                f'<td><a href="{e(r["url"])}">{e(r["title"])}</a>{badge(r)}{new}{extra}{note}</td>'
                f'<td class="{tcls}">{TYPES[r["type"]]}<span class="fmt">{FORMATS[r["format"]]}</span></td>'
                f'<td class="hide-sm">{e(r["lang"])}</td>'
                f'<td class="n">{stars(r.get("stars"))}</td>'
                f'<td>{md_links(r["desc"])}</td></tr>')
    total = sum(1 for r in data["resources"] if r.get("status") != "removed")
    chips = "".join(f'<button data-k="c:{c["id"]}">{e(c["name"])}</button>' for c in cats
                    if any(r["category"] == c["id"] for r in data["resources"]))
    return f'''<header class="pagehead"><h1>资料库</h1>
<p class="lead">{total} 条教程、课程、文档、文章、论文与视频，每周自动检索并经质量审核后更新。支持搜索标题、说明、仓库名，可叠加筛选。</p></header>
<div class="toolbar">
  <input id="q" type="search" placeholder="搜索，例如：kv cache、量化、中文、LoRA…" aria-label="搜索资料" autofocus>
  <div class="filters" id="filters" data-group="main">
    <button class="on" data-k="all">全部</button>
    <button data-k="t:official">官方</button><button data-k="t:community">第三方</button>
    <button data-k="t:academic">学术</button><button data-k="t:ai">AI 生成</button>
    <button data-k="f:article">文章</button><button data-k="f:video">视频</button>
    <button data-k="f:paper">论文</button><button data-k="f:course">课程</button>
    <button data-k="zh">只看中文</button><button data-k="new">最近新增</button>
  </div>
  <details class="catbox"><summary>按分类</summary><div class="filters" id="catfilters">{chips}</div></details>
  <p class="note" id="count" aria-live="polite"></p>
</div>
<div class="tblwrap"><table class="tbl" id="reftbl">
<thead><tr><th>资料</th><th>类型</th><th class="hide-sm">语言</th><th>★</th><th>说明</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody></table></div>
<p id="empty" class="empty" hidden>没有匹配的资料。换个关键词，或取消筛选。</p>
<p class="note">★ 为 GitHub Star 数，每周自动刷新，仅代表热度。</p>'''


def changelog_html(log: list, by_id: dict) -> str:
    parts = []
    for entry in log:
        def li(ids, cls):
            out = []
            for x in ids:
                if isinstance(x, dict):
                    out.append(f'<li class="{cls}">{e(x.get("title", x.get("id", "")))}'
                               f'{" — " + e(x["reason"]) if x.get("reason") else ""}</li>')
                elif x in by_id:
                    r = by_id[x]
                    out.append(f'<li class="{cls}"><a href="{e(r["url"])}">{e(r["title"])}</a> — {md_links(r["desc"])}</li>')
            return "".join(out)
        stats = entry.get("stats", {})
        stat_txt = " · ".join(f"{k} {v}" for k, v in stats.items())
        body = ""
        if entry.get("added"):
            body += f'<h4>新增 {len(entry["added"])}</h4><ul>{li(entry["added"], "add")}</ul>'
        if entry.get("changed"):
            body += f'<h4>调整 {len(entry["changed"])}</h4><ul>{li(entry["changed"], "chg")}</ul>'
        if entry.get("removed"):
            body += f'<h4>移除 {len(entry["removed"])}</h4><ul>{li(entry["removed"], "del")}</ul>'
        if entry.get("guide_changes"):
            body += "<h4>教程正文</h4><ul>" + "".join(f"<li>{e(x)}</li>" for x in entry["guide_changes"]) + "</ul>"
        parts.append(f'''<article class="log" id="v{e(entry["date"])}">
<header><time>{e(entry["date"])}</time><h3>{e(entry["summary"])}</h3>
{f'<p class="note">{e(stat_txt)}</p>' if stat_txt else ""}</header>
{body}</article>''')
    return "\n".join(parts) or "<p>暂无记录。</p>"


NAV = [("home", "index.html", "首页"), ("path", "path.html", "学习路线"), ("refs", "resources.html", "资料库"),
       ("tools", "tools.html", "工具"), ("capstone", "capstone.html", "毕业项目"),
       ("tips", "tips.html", "学习建议"), ("changelog", "changelog.html", "更新日志")]

SEARCH_JS = r"""
(function(){
  const q=document.getElementById('q'); if(!q) return;
  const rows=[...document.querySelectorAll('#reftbl tbody tr')];
  const items=rows.filter(r=>!r.classList.contains('cat'));
  const cnt=document.getElementById('count'), empty=document.getElementById('empty');
  let key='all', cat='';
  function ok(r){
    if(cat && r.dataset.c!==cat) return false;
    if(key==='all') return true;
    if(key==='zh') return r.dataset.zh==='1';
    if(key==='new') return r.dataset.new==='1';
    const [k,v]=key.split(':'); return r.dataset[k]===v;
  }
  function apply(){
    const words=q.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    let n=0;
    items.forEach(r=>{
      const show=ok(r)&&words.every(w=>r.dataset.s.includes(w));
      r.style.display=show?'':'none'; if(show) n++;
    });
    rows.forEach((r,i)=>{ if(!r.classList.contains('cat')) return; let j=i+1,any=false;
      while(j<rows.length&&!rows[j].classList.contains('cat')){ if(rows[j].style.display!=='none') any=true; j++; }
      r.style.display=any?'':'none';
      const k=r.querySelector('.cnt'); if(k){ let m=0; for(let t=i+1;t<rows.length&&!rows[t].classList.contains('cat');t++) if(rows[t].style.display!=='none') m++; k.textContent=m; } });
    cnt.textContent='显示 '+n+' / '+items.length+' 条';
    empty.hidden=n>0;
    const u=new URL(location); q.value?u.searchParams.set('q',q.value):u.searchParams.delete('q');
    history.replaceState(null,'',u);
  }
  document.querySelectorAll('#filters button').forEach(b=>b.addEventListener('click',()=>{
    document.querySelectorAll('#filters button').forEach(x=>x.classList.remove('on'));
    b.classList.add('on'); key=b.dataset.k; apply(); }));
  const cb=[...document.querySelectorAll('#catfilters button')];
  cb.forEach(b=>b.addEventListener('click',()=>{
    const on=b.classList.contains('on'); cb.forEach(x=>x.classList.remove('on'));
    cat=on?'':b.dataset.k.slice(2); if(!on) b.classList.add('on'); apply(); }));
  q.addEventListener('input',apply);
  document.addEventListener('keydown',ev=>{ if(ev.key==='/'&&document.activeElement!==q){ev.preventDefault();q.focus();} });
  const init=new URL(location).searchParams.get('q'); if(init) q.value=init;
  apply();
})();
"""


def page(title: str, body: str, active: str, updated: str, desc: str = "") -> str:
    css = (CONTENT / "style.css").read_text(encoding="utf-8")
    nav = "".join(f'<a href="{href}"{" class=on" if key == active else ""}>{label}</a>'
                  for key, href, label in NAV)
    desc = desc or "深入学习大语言模型原理：Transformer 架构、KV Cache、预训练、对齐微调、推理优化，附持续更新的精选资料库。"
    script = f"<script>{SEARCH_JS}</script>" if active == "refs" else ""
    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="alternate" type="application/rss+xml" title="{e(TITLE)} 更新日志" href="feed.xml">
<style>{css}</style></head>
<body><div class="topbar"><div class="wrap-top"><a class="brand" href="index.html">LLM 原理指南</a>
<nav>{nav}</nav></div></div>
<div class="wrap">
{body}
<footer>最近更新：{e(updated)} · 每周一自动检索新资料、核对链接、审核后发布 ·
<a href="changelog.html">更新日志</a> · <a href="feed.xml">RSS</a> · <a href="{REPO_URL}">源码与数据</a></footer>
</div>
{script}</body></html>
'''


def feed_xml(log: list, by_id: dict) -> str:
    items = []
    for entry in log[:30]:
        d = dt.datetime.fromisoformat(entry["date"]).replace(hour=9, tzinfo=TZ)
        added = "".join(f"<li><a href='{by_id[x]['url']}'>{e(by_id[x]['title'])}</a> — {e(by_id[x]['desc'])}</li>"
                        for x in entry.get("added", []) if isinstance(x, str) and x in by_id)
        desc = f"<p>{e(entry['summary'])}</p>" + (f"<ul>{added}</ul>" if added else "")
        items.append(f"""<item><title>{e(entry['date'] + ' ' + entry['summary'])}</title>
<link>{SITE_URL}changelog.html#v{entry['date']}</link><guid>{SITE_URL}changelog.html#v{entry['date']}</guid>
<pubDate>{format_datetime(d)}</pubDate><description>{e(desc)}</description></item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>{e(TITLE)} · 更新日志</title><link>{SITE_URL}</link>
<description>每周新增的 LLM 原理教程、文档与文章</description><language>zh-CN</language>
{''.join(items)}
</channel></rss>
"""


def main() -> int:
    data = load("resources.json")
    log = load("changelog.json", [])
    log.sort(key=lambda x: x["date"], reverse=True)
    errs = validate(data, log)
    if errs:
        print("数据校验失败：\n" + "\n".join(f"  - {x}" for x in errs), file=sys.stderr)
        return 1
    by_id = {r["id"]: r for r in data["resources"]}
    updated = log[0]["date"] if log else today()
    new_ids = {x for entry in log[:2] if not entry.get("initial") for x in entry.get("added", []) if isinstance(x, str)}

    phases = json.loads((CONTENT / "phases.json").read_text(encoding="utf-8"))
    rd = lambda n: (CONTENT / n).read_text(encoding="utf-8")  # noqa: E731

    def phase_cards(detail: bool) -> str:
        out = []
        for p in phases:
            extra = (f'<p class="goal">产出：{p["goal"]}</p>' if detail else "")
            out.append(f'<a class="pcard" href="phase-{p["id"]}.html"><span class="pno">{p["label"]}'
                       f'<small>{p["weeks"]}</small></span><span><b>{e(p["title"])}</b>'
                       f'<span class="ps">{e(p["summary"])}</span>{extra}</span></a>')
        return '<div class="pgrid">' + "".join(out) + "</div>"

    def write(name: str, title: str, body: str, active: str, desc: str = "") -> None:
        (DOCS / name).write_text(page(title, body, active, updated, desc), encoding="utf-8")

    latest = ""
    if log:
        l0 = log[0]
        latest = (f'<p class="latest">最近一次更新 <a href="changelog.html#v{e(l0["date"])}">{e(l0["date"])}</a>：'
                  f'{e(l0["summary"])}</p>')
    header = rd("header.html").replace("<!-- LATEST -->", latest)

    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir()
    total = sum(1 for r in data["resources"] if r.get("status") != "removed")
    home = (header + rd("home.html")
            + '<section id="roadmap"><h2>学习路线一览 <small>7 个阶段，点进去看每周要读什么、做什么</small></h2>'
            + phase_cards(False) + '<p><a href="path.html">查看完整路线 →</a></p></section>'
            + f'<section class="cta"><h2>资料库</h2><p>{total} 条精选教程、文章、论文与视频，支持搜索与筛选。'
              '<a href="resources.html">打开资料库 →</a></p></section>')
    write("index.html", f"{TITLE}：Transformer · KV Cache · 微调 · 推理优化", home, "home")

    path_body = ('<header class="pagehead"><h1>10 周学习路线</h1><p class="lead">每周约 8–10 小时；'
                 '有 Python 基础和微积分/线代基础可压缩到 7 周。每个阶段给出要读的材料和学完后应该做出的东西。'
                 '按顺序走，不要囤教程。每个阶段先做完"必做"，"选读"按需挑。P0–P2（约 4 周）学完即算入门，'
                 'P3–P5 是进阶，P6 选修。</p></header>' + phase_cards(True)
                 + '<p class="note">想找某个主题的更多材料，去<a href="resources.html">资料库</a>搜索。</p>')
    write("path.html", f"学习路线 · {TITLE}", path_body, "path")

    for i, p in enumerate(phases):
        prev_ = phases[i - 1] if i else None
        next_ = phases[i + 1] if i + 1 < len(phases) else None
        side = "".join(f'<a href="phase-{q["id"]}.html"{" class=on" if q is p else ""}>'
                       f'<b>{q["label"]}</b> {e(q["title"])}</a>' for q in phases)
        pn = ('<nav class="pn">'
              + (f'<a href="phase-{prev_["id"]}.html">← {prev_["label"]} {e(prev_["title"])}</a>' if prev_
                 else '<a href="path.html">← 路线总览</a>')
              + (f'<a href="phase-{next_["id"]}.html">{next_["label"]} {e(next_["title"])} →</a>' if next_
                 else '<a href="capstone.html">毕业项目 →</a>') + '</nav>')
        body = (f'<div class="layout"><aside class="side"><a class="back" href="path.html">学习路线</a>{side}</aside>'
                f'<article class="phasepage"><p class="crumb">{p["label"]} · {p["weeks"]}</p>'
                f'<h1>{e(p["title"])}</h1><p class="lead">{e(p["summary"])}</p>'
                f'<h2>要读什么</h2>{rd(f"phases/{p["id"]}.html")}'
                f'<div class="goal big">✔ 学完应做出：{p["goal"]}</div>{pn}</article></div>')
        write(f"phase-{p['id']}.html", f"{p['label']} {p['title']} · {TITLE}", body, "path", p["summary"])

    write("resources.html", f"资料库 · {TITLE}", resource_table(data, new_ids), "refs",
          f"{total} 条 LLM 教程、文档、文章、论文与视频，可搜索与筛选。")
    write("capstone.html", f"毕业项目 · {TITLE}",
          '<header class="pagehead"><h1>毕业项目建议</h1><p class="lead">选一个，把前面所有阶段串起来。</p></header>'
          + rd("capstone.html"), "capstone")
    write("tips.html", f"学习建议 · {TITLE}",
          '<header class="pagehead"><h1>学习建议</h1></header>' + rd("tips.html"), "tips")
    write("tools.html", f"工具 · {TITLE}",
          '<header class="pagehead"><h1>辅助工具</h1>'
          '<p class="lead">交互式可视化、沙箱环境与调试工具，帮助建立直觉、验证理解。</p></header>'
          + rd("tools.html"), "tools",
          "辅助学习大语言模型原理的交互式工具：Transformer 可视化、Tokenizer 沙箱、Attention 调试器。")
    log_body = (f'<header class="pagehead"><h1>更新日志</h1><p class="lead">每周一自动检索 GitHub、官方博客、技术社区、arXiv，'
                f'经质量审核后收录。也可以 <a href="feed.xml">订阅 RSS</a>。</p></header>'
                + changelog_html(log, by_id))
    write("changelog.html", f"更新日志 · {TITLE}", log_body, "changelog")
    (DOCS / "feed.xml").write_text(feed_xml(log, by_id), encoding="utf-8")
    pub = [{k: v for k, v in r.items() if k not in ("fail_count",)} for r in data["resources"]]
    (DOCS / "resources.json").write_text(json.dumps({"updated": updated, "categories": data["categories"],
                                                     "resources": pub}, ensure_ascii=False, indent=1), encoding="utf-8")
    (DOCS / ".nojekyll").write_text("")
    print(f"built docs/: {len(data['resources'])} resources, {len(log)} changelog entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
