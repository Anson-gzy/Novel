# Novel Writer · 长篇小说工程化连贯性系统

面向 20–50+ 章中英文长篇小说的分章创作 Skill。流程集中处理 Notes、5 个控制文件、POV 信息墙、字数与同步校验，以及每章和全本 EPUB 导出。

## 当前流程

项目包含：

```text
00-outline.md                 大纲、TODO、逐章 Brief
01-characters.md              人物硬事实与 Ch.NN 演进
02-timeline.md                时间线与约束
03-global-notes.md            既成事实、POV 信息墙、配角追踪
04-generation-plan.json       机器状态唯一真源
chapter-NN.md                 正文
chapter-NN-notes.md           连贯性备忘
```

每章按以下顺序执行：

```text
preflight N → 写正文 → 字数门禁 → Agent 语义复核 + POV 词法复核
→ 写 notes → 更新 00/01/02/03 → sync_check --fix
→ sync_check 只读复跑 → 单章 EPUB → 下一章
```

推进前，模型上下文只使用 notes 和控制文件。校验脚本可以在本地读取正文做机器检查，但只返回状态、错误和必要短摘录，不把全文返回给模型；精确切片与逐章 notes 回填按 SKILL.md 的限定规则执行。每章必须做语义 POV 复核，关键词无命中不等于语义通过。

共享控制文件由主 Agent 单写。子 Agent 只能写已分配章节正文与 notes，并且前置章节 notes 已完成后才能处理连续章节。

重写时，正文、notes 和 4 个 Markdown 控制文件完成后，必须显式执行：

```bash
python3 "$SKILL_ROOT/scripts/sync_check.py" "$ABS_PROJECT" --fix --chapter N --finalize-rewrite
python3 "$SKILL_ROOT/scripts/sync_check.py" "$ABS_PROJECT"
```

普通 `--fix` 不得结束 `rewriting`。`--fix` 可能报告修复前错误，必须复跑只读校验；最终导出前先全量 `--fix`，再全量只读确认 `errors=0`。

## 验证方式

先把 Skill 目录解析为绝对 `SKILL_ROOT`，把小说项目解析为绝对 `ABS_PROJECT`；执行前将 `N` 和其他占位符替换成实际值，并为含空格的路径保留引号：

```bash
python3 "$SKILL_ROOT/scripts/preflight.py" "$ABS_PROJECT" N
python3 "$SKILL_ROOT/scripts/check_chapter_wordcount.py" "$ABS_PROJECT/chapter-NN.md"
python3 "$SKILL_ROOT/scripts/pov_guard.py" "$ABS_PROJECT/chapter-NN.md"
python3 "$SKILL_ROOT/scripts/sync_check.py" "$ABS_PROJECT" --fix
python3 "$SKILL_ROOT/scripts/sync_check.py" "$ABS_PROJECT"
python3 "$SKILL_ROOT/scripts/export_epub.py" "$ABS_PROJECT" --book --desktop
```

全量导出前必须完成全量只读同步校验和每章 POV 语义复核。导出目录按脚本帮助与 SKILL.md 规则解析，桌面不可用时回退到项目 `exports/`。

## 外部审计声明

`The Transfer Kid` 的 28 章审计背景与审计任务说明来自本目录的 [AUDIT_BRIEFING.md](AUDIT_BRIEFING.md)；该外部材料仅是来源说明，不是当前安装包的验证结果。当前验证以脚本退出码和项目自身 fixture 为准。
