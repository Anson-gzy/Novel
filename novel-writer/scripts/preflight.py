#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
preflight.py — Step 1 写前自检：生成「紧凑上下文包」，替代整读 5 大控制文件

用法：
  python3 scripts/preflight.py <project-dir> [N]        # N 缺省 = 下一待写章节
  python3 scripts/preflight.py <project-dir> N --json

只输出写第 N 章真正需要的切片：
  1. 计划元数据（语言、字数基线、POV 规则、导出目录）
  2. 00-outline.md 中第 N 章 Brief（切片，不整读 50KB 大纲）
  3. 上一章 chapter-(N-1)-notes.md 全文（Notes-Only 的唯一合法前文来源）
  4. 03-global-notes.md：既成事实段 + 当前 POV 的信息墙行 + 配角活跃度预警
  5. 02-timeline.md：最近 2 行时间线 + 全部有效约束 + 未解决冲突
  6. 健康检查：上一章 notes 是否缺失、5 文件是否齐全
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novel_common import (  # noqa: E402
    CONTROL_FILES,
    extract_chapter_brief,
    list_chapters,
    load_plan,
    notes_path_for,
    parse_pov_wall,
    parse_tracker,
    plan_language,
    plan_limits,
    read_text,
    timeline_constraints,
    timeline_open_conflicts,
    timeline_rows,
)

STALE_AFTER = 4  # 配角超过 N 章未露面触发预警


def section(title: str) -> str:
    return f"\n## {title}\n"


def extract_canon_section(text: str) -> str:
    """切出 03-global-notes.md 中「既成事实」章节（第一个二级标题到下一个二级标题）。"""
    m = re.search(r"^##\s.*?(既成事实|Canon|核心设定).*$", text, re.M | re.IGNORECASE)
    if not m:  # 旧版布局：既成事实只是某个二级标题下的一个列表项
        m = re.search(r"^.*(既成事实|重大剧情事实|Canon Facts).*$", text, re.M | re.IGNORECASE)
        if not m:
            return ""
    rest = text[m.end():]
    nxt = re.search(r"^##\s", rest, re.M)
    return (m.group(0) + rest[: nxt.start() if nxt else None]).strip()


