---
name: novel-writer
description: |
  长篇小说分章节创作与工程化连贯性系统（zh/en）。Notes-Only 防上下文爆炸、5 大状态控制文件对齐、
  POV 视角信息墙、脚本化门禁（字数 / 同步 / POV 泄漏）与 EPUB 自动导出。
  当用户提到：写小说、创作故事、分章节写作、长篇小说、小说续写、novel-writer、chinese-novelist 时使用。
metadata:
  trigger: 创作小说、写小说、分章节故事、长篇小说创作、novel-writer、chinese-novelist
  source: 经 The Transfer Kid（28 章）实战沉淀，v2 增加脚本门禁与机器可读契约
---

# Novel Writer

面向 20–50+ 章长篇的分章创作系统，集中管理跨章状态、信息边界、校验与导出。
文风、修辞、对话节奏全部交给模型自身判断，本文件不包含任何文学写法要求。

---

## 硬规则（7 条，全程无条件遵守）

### R1 · Notes-Only：禁止回读正文
- 推进新章或查询前情时，模型上下文**只读** `chapter-NN-notes.md` 与 5 大控制文件；**禁止**把任何 `chapter-NN.md` 全文加载或返回给模型。
- 本地校验脚本可以为机器校验读取正文全文，但只能返回状态、错误和必要的短摘录，不得把全文交给模型。需要精确核对某句原话 / 某个道具名时，可用 `grep`/切片查看 ≤ 20 行；查完即关。
- 缺 notes 的旧章可按章依次读取正文，每次只读一章并立即写出 notes；精确切片和逐章 notes 回填是 R1 的限定例外，不得一次性加载多章。
- 先把本文件所在目录解析为绝对 `SKILL_ROOT`，把项目解析为绝对 `ABS_PROJECT`；所有可执行命令都使用已解析变量并加引号，例如 `python3 "$SKILL_ROOT/scripts/<name>.py" "$ABS_PROJECT" ...`。`<name>`、`<N>` 等占位符执行前必须替换为实际值。Step 1 生成紧凑上下文包（大纲切片 + 上章 notes + 既成事实 + 本章 POV 的信息墙行 + 配角预警 + 时间线尾部），不要手动整读大纲。

### R2 · 语言锁定与字数门禁
- 语言与上下限来自 `04-generation-plan.json`（`language` / `minWordsPerChapter` / `maxWordsPerChapter`）。默认：zh 3000–5000 汉字，en 1500–2500 词。
- 写完必须跑 `python3 "$SKILL_ROOT/scripts/check_chapter_wordcount.py" "$ABS_PROJECT/chapter-NN.md"`，退出码非 0 不得进入 Step 3；上下限均为门禁条件。

### R3 · 正文机器契约
- 首行 `# 第 NN 章：标题`（en：`# Chapter NN: Title`），第三行 `*(POV: 角色名)*`——**单视角作品也必须标**。缺失即 `sync_check` ❌。

### R4 · 5 文件全量对齐
每章生成 notes 后，**同拍**更新 5 个控制文件，然后运行 `python3 "$SKILL_ROOT/scripts/sync_check.py" "$ABS_PROJECT" --fix`，直到 `errors=0`。`--fix` 只修复机器元数据，不改 Markdown；它可能报告修复前的错误，必须重新运行 `python3 "$SKILL_ROOT/scripts/sync_check.py" "$ABS_PROJECT"` 做只读校验。

| 文件 | 本章必做 | 自动校验点 |
|---|---|---|
| `00-outline.md` | TODO 勾选 `[x]` | 该章条目已勾选 |
| `01-characters.md` | 追加 `Ch.NN 演进：…` | 出现 `Ch.NN` |
| `02-timeline.md` | 全局时间线追加一行 | 该章行存在 |
| `03-global-notes.md` | 刷新既成事实 / 信息墙（新秘密、解禁）/ 追踪表 | 追踪表最大章号 ≥ NN |
| `04-generation-plan.json` | 由 `sync_check --fix` 自动回填 | status / wordCount / pov / day |

