"""Auto-review candidates from work/candidates.json using the quality rubric.

Calls the Anthropic API (claude-sonnet-5-5) to score each candidate.
Scores >= 7: added to data/resources.json and data/changelog.json.
All candidates (pass or fail): written to data/reviewed.json.

Requires: ANTHROPIC_API_KEY env var.
Writes: data/resources.json, data/reviewed.json, data/changelog.json,
        work/review-report.md.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

from common import DATA, WORK, load, norm_url, save, today

RUBRIC = """你是一个资料审核 agent，负责为《深入学习大语言模型原理》网站评审教程。

评分标准（满分 10 分，≥7 才收录）：
- 深度与系统性 0–3：讲清原理和"为什么"，有完整结构
- 可实践性 0–2：有可运行代码、练习或真实案例
- 来源可信度 0–2：官方/知名团队/有一手经验的作者
- 新颖性 0–2：覆盖资料库里没有的主题，或明显比现有更好/更新
- 维护与口碑 0–1：近期更新、社区讨论正面

一票否决（score=0）：纯付费课程、明显AI批量生成未验证、纯广告、与已有条目高度重复。

主题范围：Transformer架构、KV Cache、自注意力、位置编码(RoPE/ALiBi)、预训练、分词器、
SFT/RLHF/DPO、LoRA/PEFT、量化、Flash Attention、推理优化、MoE、多模态LLM、Mamba。

已收录的核心资源（避免重复收录）：
- rasbt/LLMs-from-scratch (108k★, 从零实现)
- mlabonne/llm-course (85k★, 路线图)
- karpathy/nn-zero-to-hero (25k★, 视频)
- datawhalechina/self-llm (32k★, 中文微调部署)
- karpathy/build-nanogpt (5.6k★, nanoGPT视频)
- harvardnlp/annotated-transformer (7.6k★, 论文注释)

请仅根据提供的标题和摘要评分。对信息不足的候选给出保守分数（≤6）。

输出严格JSON格式：
{"score": 7, "decision": "accept", "category": "courses", "type": "community", "format": "repo", "lang": "英文", "desc": "一句话中文说明（≤60字）", "reason": "一句话理由"}

category枚举：courses | from-scratch | zh-community | official-docs | internals | training | inference | academic | ai-generated
type枚举：official | community | academic | ai
format枚举：repo | course | docs | article | paper | video | newsletter | book | website
"""


def call_claude(prompt: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    payload = json.dumps({
        "model": "claude-sonnet-5-5",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read())
            return body["content"][0]["text"].strip()
    except urllib.error.HTTPError as ex:
        raise RuntimeError(f"Anthropic API {ex.code}: {ex.read()[:200]}") from ex


def score_candidate(c: dict) -> dict:
    prompt = (
        f"候选资源：\n标题：{c['title']}\nURL：{c['url']}\n"
        f"摘要：{c.get('snippet', '')[:300]}\n"
        f"Stars：{c.get('stars', '未知')}\n来源：{c.get('source', '')}\n"
        f"日期：{c.get('date', '')}\n\n{RUBRIC}"
    )
    text = call_claude(prompt)
    # Extract JSON from response
    import re
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {"score": 0, "decision": "reject", "reason": "无法解析模型输出"}
    return json.loads(m.group(0))


def make_resource_id(url: str, title: str) -> str:
    import re
    # GitHub: owner/repo → owner-repo
    m = re.match(r"https?://github\.com/([^/]+)/([^/#?]+)", url)
    if m:
        return f"{m.group(1).lower()}-{m.group(2).lower()}"
    # Other: slugify domain + path
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60]


def main() -> int:
    candidates_path = WORK / "candidates.json"
    if not candidates_path.exists():
        print("work/candidates.json 不存在，跳过审核。")
        return 0

    candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
    if not candidates:
        print("没有新候选。")
        return 0

    data = load("resources.json")
    reviewed = load("reviewed.json", {})
    log = load("changelog.json", [])

    existing_ids = {r["id"] for r in data["resources"]}
    t = today()
    added_ids: list[str] = []
    report_lines = [f"# 审核报告 {t}\n", f"共审核 {len(candidates)} 条候选。\n"]

    for c in candidates:
        nurl = norm_url(c["url"])
        if nurl in reviewed:
            continue
        try:
            result = score_candidate(c)
        except Exception as ex:
            print(f"[review] {c['title']}: {ex}", file=sys.stderr)
            reviewed[nurl] = {"date": t, "decision": "error", "score": 0, "reason": str(ex)[:100]}
            continue

        score = result.get("score", 0)
        decision = result.get("decision", "reject")
        reviewed[nurl] = {"date": t, "decision": decision, "score": score, "reason": result.get("reason", "")}

        report_lines.append(
            f"\n{'✓' if decision == 'accept' else '✗'} [{c['title']}]({c['url']})  "
            f"score={score}  {result.get('reason', '')}"
        )

        if decision == "accept" and score >= 7:
            rid = make_resource_id(c["url"], c["title"])
            # Avoid duplicate IDs
            suffix = 1
            base = rid
            while rid in existing_ids:
                rid = f"{base}-{suffix}"
                suffix += 1
            existing_ids.add(rid)

            resource = {
                "id": rid,
                "title": c.get("title", ""),
                "url": c["url"],
                "extra_links": [],
                "category": result.get("category", "courses"),
                "type": result.get("type", "community"),
                "format": result.get("format", "repo"),
                "lang": result.get("lang", "英文"),
                "github": None,
                "desc": result.get("desc", ""),
                "pick": False,
                "added": t,
                "score": score,
                "stars": c.get("stars"),
                "pushed_at": c.get("pushed_at"),
                "status": "ok",
                "last_checked": t,
                "note": "",
                "fail_count": 0,
            }
            # Fill github field for github URLs
            import re
            m = re.match(r"https?://github\.com/([^/]+/[^/#?]+)", c["url"])
            if m:
                resource["github"] = m.group(1).rstrip(".git")

            data["resources"].append(resource)
            added_ids.append(rid)

    # Save updated data
    save("resources.json", data)
    save("reviewed.json", reviewed)

    if added_ids:
        log.insert(0, {
            "date": t,
            "summary": f"自动审核新增 {len(added_ids)} 条",
            "stats": {"候选": len(candidates), "审核": len(candidates), "新增": len(added_ids), "移除": 0},
            "added": added_ids,
            "changed": [],
            "removed": [],
            "guide_changes": [],
        })
        save("changelog.json", log)
        report_lines.append(f"\n\n## 新增 {len(added_ids)} 条\n")
        for rid in added_ids:
            r = next(x for x in data["resources"] if x["id"] == rid)
            report_lines.append(f"- {r['title']} — {r['desc']}")

    WORK.mkdir(exist_ok=True)
    (WORK / "review-report.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(f"审核完成：新增 {len(added_ids)} / {len(candidates)} 条。详见 work/review-report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
