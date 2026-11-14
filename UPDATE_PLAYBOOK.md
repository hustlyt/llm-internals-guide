# 每周更新手册（给执行更新的 agent）

目标：让网站保持**高质量 + 新鲜**。宁缺毋滥：一周没有够格的新资料，就只发布健康检查结果，不凑数。

工作目录：本仓库根目录。所有脚本只用 Python 标准库 + `gh` CLI。

## 流程

1. **同步**：`git pull --ff-only`。失败就停止，报告原因。
2. **健康检查**：`python3 scripts/check.py` → 读 `work/check-report.md`。
   - `改名 / 重定向`：把 `data/resources.json` 和 `content/` 下各页面里的旧 URL 换成新 URL。
   - `已判定失效`：先手动 `curl -IL` 复核；确实失效就移出 `resources.json`，在 changelog 的 `removed` 记录。
   - `超过一年未更新`：评估是否仍有价值。经典教材（论文实现、Karpathy 系列）设 `"evergreen": true`；过时的移除。
3. **搜集候选**：`python3 scripts/discover.py` → 读 `work/candidates.md`。
4. **补充检索（必须做）**：用 Web 搜索查最近 3 周的
   - 官方：Hugging Face、Meta AI、Google DeepMind、OpenAI、Anthropic 新发布的 LLM 教程、模型卡、技术报告；
   - 课程平台：DeepLearning.AI 短课、YouTube 上的系统性 LLM 课程；
   - 中文：Datawhale、知乎专栏、掘金、机器之心上的高质量 Transformer/KV Cache/推理优化教程；
   - 重要新论文/综述（KV Cache 优化、注意力变体、推理加速、对齐）。
5. **审核**：对每个有希望的候选，**打开原文读**（README / 正文 / 目录），按下方评分标准打分。
6. **写入**：通过的条目加进 `data/resources.json`；所有看过的候选（通过和拒绝都算）写进 `data/reviewed.json`。
7. **教程正文**：只有出现明显更好的资料或某阶段内容过时，才改教程页面。
   - 首页推荐：`content/home.html`
   - 学习路线阶段阅读清单：`content/phases/p0.html` … `p6.html`（只写 `<ul>` 列表）
   - 阶段标题、周次、一句话简介、产出：`content/phases.json`
   - 毕业项目：`content/capstone.html`；学习建议：`content/tips.html`
   - 每个阶段页保持 4–6 条阅读材料，新增时同步淘汰过时的。
8. **更新日志**：在 `data/changelog.json` 最前面加一条。
9. **构建与自检**：`python3 scripts/build.py`（会做数据校验，失败必须修好），再抽查 `docs/index.html`。
10. **发布**：`git add -A && git commit -m "update: YYYY-MM-DD ..." && git push`。

## 质量评分标准（满分 10，**≥ 7 才收录**）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 深度与系统性 | 0–3 | 讲清原理和"为什么"，有完整结构；单篇浅显介绍、营销软文 = 0 |
| 可实践性 | 0–2 | 有可运行代码、练习或真实案例；代码能跑通且维度正确 |
| 来源可信度 | 0–2 | 官方 / 知名团队 / 有一手经验的作者；匿名搬运 = 0 |
| 新颖性 | 0–2 | 覆盖资料库里还没有的主题，或明显比现有条目更好/更新 |
| 维护与口碑 | 0–1 | 近期更新、社区讨论正面（star、HN 讨论、引用） |

**一票否决**：需要付费才能看核心内容；明显 AI 批量生成且未经验证；纯产品广告；与已收录条目高度重复；工具/框架本身（除非就是学习材料）。

**AI 生成的教程**：可以收，但单独标注 `type: "ai"`，且必须"可实践性 ≥ 1"和"深度 ≥ 2"。

## 数据格式

### resources.json 条目

```json
{
 "id": "owner-repo 或 域名-路径 的小写短横线形式，唯一",
 "title": "显示标题",
 "url": "https://…",
 "extra_links": [{"label": "文档", "url": "https://…"}],
 "category": "courses | from-scratch | zh-community | official-docs | internals | training | inference | academic | ai-generated",
 "type": "official | community | academic | ai",
 "format": "repo | course | docs | article | paper | video | newsletter | book",
 "lang": "中文 | 英文 | 多语（含中文）…",
 "github": "owner/repo 或 null",
 "desc": "一句话中文说明（≤ 60 字）",
 "note": "可选注意事项",
 "pick": false,
 "added": "YYYY-MM-DD",
 "score": 8,
 "stars": null, "pushed_at": null, "status": "ok", "last_checked": null
}
```

`pick: true` 只给推荐组合里的核心教材，全站保持 ≤ 5 个。

### changelog.json 条目（加在数组最前）

```json
{
 "date": "YYYY-MM-DD",
 "summary": "一句话概括本周更新",
 "stats": {"候选": 50, "审核": 15, "新增": 4, "移除": 0},
 "added": ["resource-id"],
 "changed": [{"id": "x", "title": "x", "reason": "URL 迁移到 …"}],
 "removed": [{"id": "x", "title": "x", "reason": "仓库已删除"}],
 "guide_changes": ["学习路线 P2 增加 …"]
}
```

## 不要做

- 不要改写 `UPDATE_PLAYBOOK.md`、`scripts/` 的核心逻辑，除非是修 bug。
- 不要 `git push --force`。
- 不要编造链接、star 数或内容描述。
