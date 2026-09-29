#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_check.py — Step 4 「5 文件全量对齐」自动校验器（可选自动修复 plan.json）

用法：
  python3 scripts/sync_check.py <project-dir>            # 只校验，退出码 1 = 有失步
  python3 scripts/sync_check.py <project-dir> --fix      # 同时回填/修正 04-generation-plan.json
  python3 scripts/sync_check.py <project-dir> --chapter N  # 只看第 N 章

校验矩阵（每一章 chapter-NN.md）：
  正文   : 首行标题格式、*(POV)* 标记、字数达标
  notes  : chapter-NN-notes.md 存在、```meta 块存在、meta.pov 与正文一致、meta.chapter == NN
  00     : TODO 列表中该章已勾选 [x]
  01     : 出现 "Ch.NN" 演进记录（至少一条）或该章无新弧光（仅提示）
  02     : 全局时间线表存在该章行
  03     : 配角追踪表中最大章节号 >= NN（追踪表已刷新）
  04     : plan.chapters 含该章、status=completed、wordCount 与实际偏差 <= 5%
  EPUB   : 若 plan.exportDir 或 chapters[].epubPath 可解析，则检查文件存在（仅提示）

--fix 只写 04-generation-plan.json（其它 4 个 Markdown 由 Agent 按报告修改），不会碰任何正文。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novel_common import (  # noqa: E402
    CONTROL_FILES,
    count_words,
    list_chapters,
    load_plan,
    notes_path_for,
    now_iso,
    outline_todo_status,
    parse_chapter,
    parse_notes,
    parse_tracker,
    plan_language,
    plan_limits,
    read_text,
    save_plan,
    timeline_rows,
)


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warns: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)


def main() -> int:
    ap = argparse.ArgumentParser(description="Novel Writer 5 文件对齐校验")
    ap.add_argument("project")
    ap.add_argument("--fix", action="store_true", help="回填 04-generation-plan.json")
    ap.add_argument("--chapter", type=int, help="仅校验指定章")
    ap.add_argument("--finalize-rewrite", action="store_true", help="仅在重写稿已验证时将 rewriting 标记为 completed")
    args = ap.parse_args()
    if args.finalize_rewrite and not (args.fix and args.chapter):
        ap.error("--finalize-rewrite 必须与 --fix --chapter N 一起使用")

    root = Path(args.project).resolve()
    rep = Report()
    for f in CONTROL_FILES:
        if not (root / f).exists():
            rep.err(f"缺少控制文件 {f}")
    plan = load_plan(root) or {
        "version": 2,
        "novelName": root.name,
        "language": "zh",
        "status": "in_progress",
        "createdAt": now_iso(),
        "chapters": [],
    }
    lang = plan_language(plan)
    lo, hi = plan_limits(plan, lang)

    outline = read_text(root / "00-outline.md") if (root / "00-outline.md").exists() else ""
    chars = read_text(root / "01-characters.md") if (root / "01-characters.md").exists() else ""
    tl = read_text(root / "02-timeline.md") if (root / "02-timeline.md").exists() else ""
    gn = read_text(root / "03-global-notes.md") if (root / "03-global-notes.md").exists() else ""

    todo = outline_todo_status(outline)
    tl_chapters = {r["chapter"] for r in timeline_rows(tl) if r["chapter"] is not None}
    tracker_max = max([t["last"] or 0 for t in parse_tracker(gn)] or [0])
    plan_by_no = {c.get("chapterNumber"): c for c in plan.get("chapters", [])}
    plan_numbers = [c.get("chapterNumber") for c in plan.get("chapters", [])]
    duplicates = sorted({n for n in plan_numbers if plan_numbers.count(n) > 1 and n is not None})
    for n in duplicates:
        rep.err(f"04-generation-plan.json 存在重复 chapterNumber={n}，拒绝自动修复歧义数据")

    chapters = list_chapters(root)
    file_numbers = [n for n, _ in chapters]
    duplicate_file_numbers = sorted({n for n in file_numbers if file_numbers.count(n) > 1})
    for n in duplicate_file_numbers:
        rep.err(f"正文文件存在重复章节号 Ch.{n:02d}，拒绝自动修复")
    has_duplicates = bool(duplicates or duplicate_file_numbers)
    global_structure_valid = not has_duplicates and all((root / f).exists() for f in CONTROL_FILES)
    manuscript_numbers = set(file_numbers)
    for entry in ([] if args.chapter else plan.get("chapters", [])):
        n = entry.get("chapterNumber")
        if entry.get("status") in {"draft", "completed", "rewriting"} and n not in manuscript_numbers:
            rep.err(f"Ch.{n:02d} 计划状态为 {entry.get('status')} 但缺少正文文件")
    if args.chapter:
        chapters = [(n, p) for n, p in chapters if n == args.chapter]
        if not chapters:
            rep.err(f"chapter-{args.chapter:02d}.md 不存在")

    changed = False
    chapter_valid_by_no = {}
    for n, path in chapters:
        tag = f"Ch.{n:02d}"
        errors_before = len(rep.errors)
        ch = parse_chapter(path)
        wc = count_words(ch["body"], lang)

        # 正文
        if not ch["heading"]:
            rep.err(f"{tag} 正文缺少首行标题（# 第 NN 章：标题 / # Chapter NN: Title）")
        else:
            heading_match = re.match(r"^#\s+(?:第\s*0*(\d+)\s*章|Chapter\s*0*(\d+)\b)", ch["heading"], re.IGNORECASE)
            heading_number = int(heading_match.group(1) or heading_match.group(2)) if heading_match else None
            if heading_number != n:
                rep.err(f"{tag} 标题章节号与文件名不一致：标题={heading_number or '无法解析'}，文件={n}")
        if not ch["pov"]:
            rep.err(f"{tag} 正文缺少 *(POV: 角色)* 标记")
        if wc < lo:
            rep.err(f"{tag} 字数 {wc} 低于下限 {lo}")
        elif wc > hi:
            rep.err(f"{tag} 字数 {wc} 超过上限 {hi}")

        # notes
        npath = notes_path_for(root, n, path)
        meta = {}
        if not npath.exists():
            rep.err(f"{tag} 缺少 {npath.name}（Notes-Only 链条断裂，后续章节将无法安全续写）")
        else:
            meta = parse_notes(npath)["meta"]
            if not meta:
                rep.err(f"{tag} {npath.name} 缺少 ```meta 块（机器不可读，POV/时间线无法校验）")
            else:
                if str(meta.get("chapter", "")).lstrip("0") != str(n):
                    rep.err(f"{tag} notes meta.chapter={meta.get('chapter')} 与文件名不符")
                if not meta.get("pov"):
                    rep.err(f"{tag} notes meta 缺少 pov")
                elif ch["pov"] and str(meta["pov"]).lower() != ch["pov"].lower():
                    rep.err(f"{tag} notes meta.pov={meta['pov']} 与正文 POV={ch['pov']} 不一致")
                if not meta.get("day"):
                    rep.err(f"{tag} notes meta 缺少 day（D+N 时间锚点）")

        # 00 outline
        if n not in todo:
            rep.err(f"{tag} 00-outline TODO 列表中无该章条目")
        elif not todo[n]:
            rep.err(f"{tag} 00-outline TODO 未勾选 [x]")

        # 01 characters
        if not re.search(rf"Ch\.?\s*0?{n}\b", chars):
            rep.warn(f"{tag} 01-characters 未见 'Ch.{n:02d}' 演进记录（若本章无弧光变化可忽略）")

        # 02 timeline
        if n not in tl_chapters:
            rep.err(f"{tag} 02-timeline 全局时间线表缺少该章行")

        # 03 tracker
        if tracker_max < n:
            rep.err(f"{tag} 03-global-notes 配角追踪表最大章节为 Ch.{tracker_max:02d}，未刷新到本章")

        chapter_valid = global_structure_valid and len(rep.errors) == errors_before
        chapter_valid_by_no[n] = chapter_valid

        # 04 plan
        entry = plan_by_no.get(n)
        desired = {
            "chapterNumber": n,
            "title": ch["title"],
            "pov": ch["pov"] or (entry or {}).get("pov", ""),
            "filePath": path.name,
            "notesPath": npath.name,
            "status": "completed" if chapter_valid else "draft",
            "wordCount": wc,
            "wordCountPass": lo <= wc <= hi,
            "day": meta.get("day", (entry or {}).get("day", "")),
        }
        if entry is None:
            rep.err(f"{tag} 04-generation-plan.json 无该章条目")
            if args.fix:
                entry = {"retryCount": 0}
                plan.setdefault("chapters", []).append(entry)
                plan_by_no[n] = entry
                changed = True
        else:
            if entry.get("status") == "rewriting" and not args.finalize_rewrite:
                pass
            elif entry.get("status") != desired["status"]:
                rep.err(f"{tag} plan.status={entry.get('status')} 应为 {desired['status']}")
            pw = int(entry.get("wordCount") or 0)
            if pw == 0 or abs(pw - wc) / max(wc, 1) > 0.05:
                rep.err(f"{tag} plan.wordCount={pw} 与实际 {wc} 偏差 >5%")
        if args.fix and entry is not None and not has_duplicates:
            for k, v in desired.items():
                if k == "status" and entry.get("status") == "rewriting" and (not args.finalize_rewrite or not chapter_valid):
                    continue
                if entry.get(k) != v:
                    entry[k] = v
                    changed = True

        # EPUB
        epub = (entry or {}).get("epubPath")
        if epub and not Path(epub).expanduser().exists():
            rep.warn(f"{tag} plan.epubPath 指向的文件不存在：{epub}")
        elif not epub and plan.get("exportDir"):
            cand = Path(plan["exportDir"]).expanduser() / f"{path.stem}.epub"
            if not cand.exists():
                rep.warn(f"{tag} 未发现 EPUB：{cand}")

    # plan 级别
    total = plan.get("totalChapters")
    done_n = sum(1 for c in plan.get("chapters", []) if c.get("status") == "completed")
    expected_set = set(range(1, int(total) + 1)) if total else set()
    plan_set = {c.get("chapterNumber") for c in plan.get("chapters", [])}
    completed_set = {c.get("chapterNumber") for c in plan.get("chapters", []) if c.get("status") == "completed"}
    book_ready = bool(
        total and not args.chapter and manuscript_numbers == expected_set
        and plan_set == expected_set and completed_set == expected_set
        and not any(c.get("status") == "rewriting" for c in plan.get("chapters", []))
        and all(chapter_valid_by_no.get(n, False) for n in expected_set)
        and global_structure_valid
    )
    if plan.get("status") == "completed" and not book_ready:
        rep.err("plan.status=completed 但全书仍缺章节、存在重写/错误，或本次仅校验单章")
    if plan.get("completedChapters") is not None and int(plan.get("completedChapters") or 0) != done_n:
        rep.err(f"plan.completedChapters={plan.get('completedChapters')} 与实际 {done_n} 不一致")
    if plan.get("totalWordCount") is not None:
        actual_total = sum(int(c.get("wordCount") or 0) for c in plan.get("chapters", []))
        if int(plan.get("totalWordCount") or 0) != actual_total:
            rep.err(f"plan.totalWordCount={plan.get('totalWordCount')} 与章节合计 {actual_total} 不一致")
    if args.fix and not has_duplicates:
        done_n = sum(1 for c in plan.get("chapters", []) if c.get("status") == "completed")
        plan["chapters"].sort(key=lambda c: c.get("chapterNumber", 0))
        plan["completedChapters"] = done_n
        plan["totalWordCount"] = sum(int(c.get("wordCount") or 0) for c in plan["chapters"])
        if book_ready:
            plan["status"] = "completed"
        else:
            plan["status"] = "in_progress"
        changed = True
        save_plan(root, plan)

    # 输出
    print(f"# SYNC CHECK · {root.name} · {len(chapters)} chapters · lang={lang}")
    for e in rep.errors:
        print(f"❌ {e}")
    for w in rep.warns:
        print(f"⚠️  {w}")
    if changed:
        print("🛠  已回填 04-generation-plan.json（其余 Markdown 请按上方 ❌ 项手动同步）")
    print(f"— errors={len(rep.errors)} warnings={len(rep.warns)}")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
