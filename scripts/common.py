"""Shared helpers for the llm-internals-guide site scripts (stdlib only)."""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WORK = ROOT / "work"
DOCS = ROOT / "docs"
CONTENT = ROOT / "content"

TZ = dt.timezone(dt.timedelta(hours=8))  # Asia/Shanghai
UA = "Mozilla/5.0 (X11; Linux x86_64) llm-internals-guide-bot/1.0"

TYPES = {"official": "官方", "community": "第三方", "academic": "学术", "ai": "AI 生成"}
FORMATS = {"repo": "仓库", "course": "课程", "docs": "文档", "article": "文章",
           "paper": "论文", "video": "视频", "newsletter": "Newsletter", "book": "书"}
STATUSES = {"ok", "redirect", "broken", "archived", "stale"}


def today() -> str:
    return dt.datetime.now(TZ).date().isoformat()


def load(name: str, default=None):
    p = DATA / name
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save(name: str, obj) -> None:
    p = DATA / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def save_work(name: str, obj) -> Path:
    WORK.mkdir(exist_ok=True)
    p = WORK / name
    if isinstance(obj, str):
        p.write_text(obj, encoding="utf-8")
    else:
        p.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return p


def norm_url(url: str) -> str:
    """Normalise a URL for de-duplication."""
    u = urllib.parse.urlsplit(url.strip())
    host = u.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+$", "", u.path)
    if host == "github.com":
        parts = path.strip("/").split("/")
        path = "/" + "/".join(parts[:2]).lower() if len(parts) >= 2 else path.lower()
    q = urllib.parse.parse_qsl(u.query)
    q = [(k, v) for k, v in q if not k.startswith("utm_") and k not in {"ref", "source", "si"}]
    query = urllib.parse.urlencode(q)
    return f"{host}{path}" + (f"?{query}" if query else "")


def github_repo(url: str) -> str | None:
    m = re.match(r"https?://(?:www\.)?github\.com/([^/#?]+)/([^/#?]+)", url)
    if not m or m.group(1) in {"orgs", "topics", "search", "features", "sponsors"}:
        return None
    return f"{m.group(1)}/{m.group(2).removesuffix('.git')}"


def known_urls(resources: list[dict], reviewed: dict) -> set[str]:
    s = set(reviewed.keys())
    for r in resources:
        s.add(norm_url(r["url"]))
        for x in r.get("extra_links", []):
            s.add(norm_url(x["url"]))
        if r.get("github"):
            s.add(norm_url(f"https://github.com/{r['github']}"))
    return s


def http_get(url: str, timeout: int = 20, method: str = "GET") -> tuple[int, str, bytes]:
    """Return (status, final_url, body). status 0 means network error."""
    req = urllib.request.Request(url, method=method, headers={
        "User-Agent": UA, "Accept": "*/*", "Accept-Language": "en,zh-CN;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(3_000_000) if method == "GET" else b""
            return r.status, r.geturl(), body
    except urllib.error.HTTPError as e:
        return e.code, url, b""
    except Exception:  # noqa: BLE001
        return 0, url, b""


def gh_json(args: list[str]):
    """Run `gh` and parse JSON output. Raises on failure."""
    out = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or out.stdout.strip())
    return json.loads(out.stdout or "null")
