# Novel Writer（chinese-novelist-skill）深度审计与重构报告

> 来源：用户提供的 `~/Downloads/novel/AUDIT_REPORT.md`。历史审计声明：本次未复跑外部 28 章工程；当前验证见 `tests/` 与 `README.md`。本文为归档参考，不是可执行流程指令。

> 审计对象：<https://github.com/Anson-gzy/chinese-novelist-skill>（SKILL.md / references/ / scripts/ / README.md / AUDIT_BRIEFING.md / test-prompts.json / user-preferences.json）
> 实战参照：<https://github.com/Anson-gzy/Novel> `the-transfer-kid/`（28 章，已完整克隆并用新脚本做回归扫描）
> 审计方法：全量阅读 → 对实战项目做静态扫描（字数 / POV 标记 / notes 覆盖 / plan 一致性）→ 在"无 ebooklib、无 pandoc、无 ~/Desktop"的最恶劣环境中运行旧脚本与新脚本 → 重构落地 → 端到端回归（28 章实战项目 + 符合 v2 契约的迷你项目）。

---

## 一、发现的问题清单

### 🔴 高危（会直接导致创作循环失败、数据错误或规则形同虚设）

| # | 问题 | 证据 | 影响 |
|---|---|---|---|
| H1 | **`export_epub.py` 目录模式会把 notes 一并导出为 EPUB** | 旧脚本 L113 `glob("chapter-[0-9]*.md")`，`*` 同样匹配 `1-notes`，`chapter-01-notes.md` 被视为章节 | 全书批量导出产出 2× 文件，读者拿到 notes |
| H2 | **`export_epub.py` 在无 `~/Desktop` 环境直接崩溃** | 旧 L18 `desktop.iterdir()` 对不存在目录抛 `FileNotFoundError`，未捕获；沙箱实测 traceback | Linux 服务器 / Windows OneDrive 重定向桌面 / CI 全部不可用 |
| H3 | **pandoc 兜底本身会崩溃** | 旧 L83 `subprocess.run(["pandoc",…])`，pandoc 未安装时抛 `FileNotFoundError`，位于 `except` 块内无二次保护 | "双通道容灾"在缺 ebooklib + 缺 pandoc 时等于零通道；实战作者最终手写了 `the-transfer-kid/export_epub.py` 硬编码路径脚本，证明工具未被采用 |
| H4 | **`check_chapter_wordcount.py` 对英文项目永远返回 0 字** | 只统计 `[\u4e00-\u9fff]`；标题识别依赖汉字"章"；默认 glob `第*.md`；README 却宣称"精确统计汉字字数与英文词数" | 英文项目字数门禁完全失效；The Transfer Kid 实测 4 章低于 1500 词（Ch.22 仅 1165 词）、3 章超过 2500 词，README"28 章全部达成 1500–2500"与事实不符 |
| H5 | **5 文件对齐纯靠 Prompt 自觉，无任何校验，实战已失步** | `04-generation-plan.json` 只登记 Ch.25–28（4/28）；Ch.21–24 无 notes；10 章缺 `*(POV)*` 标记；大纲头部仍链接旧文件名 `timeline.md`/`global-notes.md` | Notes-Only 链条在 Ch.21–24 断裂；断点续写时 plan 无法作为真源 |
| H6 | **Notes-Only 规则没有给出"notes 缺失"时的合法出路** | SKILL 只说"严禁读正文"，实战出现 4 章无 notes 时 Agent 只能违规或瞎写 | 规则在最需要时无法执行 |

### 🟠 中危（明显降低 Token 效率、可维护性或规则可执行性）