### R5 · POV 信息墙
- 每个 POV 角色只能使用其亲眼所见、亲耳所闻的信息。秘密在 `03-global-notes.md` 信息墙表中以**表格 + 禁用关键词**登记，揭示后填「解禁章节」。
- 每章写完都必须由 Agent 做语义复核，再跑 `python3 "$SKILL_ROOT/scripts/pov_guard.py" "$ABS_PROJECT/chapter-NN.md"`。关键词命中必须人工/Agent 复核；关键词无命中不代表语义通过。信息墙为空时脚本会明确报告未执行词法检查，仍可由 Agent 完成语义复核后放行，不得伪造秘密或关键词。

### R8 · 每章配图
- 每章正文定稿（通过 R2/R4/R5）后，必须走 [novel-illustrator](../novel-illustrator/SKILL.md) 产出 `illustrations/chapter-NN/chapter-NN-illustrated.md` 与该章 30 幅插图，再进 R7 导出。成品 EPUB 一律带插图。
- **这是 R1 的限定例外**：配图环节允许读**正在配图的那一章**正文，读完直接产出 30 镜头的 shot list 与提示词文件；不得把正文带进后续轮次，派子代理时子代理只返回提示词文件，不返回正文。
- 人物正脸图与场景定场图是**项目级资产**（`illustrations/refs/`），第一次配图时建立，之后每章复用——跨章形象一致靠它，不靠每章重写外貌描述。
- 门禁：`python3 ~/.agents/skills/novel-illustrator/scripts/verify_illustrated.py "$ABS_PROJECT/illustrations/chapter-NN/chapter-NN-illustrated.md"`，退出码非 0 不得进入 R7。

### R6 · 配角活跃度
- `03-global-notes.md` 追踪表记录每个重点配角的上次出场章节与形式。`preflight.py` 对 > 4 章未露面者预警；用走廊偶遇、群聊、被提及、背景动作等轻量形式带出，禁止断崖式蒸发。

### R7 · EPUB 导出（每章 + 全本）
- 每章通过 R2/R4/R5/R8 后执行 `python3 "$SKILL_ROOT/scripts/export_epub.py" "$ABS_PROJECT/chapter-NN.md" --desktop --illustrated`。
- `--illustrated` 使导出优先取 `illustrations/chapter-NN/chapter-NN-illustrated.md`（不存在则静默回退到纯正文），并把 `<img>` 引用的图片打进 EPUB 包。
- 目录解析：`--out` > `$NOVEL_EXPORT_DIR` > `plan.exportDir` > `~/Desktop/<书名>`（大小写/空格不敏感匹配已有文件夹）> `<项目>/exports/`。桌面不存在时自动回退，**不得因导出失败中断创作循环**，但要在汇报中标注。
- 引擎自动降级：ebooklib → pandoc → 内置零依赖引擎；全本用 `--book`。

---

## 项目结构

```text
novel-project/
├── 00-outline.md             # 大纲 + TODO + 逐章 Brief（### 第 NN 章：标题）
├── 01-characters.md          # 人物硬事实 + Ch.NN 演进记录
├── 02-timeline.md            # D+N 时间线表 + 固定周期 + 约束 + 冲突记录
├── 03-global-notes.md        # 既成事实 + POV 信息墙表 + 配角追踪表
├── 04-generation-plan.json   # 机器状态（唯一真源）
├── chapter-NN.md / chapter-NN-notes.md
└── exports/                  # 桌面不可用时的 EPUB 回退目录
```
模板见 `<SKILL_ROOT>/references/`；所有脚本零第三方依赖，使用 `python3 <SKILL_ROOT>/scripts/<name>.py -h` 查看用法。

---

## 工作流

