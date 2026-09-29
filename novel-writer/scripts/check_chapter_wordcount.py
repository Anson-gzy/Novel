#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_chapter_wordcount.py — 双语字数门禁（中文按汉字计，英文按词计）

用法：
  python3 scripts/check_chapter_wordcount.py <chapter-NN.md> [--min N] [--max N] [--lang zh|en]
  python3 scripts/check_chapter_wordcount.py --all <project-dir> [--min N] [--max N] [--json]

规则：
  - 语言与上下限优先读取项目 04-generation-plan.json（language / minWordsPerChapter / maxWordsPerChapter）；
    找不到时按文本自动检测语言并使用默认基线：zh 3000–5000，en 1500–2500。
  - 统计前自动剔除标题行、POV 标记与 Markdown 语法符号。
  - 任一章节低于下限 → 退出码 1（可直接作为 Step 2 → Step 3 的门禁）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novel_common import (  # noqa: E402
    count_words,
    detect_language,
    find_project_root,
    list_chapters,
    load_plan,
    parse_chapter,
    plan_language,
    plan_limits,
)


def check_one(path: Path, lang: str | None, lo: int | None, hi: int | None) -> dict:
    if not path.exists():
        return {"file": str(path), "exists": False, "status": "error", "message": "文件不存在"}
    ch = parse_chapter(path)
    root = find_project_root(path)
    plan = load_plan(root) if root else None
    lang = lang or (plan_language(plan) if plan else detect_language(ch["body"]))
    p_lo, p_hi = plan_limits(plan, lang)
    lo, hi = lo or p_lo, hi or p_hi
    wc = count_words(ch["body"], lang)
    status = "pass" if lo <= wc <= hi else "fail"
    over = wc > hi
    return {
        "file": str(path),
        "chapter": ch["number"],
        "title": ch["title"],
        "pov": ch["pov"],
        "exists": True,
        "lang": lang,
        "word_count": wc,
        "min": lo,
        "max": hi,
        "status": status,
        "over_max": over,
    }


def fmt(r: dict) -> str:
    if not r.get("exists"):
        return f"❌ {r['file']} — {r['message']}"
    icon = "✅" if r["status"] == "pass" else "⚠️"
    unit = "字" if r["lang"] == "zh" else "词"
    line = f"{icon} {Path(r['file']).name}  {r['word_count']:,} {unit}  (基线 {r['min']}–{r['max']})"
    if r["status"] == "fail" and r["word_count"] < r["min"]:
        line += f"  ← 不足，至少需补 {r['min'] - r['word_count']} {unit}"
    elif r["over_max"]:
        line += "  ← 超过上限，必须拆分或收束"
    if not r["pov"]:
        line += "  | 缺少 *(POV: …)* 标记"
    return line


def main() -> int:
    ap = argparse.ArgumentParser(description="Novel Writer 双语字数门禁")
    ap.add_argument("target", nargs="?", help="chapter-NN.md 文件")
    ap.add_argument("--all", metavar="DIR", help="检查目录下全部 chapter-NN.md")
    ap.add_argument("--min", type=int, help="覆盖下限")
    ap.add_argument("--max", type=int, help="覆盖上限")
    ap.add_argument("--lang", choices=["zh", "en"], help="覆盖语言")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    # 兼容旧用法：位置参数第二项为最小字数
    ap.add_argument("legacy_min", nargs="?", type=int, help=argparse.SUPPRESS)
    args = ap.parse_args()

    lo = args.min or args.legacy_min
    results = []
    if args.all:
        root = Path(args.all)
        if not root.is_dir():
            print(f"❌ 目录不存在: {root}")
            return 2
        for _, p in list_chapters(root):
            results.append(check_one(p, args.lang, lo, args.max))
        if not results:
            print(f"⚠️ {root} 下未找到 chapter-NN.md")
            return 2
    elif args.target:
        results.append(check_one(Path(args.target), args.lang, lo, args.max))
    else:
        ap.print_help()
        return 2

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(fmt(r))
        ok = [r for r in results if r.get("exists")]
        total = sum(r["word_count"] for r in ok)
        failed = [r for r in ok if r["status"] == "fail"]
        if len(results) > 1:
            print(f"— 共 {len(ok)} 章 | 达标 {len(ok) - len(failed)} | 不足 {len(failed)} | 总计 {total:,}")
    return 1 if any(r.get("status") != "pass" or r.get("over_max") for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