| # | 问题 | 证据 |
|---|---|---|
| M1 | **Pre-Flight 要求"读 00-outline 章节 Brief"，但大纲文件会膨胀到 51KB** | 实战 `00-outline.md` 51,110 字节；每章整读 ≈ 15k tokens 纯浪费，且与"防爆"目标矛盾 |
| M2 | **SKILL.md 约 25% 篇幅在解释"为什么不说教"** | 开头哲学段、每条规则的"核心目的"说明；本身就是一种元说教，Agent 执行时无需 |
| M3 | **`--name` 参数在目录模式下被静默忽略** | 旧 L105 `args.name or a if cond else b` 运算符优先级：解析为 `(args.name or a) if cond else b` |
| M4 | **实战文件仍大量残留文风说教** | `03-global-notes.md` 一整节"写作风格与偏好提醒"（CEFR B2 / Show don't tell）；每章 notes 含 `Style & Language: … zero em dashes, zero AI buzzwords, zero negative parallelisms`——与项目核心主张直接冲突，且 28 章重复 28 次 |
| M5 | **模板缺乏机器可读契约** | notes 模板、POV 信息墙、追踪表都是自由文本；没有任何脚本能校验 POV 一致性、时间锚点或追踪表刷新 |
| M6 | **`generation-plan.json` 元数据不足** | 无 `pov` / `day` / `maxWordsPerChapter` / `exportDir` / `author` / `displayTitle` / `epubPath`；导出器只能硬编码 `lang="zh"`、`author="Author"` |
| M7 | **没有"重写 / 回滚"流程** | 剧情大改时 5 文件如何级联、被推翻事实如何标注，SKILL 无任何说明（AUDIT_BRIEFING 维度 2 已点名） |
| M8 | **Phase 4 承诺"全本整合 EPUB"，脚本不支持** | 旧脚本目录模式仅逐章导出，无合并 |
| M9 | **章节标题契约只有中文** | `chapter-template.md` 仅 `# 第 [X] 章：`；实战英文用 `# Chapter 28: Ice Pack`；`*(POV)*` 英文项目缺失 10 章 |
| M10 | **控制文件间字段重复** | 角色性格同时出现在 `01-characters`（性格核心/Speech Pattern）与 `03-global-notes` 第四节"防崩提醒"；时间线模板"各章节时间细节"与 notes 的时间锚点重复；TODO 列表 / Brief / plan.json 三处维护章节状态 |

### 🟡 低危（卫生、一致性、文档准确性）

| # | 问题 |
|---|---|
| L1 | 仓库提交了 `.DS_Store` 与 `.claude/settings.local.json`（本地权限文件），无 `.gitignore` |
| L2 | `AUDIT_BRIEFING.md` 引用绝对本地路径 `the-transfer-kid` |
| L3 | `check_chapter_wordcount.py` 末尾引用不存在的 `references/content-expansion.md`，并输出"添加细节描写/扩展内心活动"等扩写说教 |
| L4 | `test-prompts.json` 仍是上游语义（"7 问"、"确认门"、"novelist"、"purple prose"），与当前 Lean Intake 流程不符；Prompt 5 本身含文风说教 |
| L5 | `user-preferences.json` 混入项目专属数据（Samira 行为禁令）与未被 SKILL 引用的 `subagentConfig` 模型名 |
| L6 | 旧脚本无退出码语义（批量失败仍 exit 0）、无 Windows 控制台 UTF-8 处理（wordcount 有、export 没有） |
| L7 | `character-template.md` 的 MBTI 字段无剧情决策价值；"避免空洞形容词"属文风说教 |
| L8 | `timeline-template.md` 约束表缺少二级标题（L58 直接以 `>` 开始） |
| L9 | README "所有 28 章均自动生成 EPUB"与实战（手写脚本、硬编码 20–24 章）不符 |

### 🔵 架构与工程优化项

| # | 项 |
|---|---|
| A1 | 语义级 POV 越界检测（词法检测只能抓"直接提名"） |
| A2 | 多 Agent 并行章节写作的分工锁协议 |
| A3 | 5 文件 Markdown 段落的自动回写（目前 `--fix` 只写 plan.json） |
| A4 | notes → 追踪表 / 时间线的自动派生 |
| A5 | 项目级 `doctor` 一键体检与 CI 集成 |

---

## 二、核心解题思路与重构策略

**1. 从"Prompt 提醒"转向"脚本门禁"。**
旧系统把 6 条硬规则全部寄托于模型自觉，实战证明会失步（H5）。重构后每条规则都对应一个有退出码的脚本，Agent 的职责从"记住规则"变为"跑命令、看 ❌、修到 0"：