def guess_pov(brief: str, plan_entry: dict | None) -> str:
    """Brief 是待写章节的权威规划，优先于 plan.json 中可能残留的占位值。"""
    m = re.search(r"POV[^:：\n]*[:：]\s*\**\s*([^\n\*\|]+)", brief, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    if plan_entry and plan_entry.get("pov"):
        return str(plan_entry["pov"])
    return ""


def build_packet(root: Path, n: int | None) -> dict:
    plan = load_plan(root) or {}
    chapters = list_chapters(root)
    done = [c for c, _ in chapters]
    if n is None:
        n = (max(done) + 1) if done else 1
    lang = plan_language(plan)
    lo, hi = plan_limits(plan, lang)
    entry = next((c for c in plan.get("chapters", []) if c.get("chapterNumber") == n), None)

    outline = read_text(root / "00-outline.md") if (root / "00-outline.md").exists() else ""
    gnotes = read_text(root / "03-global-notes.md") if (root / "03-global-notes.md").exists() else ""
    tl = read_text(root / "02-timeline.md") if (root / "02-timeline.md").exists() else ""

    brief = extract_chapter_brief(outline, n)
    pov = guess_pov(brief, entry)

    prev_notes_text, prev_notes_missing = "", []
    if n > 1:
        pn = notes_path_for(root, n - 1)
        if pn.exists():
            prev_notes_text = read_text(pn).strip()
        else:
            prev_notes_missing.append(pn.name)

    wall = parse_pov_wall(gnotes)
    wall_rows = [
        w for w in wall
        if (not pov or w["holder"].lower() in pov.lower() or pov.lower() in w["holder"].lower())
        and (w["until"] is None or n < w["until"])
    ]

    tracker = parse_tracker(gnotes)
    warnings = []
    for t in tracker:
        if t["last"] is None:
            warnings.append(f"{t['name']}：尚未出场（寻找自然切口）")
        elif n - t["last"] > STALE_AFTER:
            warnings.append(f"{t['name']}：已 {n - t['last']} 章未露面（上次 Ch.{t['last']:02d}，{t['form']}）")

    rows = timeline_rows(tl)
    recent_rows = [" | ".join(r["cells"]) for r in rows if r["chapter"] is not None][-2:]
    constraints = [" | ".join(r) for r in timeline_constraints(tl) if "✅" in " ".join(r) or "有效" in " ".join(r)]
    conflicts = [" | ".join(r) for r in timeline_open_conflicts(tl)]

    missing_files = [f for f in CONTROL_FILES if not (root / f).exists()]
    health = []
    if missing_files:
        health.append(f"缺少控制文件：{', '.join(missing_files)}")
    if prev_notes_missing:
        health.append(f"上一章 notes 缺失：{', '.join(prev_notes_missing)} → 先按 SKILL.md「Notes 回填」流程补齐，再动笔")
    if not brief:
        health.append(f"00-outline.md 中找不到第 {n} 章 Brief → 先补写 Brief")
    if n in done:
        health.append(f"chapter-{n:02d}.md 已存在 → 这是重写；按 SKILL.md「重写与回滚」流程执行")

    return {
        "chapter": n,
        "language": lang,
        "wordRange": [lo, hi],
        "pov": pov,
        "povRule": plan.get("povRule", ""),
        "exportDir": plan.get("exportDir", ""),
        "brief": brief,
        "prevNotes": prev_notes_text,
        "canon": extract_canon_section(gnotes),
        "povWall": wall_rows,
        "trackerWarnings": warnings,
        "timelineRecent": recent_rows,
        "timelineConstraints": constraints,
        "openConflicts": conflicts,
        "health": health,
    }


def render(p: dict) -> str:
    out = [f"# PRE-FLIGHT · Chapter {p['chapter']:02d}"]
    out.append(
        f"lang={p['language']} · words={p['wordRange'][0]}–{p['wordRange'][1]} · POV={p['pov'] or '（未指定，按 Brief）'}"
        + (f" · rule={p['povRule']}" if p["povRule"] else "")
    )
    if p["health"]:
        out.append(section("⛔ 健康检查（先处理再动笔）"))
        out += [f"- {h}" for h in p["health"]]
    out.append(section("1. 本章 Brief（00-outline 切片）"))
    out.append(p["brief"] or "（无）")
    out.append(section("2. 上一章 Notes（唯一合法前文来源）"))
    out.append(p["prevNotes"] or "（第 1 章，无前文）")
    out.append(section("3. 既成事实（03-global-notes）"))
    out.append(p["canon"] or "（无）")
    out.append(section(f"4. POV 信息墙 · {p['pov'] or '全部'} 不知道的事"))
    if p["povWall"]:
        for w in p["povWall"]:
            kw = f"（禁用词：{', '.join(w['keywords'])}）" if w["keywords"] else ""
            src = f" [Ch.{w['since']:02d}]" if w["since"] else ""
            out.append(f"- {w['holder']} ✗ {w['fact']}{kw}{src}")
    else:
        out.append("（无匹配行 — 若为多视角作品请检查 03 信息墙表是否填写）")
    out.append(section("5. 配角活跃度预警"))
    out += [f"- ⚠️ {w}" for w in p["trackerWarnings"]] or ["- 无"]
    out.append(section("6. 时间线"))
    out += [f"- 最近：{r}" for r in p["timelineRecent"]] or ["- （无记录）"]
    out += [f"- 约束：{c}" for c in p["timelineConstraints"]]
    out += [f"- ❗未解决冲突：{c}" for c in p["openConflicts"]]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Novel Writer Pre-Flight 上下文包")
    ap.add_argument("project", help="小说项目目录")
    ap.add_argument("chapter", nargs="?", type=int, help="章节号（缺省=下一章）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = Path(args.project).resolve()
    if not root.is_dir():
        print(f"❌ 目录不存在: {root}")
        return 2
    packet = build_packet(root, args.chapter)
    print(json.dumps(packet, ensure_ascii=False, indent=2) if args.json else render(packet))
    return 1 if packet["health"] else 0


if __name__ == "__main__":
    sys.exit(main())
