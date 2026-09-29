#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pov_guard.py — POV 信息墙词法泄漏检测器（第一道防线，非语义判定）

用法：
  python3 scripts/pov_guard.py <chapter-NN.md>
  python3 scripts/pov_guard.py <project-dir> --all
  python3 scripts/pov_guard.py <chapter-NN.md> --pov Justin   # 覆盖 POV

原理：
  读取 03-global-notes.md 的「POV 信息墙」表：
    | POV 角色 | 不知道的事实 | 禁用关键词 | 来源章节 | 解禁章节 |
  对于 POV = X 的章节，若正文中出现 X 不应知道的事实的「禁用关键词」，即报告命中（含行号与上下文）。
  解禁章节 <= 当前章 的行自动失效（秘密已在该章向 X 揭示）。

局限：
  这是词法级检测（关键词命中），只能捕获「直接提到不该知道的名字/物件」的硬泄漏，
  无法判断转述、暗示或推理式越界。语义级检测请见 AUDIT_REPORT.md「架构扩展」。
  命中 ≠ 一定违规（例如 POV 角色在对话中被他人首次告知），需人工/Agent 复核后放行。

退出码：0 无命中；1 有命中；2 参数/文件错误。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novel_common import (  # noqa: E402
    find_project_root,
    list_chapters,
    parse_chapter,
    parse_pov_wall,
    read_text,
)


def scan_chapter(path: Path, wall: list[dict], pov_override: str | None) -> tuple[list[dict], str]:
    ch = parse_chapter(path)
    pov = pov_override or ch["pov"]
    hits: list[dict] = []
    if not pov:
        return hits, ""
    n = ch["number"] or 0
    rules = [
        w for w in wall
        if (w["holder"].lower() in pov.lower() or pov.lower() in w["holder"].lower())
        and w["keywords"]
        and (w["until"] is None or n < w["until"])
    ]
    lines = ch["body"].splitlines()
    for rule in rules:
        for kw in rule["keywords"]:
            is_ascii = all(ord(c) < 128 for c in kw)
            pat = re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE) if is_ascii else re.compile(re.escape(kw))
            for i, line in enumerate(lines, 1):
                m = pat.search(line)
                if m:
                    s = max(0, m.start() - 40)
                    hits.append(
                        {
                            "line": i,
                            "keyword": kw,
                            "fact": rule["fact"],
                            "context": line[s : m.end() + 40].strip(),
                        }
                    )
    return hits, pov


def main() -> int:
    ap = argparse.ArgumentParser(description="POV 信息墙词法泄漏检测")
    ap.add_argument("target", help="chapter-NN.md 或项目目录（配合 --all）")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--pov", help="覆盖正文 POV 标记")
    args = ap.parse_args()

    target = Path(args.target).resolve()
    root = find_project_root(target)
    if root is None:
        print("❌ 未找到项目根（需含 04-generation-plan.json 或 00-outline.md）")
        return 2
    gn = root / "03-global-notes.md"
    if not gn.exists():
        print("❌ 缺少 03-global-notes.md")
        return 2
    files = [p for _, p in list_chapters(root)] if (args.all or target.is_dir()) else [target]
    if not files:
        print("❌ 未找到可检查的 chapter-NN.md")
        return 2
    for p in files:
        if not parse_chapter(p)["pov"] and not args.pov:
            print(f"❌ {p.name}: 缺少 *(POV: …)* 标记，无法进行 POV 检查")
            return 1
    wall = parse_pov_wall(read_text(gn))
    if not wall:
        print("⚠️ 03-global-notes.md 中未解析到 POV 信息墙表，词法检查未执行；请人工复核信息边界")
        return 1

    total_hits = 0
    for p in files:
        hits, pov = scan_chapter(p, wall, args.pov)
        if not pov:
            print(f"⚠️  {p.name}: 缺少 *(POV: …)* 标记，跳过（这本身是 sync_check 的 ❌ 项）")
            continue
        if hits:
            total_hits += len(hits)
            print(f"❌ {p.name} (POV={pov}) 命中 {len(hits)} 处：")
            for h in hits:
                print(f"   L{h['line']:>4} [{h['keyword']}] ← {h['fact']}")
                print(f"         …{h['context']}…")
        else:
            print(f"✅ {p.name} (POV={pov}) 无词法泄漏")
    print(f"— files={len(files)} hits={total_hits}")
    return 1 if total_hits else 0


if __name__ == "__main__":
    sys.exit(main())