| 规则 | 门禁 |
|---|---|
| Notes-Only / Token 防爆 | `preflight.py` 生成切片化上下文包，不再整读控制文件 |
| 字数 & 语言 | `check_chapter_wordcount.py`（双语，读 plan） |
| 5 文件对齐 | `sync_check.py`（9 项校验矩阵 + `--fix`） |
| POV 信息墙 | `pov_guard.py`（词法检测 + 解禁章节） |
| 配角活跃度 | `preflight.py` 预警 |
| EPUB | `export_epub.py`（三通道 + 回退目录 + plan 回写） |

**2. 建立机器可读契约，让 Markdown 可被校验。**
- 正文：首行标题正则（中英）+ 第三行 `*(POV: X)*`。
- notes：顶部 ```` ```meta ```` 块（chapter / pov / day / present / mentioned）。
- 03-global-notes：POV 信息墙由自由列表改为 5 列表格，新增"禁用关键词"和"解禁章节"，直接驱动 `pov_guard.py`。
- 04-generation-plan.json v2：新增 `pov / day / maxWordsPerChapter / exportDir / author / displayTitle / povRule / epubPath / completedChapters / totalWordCount`，成为脚本的唯一配置源。

**3. 彻底减负，但把"减掉的东西"放对位置。**
- SKILL.md 从 8.0KB → 7.4KB，且新增了 3 个流程（重写回滚、Notes 回填、门禁命令）——净减掉的是哲学阐释与"核心目的"解释，全部迁至 README。
- 模板中删除：MBTI、"避免空洞形容词"、03 的"角色刻画防崩提醒"（合并进 01 的"防崩底线"一行）、时间线"各章节时间细节"（与 notes 重复）、字数扩写建议。
- 所有模板顶部改为一句话"这个文件放什么 / 哪个脚本会读它"，替代长段说明。

**4. 零依赖与容灾优先。**
所有脚本只用标准库。EPUB 新增内置引擎（zipfile 手工打包 EPUB 3 + NCX），在沙箱（无 ebooklib / pandoc / Desktop）实测 28 章批量 + 全本合并全部成功，XML 均通过 `minidom` 解析。

**5. 向后兼容实战项目。**
解析器同时识别 `第 NN 章` / `Chapter NN`、`Ch.12` / `第 12 章` / `12`、旧版列表式既成事实；旧 `check_chapter_wordcount.py <file> 3500` 位置参数用法保留。对 the-transfer-kid 原样运行 `sync_check.py --fix` 可把 plan.json 从 4 章补齐到 28 章。

---

## 三、已直接完成的改动与优化项清单

### 3.1 脚本（`scripts/`，全部新建或重写，零第三方依赖）

| 文件 | 行号 | 改动 | 解决 |
|---|---|---|---|
| `scripts/novel_common.py`（新） | L35–53 | 统一常量：控制文件清单、章节/notes 文件名正则、中英标题正则、POV 标记正则、CJK/英文词正则、默认字数基线 | M5, M9 |
| | L114–121 `list_chapters` | 用 `^chapter-(\d{1,3})\.md$` 精确匹配并按数值排序，排除 notes | **H1** |
| | L130–170 `parse_chapter` | 解析标题（中/英）、POV、剥离后的正文 | M9 |
| | L173–196 | `strip_markdown` / `detect_language` / `count_words` 双语统计 | **H4** |
| | L200–235 | GFM 表格解析、`extract_chapter_ref`（`第 05 章`/`Ch.12`/`12`） | M5 |
| | L237–264 | notes ```` ```meta ```` 块解析 | M5 |
| | L268–313 | POV 信息墙表 / 配角追踪表解析 | M5, R5/R6 |
| | L316–348 | `extract_chapter_brief`（只切当前章 Brief）、`outline_todo_status` | **M1** |
| | L351–372 | 时间线行 / 约束 / 未解决冲突解析 | M5 |
| `scripts/check_chapter_wordcount.py`（重写） | L36–61 | 语言与上下限优先读 plan.json，其次自动检测；剥离标题与 POV 行 | **H4**, M6 |
| | L63–75 | 输出含上下限、缺口、超限与缺 POV 提示；删除扩写说教与不存在的引用 | L3 |
| | L87–90, L118 | 保留旧位置参数用法；退出码 1 = 任一章不达标 | L6 |
| `scripts/preflight.py`（新） | L43 | `STALE_AFTER = 4` 配角预警阈值 | R6 |
| | L50–60 | 既成事实段切片（兼容旧版列表式布局） | M1 |
| | L62–69 | POV 推断：Brief 优先于 plan 占位值 | — |
| | L72–145 `build_packet` | 组装：plan 元数据 / 大纲切片 / 上章 notes / 既成事实 / 本章 POV 的信息墙行（自动过滤已解禁）/ 配角预警 / 时间线尾部 2 行 + 约束 + 未解决冲突 / 健康检查（缺 notes、缺 Brief、重写检测、缺控制文件） | **M1, H6** |
| | L147–177 | 文本渲染（`--json` 可选）；健康检查有项则退出码 1 | — |
| `scripts/sync_check.py`（新） | L107–115 | 正文：标题、POV 标记、字数上下限 | **H5**, M9 |
| | L117–132 | notes：存在性、meta 块、`meta.chapter`/`meta.pov` 与正文一致、`day` 缺失警告 | **H5** |
| | L134–150 | 00 TODO 勾选 / 01 `Ch.NN` 演进 / 02 时间线行 / 03 追踪表最大章号 | **H5** |
| | L152–182 | 04 plan：条目存在、status、wordCount 偏差 ≤ 5%；`--fix` 回填 title/pov/day/filePath/notesPath/status/wordCount/wordCountPass | **H5**, M6 |
| | L184–191 | EPUB 存在性（`epubPath` 或 `exportDir`） | R7 |
| | L196–204 | `--fix` 排序、`completedChapters`、`totalWordCount`、全书完成态 | M6 |
| `scripts/pov_guard.py`（新） | L41–72 | 按 POV 匹配信息墙行、`解禁章节 <= 当前章` 自动失效、ASCII 关键词整词匹配 / CJK 子串匹配、输出行号与上下文 | R5, A1（第一道防线） |
| | L74–113 | 单章 / `--all` / `--pov` 覆盖；退出码语义 | — |
| `scripts/export_epub.py`（重写） | L76–91 `resolve_desktop_dir` | 多候选桌面路径（Desktop / OneDrive / 桌面 / USERPROFILE），不存在返回 None 而非崩溃 | **H2** |
| | L94–111 `resolve_out_dir` | 优先级 `--out` > `$NOVEL_EXPORT_DIR` > `plan.exportDir` > 桌面 > `<项目>/exports/` | **H2**, M6 |
| | L115–182 | 内置 Markdown → XHTML（标题 / 段落 / 强调 / 引用 / 分隔线 / HTML 转义，zh 无空格拼接） | H3 |
| | L185–211 `engine_ebooklib` | 多章合并支持、统一 CSS | M8 |
| | L214–232 `engine_pandoc` | `shutil.which` 预检；`RuntimeError` 而非未捕获异常；120s 超时 | **H3** |
| | L235–286 `engine_builtin` | 零依赖 EPUB 3（mimetype 首项且 STORED、container.xml、OPF、nav.xhtml、toc.ncx）；原子写入 `.part → rename` | **H3** |
| | L292–307 `export` | 引擎顺序降级并聚合错误信息 | H3 |
| | L310–381 `main` | 修复 `--name` 优先级 bug；默认值读 plan（language / author / displayTitle / exportDir）；`--book` 全本；`--engine`；成功后回写 `epubPath`/`epubExportedAt`；退出码 | **M3, M8**, M6, L6 |

