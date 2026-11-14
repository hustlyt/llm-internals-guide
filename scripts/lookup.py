"""Look up whether a URL is already in the resource library or reviewed log.

Usage: python3 scripts/lookup.py <url>
"""
from __future__ import annotations

import sys
from common import github_repo, gh_json, load, norm_url


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python3 scripts/lookup.py <url>")
        return 1
    url = sys.argv[1].strip()
    nurl = norm_url(url)
    data = load("resources.json", {"categories": [], "resources": []})
    reviewed = load("reviewed.json", {})

    # Check resources
    for r in data["resources"]:
        rn = norm_url(r["url"])
        if rn == nurl:
            print(f"✓ 已收录: {r['id']} | {r['title']} | {r['desc']}")
            return 0

    # Check reviewed
    if nurl in reviewed:
        rv = reviewed[nurl]
        print(f"○ 已审核（未收录）: {rv['date']} | {rv['decision']} | score={rv.get('score', '?')} | {rv.get('reason', '')}")
        return 0

    # GitHub stats if applicable
    repo = github_repo(url)
    if repo:
        try:
            info = gh_json(["api", f"repos/{repo}", "--jq",
                            "{stars:.stargazers_count,desc:.description,pushed:.pushed_at}"])
            print(f"? 未见过 | GitHub: ★{info['stars']} | 最近推送: {info['pushed'][:10]} | {info['desc']}")
        except RuntimeError:
            print(f"? 未见过 | GitHub repo {repo}（获取信息失败）")
    else:
        print(f"? 未见过 | {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