### Phase 0 · 路由
- 目录已有 5 大控制文件 → 读 `04-generation-plan.json`，跑 `python3 "$SKILL_ROOT/scripts/sync_check.py" "$ABS_PROJECT"`，按报告修复失步后直接续写；不要求用户重新确认健康设定。
- 存在 `~/.novel-writer/user-preferences.json` 或项目内 `user-preferences.json` → 作为 Phase 1 默认值，不再询问已覆盖项。

### Phase 1 · 极简需求（一次问完）
只收集：题材 / 主线冲突 / POV 规则与角色名单 / 语言 / 章节数。用户已给大纲或素材 → 直接提炼，不追问。

### Phase 2 · 建立 5 文件
按 `<SKILL_ROOT>/references/` 模板生成 5 文件（Brief 至少覆盖前 5 章）。只有存在真实知识边界时才填写信息墙行；不要为满足格式虚构秘密。向用户输出大纲摘要 + POV 规则，确认后进入 Phase 3。

### Phase 3 · 自主分章循环（每章四步，不打扰用户）

```text
Step 1  preflight.py N      → 读上下文包；健康检查有 ⛔ 先处理
Step 2  写 chapter-NN.md   → 字数门禁 → 每章 Agent 语义复核 → POV 词法复核
Step 3  写 chapter-NN-notes.md（含 ```meta 块）
Step 4  更新 00/01/02/03 → --fix → 只读核验
Step 5  novel-illustrator 配图 → verify_illustrated.py → 导出（--illustrated）→ 下一章
```

Step 5 见 R8。首章会额外花时间建项目级人物/场景参考图，之后每章只补新出现的地点。

### Phase 4 · 终审交付
最终先运行全量 `python3 "$SKILL_ROOT/scripts/sync_check.py" "$ABS_PROJECT" --fix`，再运行只读 `python3 "$SKILL_ROOT/scripts/sync_check.py" "$ABS_PROJECT"` 确认 `errors=0`；随后全量 POV 语义复核与词法复核，最后运行 `python3 "$SKILL_ROOT/scripts/export_epub.py" "$ABS_PROJECT" --book --desktop` 导出全本。

共享控制文件只能由主 Agent 单写。子 Agent 只能写已分配的章节正文与 notes，且只有在前置章节 notes 已完成时才能处理连续章节；不满足此前置条件，不得并写连续章节。

---

## 特殊流程

### 重写与回滚（某章需要重写 / 剧情大改）
1. `04-generation-plan.json` 中该章 `status` 改为 `rewriting`，`retryCount + 1`。
2. 只读该章 **旧 notes**（不读旧正文），列出「旧 notes 中哪些事实将被推翻」。
3. 反向清理：从 `03` 既成事实/信息墙、`02` 时间线行、`01` 该章演进记录中删除或标注 `~~废弃 (rewrite NN)~~`；勿直接删除后续章节内容。
4. 重写正文 → 新 notes → 更新正文、notes 与 4 个 Markdown 控制文件后，显式运行 `python3 "$SKILL_ROOT/scripts/sync_check.py" "$ABS_PROJECT" --fix --chapter NN --finalize-rewrite`。随后再运行不带 `--fix` 的全量只读校验；只有确认 `errors=0` 后才结束 `rewriting`。若被推翻事实已被后续章节引用，逐章在其 notes 顶部加 `⚠️ 受 Ch.NN 重写影响：…`，进入下一轮修补队列。

### Notes 回填（发现旧章缺 notes，如 Ch.21–24 无 notes 的实战情形）
- 精确切片与逐章 notes 回填均是 **R1 的限定例外**：允许按章依次读取缺 notes 的正文，**每次只读一章**，读完立即写出该章 notes，再读下一章；禁止一次性加载多章。
- 回填完成后跑 `python3 "$SKILL_ROOT/scripts/sync_check.py" "$ABS_PROJECT" --fix`，再跑不带 `--fix` 的只读校验，随后恢复 Notes-Only 续写。

### 语言 / 视角规则变更
- 视为新项目：`language` 或 `povRule` 一旦写入 plan.json 不得中途修改；确需修改时另建项目目录。
