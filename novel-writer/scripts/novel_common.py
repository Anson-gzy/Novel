#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
novel_common.py — Novel Writer 共享解析库（零第三方依赖）

所有脚本（preflight / sync_check / pov_guard / check_chapter_wordcount / export_epub）
共用这里的：项目定位、章节枚举、标题/POV 解析、双语字数统计、控制文件表格解析。

约定（与 SKILL.md 保持一致）：
- 正文文件：chapter-NN.md（NN 两位以上数字），notes：chapter-NN-notes.md
- 正文首行：`# 第 NN 章：标题` 或 `# Chapter NN: Title`
- 正文次行：`*(POV: 角色名)*`
- notes 顶部包含一个 ```meta 围栏块（key: value，列表用逗号分隔）
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 控制台编码（Windows）
# ---------------------------------------------------------------------------
if sys.platform == "win32":  # pragma: no cover
    for _stream in ("stdout", "stderr"):
        _s = getattr(sys, _stream)
        if hasattr(_s, "buffer"):
            setattr(sys, _stream, io.TextIOWrapper(_s.buffer, encoding="utf-8", errors="replace"))

PLAN_FILE = "04-generation-plan.json"
CONTROL_FILES = [
    "00-outline.md",
    "01-characters.md",
    "02-timeline.md",
    "03-global-notes.md",
    PLAN_FILE,
]

CHAPTER_FILE_RE = re.compile(r"^chapter-(\d{1,3})\.md$", re.IGNORECASE)
NOTES_FILE_RE = re.compile(r"^chapter-(\d{1,3})-notes\.md$", re.IGNORECASE)
HEADING_RE = re.compile(
    r"^#\s*(?:第\s*(\d+)\s*章\s*[：:]\s*(.*?)|Chapter\s*(\d+)\s*[:：]\s*(.*?))\s*$",
    re.IGNORECASE,
)
POV_RE = re.compile(r"[\*_]*[\(（]\s*POV\s*[:：]\s*([^\)）]+?)\s*[\)）][\*_]*", re.IGNORECASE)
CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
EN_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’\-][A-Za-z0-9]+)*")

DEFAULT_LIMITS = {"zh": (3000, 5000), "en": (1500, 2500)}


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def find_project_root(start: Path) -> Optional[Path]:
    """从 start 向上查找含 04-generation-plan.json 或 00-outline.md 的目录。"""
    p = start.resolve()
    if p.is_file():
        p = p.parent
    for cand in [p, *p.parents]:
        if (cand / PLAN_FILE).exists() or (cand / "00-outline.md").exists():
            return cand
    return None


def load_plan(root: Path) -> Optional[dict]:
    fp = root / PLAN_FILE
    if not fp.exists():
        return None
    try:
        return json.loads(read_text(fp))
    except json.JSONDecodeError as e:
        raise SystemExit(f"❌ {fp} 不是合法 JSON：{e}")


def save_plan(root: Path, plan: dict) -> None:
    plan["updatedAt"] = now_iso()
    target = root / PLAN_FILE
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(root))
    try:
        with open(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def plan_language(plan: Optional[dict], fallback: str = "zh") -> str:
    lang = (plan or {}).get("language") or fallback
    return "en" if str(lang).lower().startswith("en") else "zh"


def plan_limits(plan: Optional[dict], lang: str) -> Tuple[int, int]:
    lo, hi = DEFAULT_LIMITS.get(lang, DEFAULT_LIMITS["zh"])
    if plan:
        lo = int(plan.get("minWordsPerChapter") or lo)
        hi = int(plan.get("maxWordsPerChapter") or hi)
    return lo, hi


# ---------------------------------------------------------------------------
# 章节枚举与解析
# ---------------------------------------------------------------------------
def chapter_number_of(path: Path) -> Optional[int]:
    m = CHAPTER_FILE_RE.match(path.name)
    return int(m.group(1)) if m else None


def list_chapters(root: Path) -> List[Tuple[int, Path]]:
    """只返回正文（排除 *-notes.md），按章节号数值排序。"""
    out = []
    for p in root.iterdir():
        n = chapter_number_of(p)
        if n is not None and p.is_file():
            out.append((n, p))
    return sorted(out, key=lambda t: t[0])


def notes_path_for(root: Path, n: int, chapter_path: Optional[Path] = None) -> Path:
    if chapter_path is not None:
        return chapter_path.with_name(chapter_path.stem + "-notes.md")
    return root / f"chapter-{n:02d}-notes.md"


def parse_chapter(path: Path) -> dict:
    """返回 {number,title,pov,heading,body,raw}。body 为去掉标题与 POV 行后的正文。"""
    raw = read_text(path)
    lines = raw.splitlines()
    number = chapter_number_of(path)
    title, pov, heading = "", "", ""
    body_start = 0
    # 跳过开头空行
    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx < len(lines) and lines[idx].lstrip().startswith("#"):
        heading = lines[idx].strip()
        m = HEADING_RE.match(heading)
        if m:
            number = number or int(m.group(1) or m.group(3))
            title = (m.group(2) or m.group(4) or "").strip()
        else:
            title = re.sub(r"^#+\s*", "", heading).strip()
        idx += 1
        body_start = idx
    # 标题后 3 行内寻找 POV 标记
    for j in range(idx, min(idx + 3, len(lines))):
        m = POV_RE.search(lines[j])
        if m:
            pov = m.group(1).strip()
            body_start = j + 1
            break
    body = "\n".join(lines[body_start:]).strip("\n")
    return {
        "number": number,
        "title": title or path.stem,
        "pov": pov,
        "heading": heading,
        "body": body,
        "raw": raw,
        "path": path,
    }


# ---------------------------------------------------------------------------
# 字数统计（双语）
# ---------------------------------------------------------------------------
def strip_markdown(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_~`>]+", "", text)
    text = re.sub(r"^\s*-{3,}\s*$", "", text, flags=re.M)
    return text


