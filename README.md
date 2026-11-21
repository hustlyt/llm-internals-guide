# 深入学习大语言模型原理

学习路线 + 持续更新的资料库：Transformer 架构、KV Cache、预训练、对齐微调、推理优化。

**网站：** https://hustlyt.github.io/llm-internals-guide/ · [资料库（可搜索）](https://hustlyt.github.io/llm-internals-guide/resources.html) · [更新日志](https://hustlyt.github.io/llm-internals-guide/changelog.html) · [RSS](https://hustlyt.github.io/llm-internals-guide/feed.xml)

在本仓库根目录运行 `python3 -m http.server 8000 --bind 127.0.0.1 --directory docs`，打开 [本地课程](http://127.0.0.1:8000/) 可阅读当前工作区中的站点。

## 推荐主教材

[rasbt/LLMs-from-scratch](https://github.com/rasbt/LLMs-from-scratch) 用 PyTorch 从零实现 GPT。全书 7 章，覆盖分词、注意力、预训练、分类微调和指令微调，并附配套 Notebook。附录 E 讲 LoRA，仓库补充材料另有 KV Cache 和 DPO。

配合 [karpathy/nn-zero-to-hero](https://github.com/karpathy/nn-zero-to-hero) 视频系列（P0–P1 阶段）和 [datawhalechina/self-llm](https://github.com/datawhalechina/self-llm)（P4–P5 中文实战）。

## 怎么更新

每周一 09:00（北京时间）由定时任务自动运行，流程和质量标准见 [UPDATE_PLAYBOOK.md](UPDATE_PLAYBOOK.md)：

1. `scripts/check.py`：刷新 GitHub Star 和最近提交时间，检查所有链接
2. `scripts/discover.py`：从 GitHub、官方博客 RSS、Hacker News 搜集候选
3. agent 补充网络搜索，打开原文按 10 分制评分，≥ 7 分才收录
4. `scripts/build.py`：校验数据并生成 `docs/`，推送后由 GitHub Pages 发布

只依赖 Python 3.11+ 标准库和 `gh` CLI。

## 目录

| 路径 | 内容 |
|---|---|
| `data/resources.json` | 资料库（唯一数据源） |
| `data/changelog.json` | 更新日志 |
| `data/reviewed.json` | 已审核过的 URL，避免重复审核 |
| `data/sources.json` | 搜集用的数据源和关键词 |
| `content/` | 教程页面正文：`home.html`、`phases/`（各阶段阅读清单）、`phases.json`、`capstone.html`、`tips.html` |
| `docs/` | 生成的网站（不要手改） |
| `scripts/lookup.py` | 查某个 URL 是否已收录/审核过、相近条目和 GitHub 数据 |
