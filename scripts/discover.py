"""Collect candidate resources from GitHub, RSS feeds, HN, Reddit, arXiv.

Writes work/candidates.json (new, never-seen URLs only) and
work/candidates.md (human-readable digest). Nothing is added to the site
here — the reviewing agent decides, using the rubric in UPDATE_PLAYBOOK.md.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from common import TZ, gh_json, github_repo, http_get, known_urls, load, norm_url, save_work, today

ATOM = "{http://www.w3.org/2005/Atom}"


def strip_tags(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def parse_date(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    try:
        return parsedate_to_datetime(s).date().isoformat()
    except (TypeError, ValueError):
        pass
    m = re.match(r"\d{4}-\d{2}-\d{2}", s)
    return m.group(0) if m else None


def matches(text: str, kws: list[str]) -> bool:
    t = text.lower()
    return any(re.search(r"(?<![a-z])" + re.escape(k.lower()) + r"(?![a-z])", t) for k in kws)


def from_github(cfg: dict, since: str) -> list[dict]:
    out = []
    for q in cfg["queries"]:
        for flag in ("--created", "--updated"):
            time.sleep(2.2)
            try:
                items = gh_json(["search", "repos", q, flag, f">={since}",
                                 "--stars", f">={cfg['min_stars']}", "--sort", "stars", "--limit", "15",
                                 "--json", "fullName,stargazersCount,description,createdAt,pushedAt,url"])
            except RuntimeError as ex:
                print(f"[github] {q}: {ex}", file=sys.stderr)
                continue
            for it in items or []:
                if it["stargazersCount"] < cfg["min_stars"]:
                    continue
                out.append({"url": it["url"], "title": it["fullName"], "source": f"GitHub 搜索：{q}",
                            "date": it["createdAt"][:10], "snippet": it.get("description") or "",
                            "stars": it["stargazersCount"], "pushed_at": it["pushedAt"][:10],
                            "new_repo": it["createdAt"][:10] >= since, "type_hint": "community"})
    return out


def from_feed(feed: dict, kws: list[str], since: str) -> list[dict]:
    code, _, body = http_get(feed["url"])
    if code != 200 or not body:
        print(f"[feed] {feed['name']}: HTTP {code}", file=sys.stderr)
        return []
    try:
        root = ET.fromstring(body)
    except ET.ParseError as ex:
        print(f"[feed] {feed['name']}: {ex}", file=sys.stderr)
        return []
    out = []
    items = root.iter("item") if root.find(".//item") is not None else root.iter(f"{ATOM}entry")
    for it in items:
        if it.tag == "item":
            title = it.findtext("title") or ""
            link = (it.findtext("link") or "").strip()
            date = parse_date(it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date"))
            summ = it.findtext("description") or ""
        else:
            title = it.findtext(f"{ATOM}title") or ""
            link_el = it.find(f"{ATOM}link[@rel='alternate']")
            if link_el is None:
                link_el = it.find(f"{ATOM}link")
            link = link_el.get("href") if link_el is not None else ""
            date = parse_date(it.findtext(f"{ATOM}published") or it.findtext(f"{ATOM}updated"))
            summ = it.findtext(f"{ATOM}summary") or it.findtext(f"{ATOM}content") or ""
        title, summ = strip_tags(title), strip_tags(summ)[:400]
        if not link or (date and date < since):
            continue
        if matches(title + " " + summ, kws):
            out.append({"url": link, "title": title, "source": feed["name"],
                        "date": date or today(), "snippet": summ,
                        "type_hint": feed.get("type", "community")})
    return out


def main() -> int:
    cfg = load("sources.json")
    if not cfg:
        print("sources.json 不存在", file=sys.stderr)
        return 1
    data = load("resources.json", {"categories": [], "resources": []})
    reviewed = load("reviewed.json", {})
    seen = known_urls(data["resources"], reviewed)
    kws = cfg.get("keywords", [])
    since = (dt.date.today() - dt.timedelta(days=cfg.get("lookback_days", 21))).isoformat()

    candidates: list[dict] = []

    print("搜索 GitHub…")
    gh_items = from_github(cfg.get("github", {}), since)
    candidates.extend(gh_items)

    print("读取 RSS 源…")
    for feed in cfg.get("feeds", []):
        items = from_feed(feed, kws, since)
        candidates.extend(items)
        print(f"  {feed['name']}: {len(items)} 条")

    # Deduplicate
    seen_now: set[str] = set()
    fresh = []
    for c in candidates:
        nurl = norm_url(c["url"])
        if nurl in seen or nurl in seen_now:
            continue
        seen_now.add(nurl)
        fresh.append(c)

    fresh.sort(key=lambda x: (-x.get("stars", 0), x.get("date", "")), reverse=False)

    save_work("candidates.json", fresh)

    lines = [f"# 候选资料 {today()}  ({len(fresh)} 条新 URL)\n",
             f"Since: {since} · 总候选 {len(candidates)}，去重后 {len(fresh)}\n"]
    for c in fresh:
        st = f" ★{c['stars']}" if c.get("stars") else ""
        lines.append(f"\n---\n**{c['title']}**{st}  \n{c['url']}  \n{c['snippet'][:200]}  \n来源：{c['source']} · {c['date']}")
    save_work("candidates.md", "\n".join(lines))
    print(f"写入 work/candidates.json ({len(fresh)} 条) 和 work/candidates.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