def detect_language(text: str) -> str:
    cjk = len(CJK_RE.findall(text))
    latin = len(EN_WORD_RE.findall(text))
    return "zh" if cjk >= latin else "en"


def count_words(text: str, lang: Optional[str] = None) -> int:
    clean = strip_markdown(text)
    lang = lang or detect_language(clean)
    if lang == "zh":
        return len(CJK_RE.findall(clean))
    return len(EN_WORD_RE.findall(clean))


# ---------------------------------------------------------------------------
# Markdown 表格 / notes meta 解析
# ---------------------------------------------------------------------------
def parse_md_tables(text: str) -> List[List[List[str]]]:
    """解析文本中所有 GFM 表格，返回 [table][row][cell]（含表头，去掉分隔行）。"""
    tables, cur = [], []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|") and s.count("|") >= 2:
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            cur.append(cells)
        else:
            if cur:
                tables.append(cur)
                cur = []
    if cur:
        tables.append(cur)
    return tables


def find_table(text: str, header_keywords: Iterable[str]) -> Optional[List[List[str]]]:
    """返回表头包含任一关键词的第一张表。"""
    kws = [k.lower() for k in header_keywords]
    for t in parse_md_tables(text):
        head = " ".join(t[0]).lower()
        if any(k in head for k in kws):
            return t
    return None


def extract_chapter_ref(cell: str) -> Optional[int]:
    """从 '第 05 章' / 'Ch.12' / 'Chapter 3' / '12' 中提取章节号；'尚未出场' 等返回 None。"""
    m = re.search(r"(?:第\s*(\d+)\s*章)|(?:Ch(?:apter)?\.?\s*(\d+))|^\s*(\d+)\s*$", cell, re.IGNORECASE)
    if not m:
        return None
    return int(next(g for g in m.groups() if g))


META_BLOCK_RE = re.compile(r"```meta\s*\n(.*?)\n```", re.S | re.IGNORECASE)
LIST_KEYS = {"present", "mentioned", "new_facts", "open_threads", "characters"}


def parse_meta_block(text: str) -> Dict[str, object]:
    """解析 notes 顶部 ```meta 块：`key: value`；LIST_KEYS 按逗号/顿号切分为列表。"""
    m = META_BLOCK_RE.search(text)
    if not m:
        return {}
    meta: Dict[str, object] = {}
    for line in m.group(1).splitlines():
        if ":" not in line or line.strip().startswith("#"):
            continue
        k, v = line.split(":", 1)
        k, v = k.strip().lower(), v.strip()
        if k in LIST_KEYS:
            meta[k] = [x.strip() for x in re.split(r"[,，、;；]", v) if x.strip()]
        else:
            meta[k] = v
    return meta


