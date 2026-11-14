"""Check all resource URLs for liveness and refresh GitHub star counts.

Writes work/check-report.md. Use the report to decide what to fix in
data/resources.json before running build.py.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import sys
import time
from pathlib import Path

from common import DATA, WORK, gh_json, github_repo, http_get, load, save, today

MAX_WORKERS = 6
STALE_DAYS = 365


def check_url(r: dict) -> dict:
    code, final, _ = http_get(r["url"], method="HEAD")
    if code == 405:
        code, final, _ = http_get(r["url"])
    redirected = final.rstrip("/") != r["url"].rstrip("/") and code in (200, 301, 302)
    fail = code not in (200, 301, 302, 403, 405, 429)
    return {**r, "_code": code, "_final": final, "_redirected": redirected, "_fail": fail}


def refresh_github(r: dict) -> dict:
    repo = r.get("github") or github_repo(r["url"])
    if not repo:
        return r
    try:
        data = gh_json(["api", f"repos/{repo}",
                        "--jq", "{stars: .stargazers_count, pushed: .pushed_at}"])
        if data:
            r = {**r, "stars": data["stars"],
                 "pushed_at": data["pushed"][:10] if data.get("pushed") else r.get("pushed_at")}
    except RuntimeError:
        pass
    return r


def main() -> int:
    data = load("resources.json")
    if not data:
        print("resources.json 不存在", file=sys.stderr)
        return 1

    resources = [r for r in data["resources"] if r.get("status") != "removed"]
    print(f"检查 {len(resources)} 条资料…")

    # Refresh GitHub stats first
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        refreshed = list(ex.map(refresh_github, resources))

    # Check URLs
    with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        checked = list(ex.map(check_url, refreshed))

    t = today()
    broken, redirects, stale = [], [], []
    updated_resources = []

    for r in checked:
        new_r = {k: v for k, v in r.items() if not k.startswith("_")}
        new_r["last_checked"] = t

        if r["_fail"]:
            new_r["fail_count"] = r.get("fail_count", 0) + 1
            if new_r["fail_count"] >= 2:
                new_r["status"] = "broken"
                broken.append(r)
        else:
            new_r["fail_count"] = 0
            if r["_redirected"] and r["_code"] in (301, 302):
                redirects.append({**r, "new_url": r["_final"]})
                new_r["status"] = "redirect"
            elif new_r.get("status") in ("broken", "redirect"):
                new_r["status"] = "ok"

        pushed = new_r.get("pushed_at", "")
        if pushed and pushed < t[:4 + 1 + 2 + 1] + "01":  # rough year-ago check
            import datetime as dt
            try:
                age = (dt.date.fromisoformat(t) - dt.date.fromisoformat(pushed)).days
                if age > STALE_DAYS and not new_r.get("evergreen"):
                    new_r["status"] = "stale"
                    stale.append(new_r)
            except ValueError:
                pass

        updated_resources.append(new_r)

    data["resources"] = updated_resources
    save("resources.json", data)

    WORK.mkdir(exist_ok=True)
    lines = [f"# 健康检查报告 {t}\n"]
    lines.append(f"共检查 {len(resources)} 条。\n")
    if broken:
        lines.append(f"\n## 链接失效（{len(broken)} 条，连续 ≥2 次失败）\n")
        for r in broken:
            lines.append(f"- [{r['title']}]({r['url']}) HTTP {r['_code']}")
    if redirects:
        lines.append(f"\n## 重定向（{len(redirects)} 条）\n")
        for r in redirects:
            lines.append(f"- [{r['title']}]({r['url']}) → {r['new_url']}")
    if stale:
        lines.append(f"\n## 超过一年未更新（{len(stale)} 条）\n")
        for r in stale:
            lines.append(f"- [{r['title']}]({r['url']}) 最后推送：{r.get('pushed_at', '未知')}")
    if not broken and not redirects and not stale:
        lines.append("\n所有链接正常，无需处理。\n")

    report = Path(WORK / "check-report.md")
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"报告写入 work/check-report.md | 失效 {len(broken)} · 重定向 {len(redirects)} · 久未更新 {len(stale)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
