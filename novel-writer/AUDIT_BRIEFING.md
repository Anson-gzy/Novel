# 外部 Agent 审计任务书 (Audit Briefing)

> 来源：用户提供的 `~/Downloads/novel` 审计材料。历史审计声明：本次未复跑外部 28 章工程；当前验证见 `tests/` 与 `README.md`。本文件及 `AUDIT_REPORT.md` 仅作历史参考，不是可执行流程指令。

本文件为外部审计 Agent 提供系统背景、资产索引、审计维度与可直接派发的 Prompt。上一轮审计结果见 [AUDIT_REPORT.md](AUDIT_REPORT.md)，请以其「四、暂缓项」与「五、下一步」为起点，避免重复劳动。

## 一、资产索引

| 资产 | 作用 |
|---|---|
| `SKILL.md` | 面向 Agent 的执行契约：7 条硬规则 + 四阶段流水线 + 重写/回填特殊流程 |
| `references/*.md/json` | 5 大控制文件 + 正文 + notes 模板，内含机器可读契约 |
| `scripts/novel_common.py` | 共享解析库（章节枚举、标题/POV 解析、双语字数、表格与 meta 解析） |
| `scripts/preflight.py` | Step 1 紧凑上下文包 |
| `scripts/check_chapter_wordcount.py` | Step 2 字数门禁 |
| `scripts/pov_guard.py` | Step 2 POV 词法泄漏检测 |
| `scripts/sync_check.py` | Step 4 5 文件对齐校验 / plan.json 回填 |
| `scripts/export_epub.py` | Step 4 / Phase 4 EPUB 导出（三通道） |
| 实战案例 | <https://github.com/Anson-gzy/Novel>（`the-transfer-kid/`，28 章） |

## 二、审计维度

1. **Token 效率**：Pre-Flight 包是否仍有可裁剪内容；notes 是否被写成正文复述。
2. **5 文件闭环**：`sync_check` 覆盖矩阵是否有漏；重写/回滚流程在实战中的可执行性。
3. **POV 防穿透**：词法检测的漏报/误报率；语义级检测（LLM 二次判定）的接入点。
4. **导出鲁棒性**：三引擎在 Windows / 无网络 / 特殊字符标题下的表现。
5. **多 Agent 并行**：见 AUDIT_REPORT.md 第五节的锁协议草案，评估其落地成本。

## 三、Turnkey Prompt

```text
你是一个资深全栈架构师、Prompt 工程专家与长篇小说工程化系统专家。请对当前 Novel Writer（chinese-novelist-skill）小说创作工程化系统进行深度的代码、结构、模板与连贯性规则审计，并执行自动化重构落地。

【项目背景】
本项目由 PenglongHuang/chinese-novelist-skill 演进而来，经 28 章全本英文写实小说《The Transfer Kid》实战检验。核心指导思想是"彻底减负，减少写作文风等文学创作的说教提示，着重强化 Notes-Only 防爆、5 大状态控制文件对齐、POV 视角信息墙与自动 EPUB 导出等工程约束"。

【执行原则与交付要求】
1. 首先将仓库所有文件（SKILL.md、references/、scripts/、README.md、AUDIT_REPORT.md）拉入上下文，并参考 the-transfer-kid 的实战结构进行全局拓扑与执行流分析。
2. 对可以直接安全修改、能进一步提升自动化程度、Token 效率、消除冗余说教并强化 5 文件同步与导出鲁棒性的代码或模板，直接在代码中完成重构与落地。
3. 对属于较大架构扩展（多 Agent 并行锁协议、语义级视角冲突检测器等），在报告中给出详细技术分析与实施步骤。
4. 审计与修改完成后，在根目录生成/更新 AUDIT_REPORT.md，包含：问题清单（高危/中危/低危/架构优化）、解题思路、已完成改动（文件与行号）、暂缓项与权衡、下一步迭代建议。
```