def parse_notes(path: Path) -> dict:
    raw = read_text(path)
    meta = parse_meta_block(raw)
    return {"path": path, "raw": raw, "meta": meta}


# ---------------------------------------------------------------------------
# 03-global-notes.md：POV 信息墙 + 配角追踪表
# ---------------------------------------------------------------------------
def parse_pov_wall(global_notes_text: str) -> List[dict]:
    """
    解析 POV 信息墙表：| POV 角色 | 不知道的事实 | 禁用关键词 | 来源章节 | 解禁章节 |
    返回 [{holder, fact, keywords[], since, until}]
    """
    table = find_table(global_notes_text, ["pov", "视角"])
    rows = []
    if not table or len(table) < 2:
        return rows
    for r in table[1:]:
        if len(r) < 2:
            continue
        holder = r[0]
        fact = r[1] if len(r) > 1 else ""
        kw_cell = r[2] if len(r) > 2 else ""
        keywords = [k.strip() for k in re.split(r"[,，、;；/]", kw_cell) if k.strip()]
        since = extract_chapter_ref(r[3]) if len(r) > 3 else None
        until = extract_chapter_ref(r[4]) if len(r) > 4 else None
        for h in re.split(r"[,，、/]", holder):
            h = h.strip().strip("*")
            if h:
                rows.append({"holder": h, "fact": fact, "keywords": keywords, "since": since, "until": until})
    return rows


def parse_tracker(global_notes_text: str) -> List[dict]:
    """解析配角活跃度追踪表：| 配角姓名 | 上次出场章节 | 出场形式 | 活跃度 |"""
    table = find_table(global_notes_text, ["配角", "上次出场", "last seen", "character"])
    rows = []
    if not table or len(table) < 2:
        return rows
    for r in table[1:]:
        if not r or not r[0]:
            continue
        rows.append(
            {
                "name": r[0].strip("*").strip(),
                "last": extract_chapter_ref(r[1]) if len(r) > 1 else None,
                "form": r[2] if len(r) > 2 else "",
                "status": r[3] if len(r) > 3 else "",
            }
        )
    return rows


# ---------------------------------------------------------------------------
# 00-outline.md：章节 Brief 切片；TODO 勾选状态
# ---------------------------------------------------------------------------
def extract_chapter_brief(outline_text: str, n: int) -> str:
    """只切出第 n 章的 `###` Brief 段落（到下一个 ##/### 标题为止），避免整读 50KB 大纲。"""
    pat = re.compile(
        rf"^#{{2,4}}\s*(?:第\s*0*{n}\s*章|Chapter\s*0*{n})\b.*$", re.IGNORECASE | re.M
    )
    lines = outline_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if pat.match(line):
            start = i
    if start is None:
        return ""
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    out = [lines[start]]
    for line in lines[start + 1 :]:
        if line.startswith("#") and (len(line) - len(line.lstrip("#"))) <= level:
            break
        out.append(line)
    return "\n".join(out).strip()


def outline_todo_status(outline_text: str) -> Dict[int, bool]:
    """返回 {章节号: 是否勾选}。"""
    status: Dict[int, bool] = {}
    for m in re.finditer(
        r"^\s*-\s*\[( |x|X)\]\s*(?:第\s*(\d+)\s*章|Chapter\s*(\d+))", outline_text, re.M
    ):
        n = int(m.group(2) or m.group(3))
        status[n] = m.group(1).lower() == "x"
    return status


# ---------------------------------------------------------------------------
# 02-timeline.md：全局时间线表
# ---------------------------------------------------------------------------
def timeline_rows(timeline_text: str) -> List[dict]:
    table = find_table(timeline_text, ["章节", "chapter"])
    rows = []
    if not table or len(table) < 2:
        return rows
    for r in table[1:]:
        n = extract_chapter_ref(r[0]) if r else None
        rows.append({"chapter": n, "cells": r})
    return rows


def timeline_constraints(timeline_text: str) -> List[List[str]]:
    table = find_table(timeline_text, ["约束", "constraint"])
    return table[1:] if table else []


def timeline_open_conflicts(timeline_text: str) -> List[List[str]]:
    table = find_table(timeline_text, ["冲突", "conflict"])
    if not table:
        return []
    return [r for r in table[1:] if r and not any(s in " ".join(r) for s in ("✅", "已解决", "resolved"))]