### 3.2 模板（`references/`）

| 文件 | 行号 | 改动 |
|---|---|---|
| `chapter-template.md` | L1–3, L6–17 | 双语标题契约 + POV 标记强制 + 机器契约注释（英文示例） |
| `chapter-notes-template.md` | L3–11 | 新增 ```` ```meta ```` 块（chapter / pov / day / clock / word_count / present / mentioned） |
| | L13–28 | 三段式精简：发生了什么（≤ 6 条）/ 连贯性锚点（新增"POV 知识变更"）/ 下章接力；限长 700 字 / 450 词 |
| `global-notes-template.md` | L7–14 | 既成事实要求标注来源章节 |
| | L17–27 | POV 信息墙改为 5 列表格：`POV 角色 / 不知道的事实 / 禁用关键词 / 来源章节 / 解禁章节` |
| | L31–38 | 追踪表 + 预警阈值说明；**删除**第四节"核心角色刻画防崩提醒"（与 01 重复） |
| `character-template.md` | 全文 | 删除 MBTI、外貌文风说教；新增"背景硬事实""防崩底线"；演进记录固定 `Ch.NN 演进：` 格式（供 sync_check 检查） |
| `timeline-template.md` | 全文 | 删除"各章节时间细节"节（与 notes 重复）；约束表补二级标题；增加 D-N 闪回约定 |
| `outline-template.md` | L12–18, L33–44 | TODO 条目与 Brief 标题格式固定（供 sync_check / preflight 解析）；Brief 新增"时间预算""POV 边界提醒"；删除目标字数重复项 |
| `generation-plan-template.json` | L2–16 | v2：`displayTitle / author / povRule / povCharacters / maxWordsPerChapter / exportDir / completedChapters / totalWordCount` |
| | L18–41 | 章节级 `pov / day / epubPath / epubExportedAt`；`status` 枚举含 `planned/draft/completed/rewriting` |

### 3.3 契约文档

| 文件 | 行号 | 改动 |
|---|---|---|
| `SKILL.md` | L1–10 | 精简 frontmatter description |
| | L19–56 | 6 → 7 条硬规则；每条附门禁命令；新增 R3 正文机器契约；R7 导出给出目录优先级与"导出失败不得中断循环" |
| | L74–98 | 四阶段流水线中嵌入脚本命令；Phase 0 增加 `sync_check` 体检与 user-preferences 读取 |
| | L100–113 | **新增**"重写与回滚"、"Notes 回填（R1 唯一批量例外）"、"语言/视角规则变更"三个特殊流程 |
| | 全文 | 删除"现代大模型天生具备顶级文学语感"等哲学段与各规则"核心目的"说明 |
| `README.md` | 全文 | 承接被移出 SKILL 的设计立场；7 规则 ↔ 脚本对照表；修正与实战不符的宣传（字数、EPUB）；给出回归扫描真实数据 |
| `AUDIT_BRIEFING.md` | 全文 | 移除绝对本地路径；资产索引更新为 v2 脚本；Turnkey Prompt 要求以本报告暂缓项为起点 |
| `test-prompts.json` | 全文 | 6 条用例对齐 v2 流程（含 Notes 回填、重写回滚、--book 导出） |
| `user-preferences.json` | 全文 | 移除项目专属禁令与未使用的 subagentConfig；新增 `defaultLanguage / author / exportDir` |
| `.gitignore`（新） | — | 排除 `.DS_Store`、`.claude/settings.local.json`、`__pycache__`、`exports/`、`*.epub` |

### 3.4 回归验证记录

| 场景 | 结果 |
|---|---|
| the-transfer-kid（28 章，无 ebooklib/pandoc/Desktop） `check_chapter_wordcount.py --all` | 正确按英文词计数；识别 4 章不足、3 章超限、2 章缺 POV |
| 同上 `sync_check.py --fix` | 50 errors 精确定位（缺 notes / 缺 POV / plan 缺条目 …）；plan.json 由 4 章回填为 28 章，`totalWordCount=59,955` |
| 同上 `preflight.py 29` | 正确报告"缺 Brief"；`preflight.py 22` 同时报告"上章 notes 缺失 + 重写" |
| 同上 `pov_guard.py --all`（注入测试信息墙） | Ch.11 命中 4 处 `partner`（为角色被当面告知的合法揭示，验证"命中需复核"设计） |
| 同上 `export_epub.py`（单章 / 批量 28 / `--book`） | 全部 builtin 引擎成功；EPUB 结构与全部 XML 通过校验；plan 回写 `epubPath` |
| v2 契约迷你中文项目 | preflight 输出 Brief 切片 + 信息墙行 + 未出场配角预警 + 约束 + 未解决冲突；pov_guard 精确命中越界的"铜钥匙"；sync_check 列出 7 项失步并回填 plan |
| `--engine ebooklib` / `--engine pandoc` 强制 | 缺依赖时给出明确错误并 exit 1，不再 traceback |

---

## 四、尚未修改 / 暂缓实施的项及其技术权衡

| # | 项 | 暂缓原因与权衡 |
|---|---|---|
| D1 | **`sync_check --fix` 自动回写 00/01/02/03 四个 Markdown** | 技术上可做（TODO 勾选、时间线追加行、追踪表刷新均可由 notes meta 派生），但这四个文件是 Agent 与人类共同编辑的自由文本，脚本改写有覆盖手工内容的风险。当前策略：脚本只报告 ❌，只回写机器专属的 plan.json。建议先在 D4（notes 派生）成熟后再开放 `--fix-md`，且必须先 `git diff` 可回滚。 |
| D2 | **the-transfer-kid 实战项目本身的失步修复**（补 Ch.21–24 notes、补 10 章 POV 标记、清理 03 中的文风段） | 属于另一个仓库的内容创作工作，且补 notes 需要读正文（按新 SKILL"Notes 回填"流程逐章执行）。本次只提供工具与流程，不代写。 |
| D3 | **语义级 POV 检测** | 需要 LLM 调用（或至少 NER + 共指消解），超出"零依赖脚本"边界；见第五节 A1 方案。词法检测已作为第一道防线落地。 |
| D4 | **notes → 追踪表 / 时间线自动派生** | 依赖所有历史 notes 都含 meta 块；旧项目需先回填。`novel_common.parse_meta_block` 已就绪，派生逻辑可在 40 行内实现，留给下一轮。 |
| D5 | **多 Agent 并行锁协议** | 涉及文件锁、章节范围分配、合并冲突策略，属于架构变更；见第五节 A2。 |
| D6 | **旧模板字段的兼容迁移脚本**（如把列表式信息墙转为表格） | 信息墙的"禁用关键词"必须人工提炼，无法自动迁移；提供的模板注释已说明填法。 |
| D7 | **章节标题中"Chapter NN"之外的变体**（如 `Ch. 3` / `第三章` 汉字数字） | 解析器只接受阿拉伯数字。汉字数字转换会引入歧义（"第十一章"vs"第一章"前缀），且模板已明确契约；如需支持可在 `HEADING_RE` 处扩展。 |
| D8 | **`user-preferences.json` 的读取自动化** | SKILL Phase 0 已声明读取位置与语义；未写脚本是因为该文件只影响 Phase 1 对话默认值，不影响任何门禁。 |

---

## 五、下一步长期迭代建议与实施步骤指引

### A1 · 语义级 POV 越界检测器（两级流水线）

**目标**：捕获词法检测抓不到的转述、暗示与推理式越界（例如 POV 角色"莫名知道"某人昨晚在哪）。

1. **输入契约**：复用 03 信息墙表 + 当前章 notes meta（pov / present）。`pov_guard.py --json` 输出候选段落（命中行 ± 2 段）与"零命中但含信息墙事实相关角色名"的段落。
2. **判定层**：新增 `scripts/pov_judge.py`，把每个候选段落 + 该 POV 的"不知道的事实"列表拼成一个短 Prompt（≤ 1.5k tokens），要求模型输出 `{leak: bool, reason, quote}`。模型接口通过环境变量 `NOVEL_JUDGE_CMD`（任意 CLI，stdin→stdout JSON）注入，保持仓库零 SDK 依赖。
3. **门禁接入**：SKILL R5 增加"pov_judge 判定 leak=true 的段落必须改稿或在信息墙填写解禁章节"；`sync_check` 读取 `pov_judge` 的缓存结果文件 `.novel-cache/pov-NN.json`，缺失或过期时 ❌。
4. **评估**：用 the-transfer-kid 的 Ch.17–19（Justin 视角、Zack 秘密最密集）做黄金集，先跑词法层统计误报率，再跑判定层统计漏报率。

### A2 · 多 Agent 并行章节写作分工锁协议

**约束前提**：5 大控制文件是共享状态，并行写作的冲突点只有它们；正文与 notes 天然按章隔离。

1. **章节范围分配**：主 Agent（Planner）在 plan.json 新增 `assignments: [{agent, chapters:[a..b], leaseUntil}]`。子 Agent 只能写自己范围内的 `chapter-NN.md` / `-notes.md`。范围之间必须存在**已完成的 notes 边界**（子 Agent B 的起始章 -1 已有 notes），否则不可分配。
2. **控制文件锁**：引入 `.novel-lock/<file>.lock`（内容：agent、章号、时间戳、TTL）。子 Agent 在 Step 4 前 `acquire`，超时 TTL 自动失效；`sync_check` 检测过期锁并清理。锁粒度按文件，不按段落——简单可靠。
3. **写入协议（append-only）**：子 Agent 对 00/01/02/03 只允许**追加**（TODO 勾选、`Ch.NN 演进` 行、时间线行、追踪表更新行），不得改写他人段落。追踪表改为 append-only 事件日志（`| Ch | 角色 | 形式 |`），由 `preflight.py` 聚合为"上次出场"视图——这同时解决了 D4。
4. **信息墙写权限**：只有 Planner 可新增信息墙行；子 Agent 若在正文中制造了新秘密，必须写进 notes 的"POV 知识变更"，由 Planner 在合并时提升到 03。
5. **合并与校验**：每个子 Agent 范围完成后，Planner 运行 `sync_check.py --fix` + `pov_guard.py --all`；跨范围的时间线连续性由 `02` 的 D+N 单调性检查（新增校验：后一章 `day` 不得早于前一章，闪回除外）。
6. **实施顺序**：先落地 3（append-only + 事件日志），它单 Agent 也受益；再落地 2（锁）；最后 1/5（分配与合并）。

### A3 · Markdown 自动回写（`sync_check --fix-md`）

1. 每个可回写区域用 HTML 注释锚定：`<!-- novel:todo -->…<!-- /novel:todo -->`、`<!-- novel:timeline -->`、`<!-- novel:tracker -->`。
2. 脚本只在锚点之间重写，锚点之外一字不动；重写前把原段落写入 `.novel-cache/backup/<file>.<ts>`。
3. 数据源全部来自 notes meta（day / present / mentioned）与 plan.json，保证"notes 是唯一真源"的因果方向。

### A4 · `novel doctor` 一键体检与 CI

- 新增 `scripts/doctor.py`：依次运行 `sync_check` → `check_chapter_wordcount --all` → `pov_guard --all` → `export_epub --book --engine builtin --out /tmp`，汇总为一张表并给出总退出码。
- 在小说仓库添加 GitHub Action：push 时运行 doctor，失败即阻断；这样"5 文件对齐"从 Agent 自觉变成仓库级不变量。

### A5 · Token 预算可观测

- `preflight.py --json` 已输出各段内容；下一步给每段附 `approxTokens`（按 zh 1.5 字/token、en 0.75 词/token 估算），并在 SKILL 中规定上下文包上限（建议 ≤ 4k tokens）。超限时优先截断"既成事实"为最近 N 条、上章 notes 只保留第 2/3 节。

### A6 · 面向 100 章级别的 notes 分层

- 每 10 章由 Agent 生成一份 `arc-NN-notes.md`（弧线级摘要，≤ 300 字），`preflight` 在第 N 章只带：本弧线摘要 + 上一章 notes。这样 Pre-Flight 成本与总章数解耦，是 Notes-Only 的自然延伸。

---

*报告生成于 v2 重构完成后；所有脚本已在 Python 3.11（无第三方包）环境下回归通过。*
