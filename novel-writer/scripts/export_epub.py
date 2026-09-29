#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_epub.py — Novel Writer EPUB 导出器（三通道容灾：ebooklib → pandoc → 内置零依赖引擎）

用法：
  # 单章导出到桌面项目文件夹（Step 4）
  python3 scripts/export_epub.py /path/novel/chapter-07.md --desktop

  # 批量导出目录下全部章节（每章一个 EPUB）
  python3 scripts/export_epub.py /path/novel --desktop

  # 全本合并为一个 EPUB（Phase 4 终审交付）
  python3 scripts/export_epub.py /path/novel --book --desktop

  # 显式输出目录 / 文件
  python3 scripts/export_epub.py /path/novel/chapter-07.md --out ~/Books/novel
  python3 scripts/export_epub.py /path/novel --book --output ~/Books/novel.epub

参数默认值自动读取项目 04-generation-plan.json：
  language → --lang ；author → --author ；displayTitle/novelName → --name ；exportDir → 输出目录

输出目录解析优先级：
  --output > --out > $NOVEL_EXPORT_DIR > plan.exportDir > (--desktop: ~/Desktop/<匹配的书名文件夹>) > <项目>/exports/
  ~/Desktop 不存在（Linux 服务器 / Windows OneDrive 重定向）时自动回退到 <项目>/exports/，绝不崩溃。

引擎：
  --engine auto|ebooklib|pandoc|builtin  （auto 按顺序尝试，任何一个成功即停止）
  builtin 引擎只依赖标准库（zipfile），生成 EPUB 3 + NCX 兼容包，保证在任何 Python 3.8+ 环境都能导出。

导出成功后会把 epubPath / epubExportedAt 写回 plan.chapters[]（--no-plan-update 关闭）。
退出码：0 全部成功；1 至少一个失败；2 参数错误。
"""
from __future__ import annotations

import argparse
import html
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novel_common import (  # noqa: E402
    find_project_root,
    list_chapters,
    load_plan,
    now_iso,
    parse_chapter,
    plan_language,
    save_plan,
)

CSS = (
    "body{line-height:1.8;margin:1.6em}"
    "h1,h2{font-weight:bold;margin:0 0 .6em;color:#111}h1{font-size:1.5em}"
    "p{margin:0 0 .9em;text-indent:0}em{font-style:italic}"
    "hr{border:none;border-top:1px solid #ddd;margin:2em 0}"
    "figure{margin:1.8em 0;text-align:center;page-break-inside:avoid;break-inside:avoid}"
    "figure img{max-width:100%;height:auto;display:block;margin:0 auto}"
    "figcaption{margin-top:0.7em;font-style:italic;font-size:0.92em;line-height:1.5}"
    "mark{background:#EADFC4;color:#2A2420;padding:0.05em 0.18em;border-radius:2px}"
    "blockquote{margin:1.3em 1.6em;padding-left:0.9em;border-left:2px solid rgba(0,0,0,0.18);font-style:italic}"
    ".pov{color:#666;font-style:italic;margin-bottom:1.4em}"
)


# ---------------------------------------------------------------------------
# 图片发现与处理
# ---------------------------------------------------------------------------
_IMG_SRC_RE = re.compile(r'<img\b[^>]*\bsrc="([^"]+)"', re.IGNORECASE)
_FIGURE_BLOCK_RE = re.compile(r'<figure\b[^>]*>.*?</figure>', re.IGNORECASE | re.DOTALL)
_SCHEME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9+\-.]*:')
_IMG_MEDIA = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
}


def _image_media_type(path: Path) -> str:
    mt = _IMG_MEDIA.get(path.suffix.lower())
    if mt:
        return mt
    guess, _ = mimetypes.guess_type(str(path))
    return guess or "application/octet-stream"


def _discover_images(md_text: str, md_dir: Path) -> List[tuple]:
    """Return [(src_in_md, resolved_abs_path)] for local images in markdown."""
    results = []
    for src in _IMG_SRC_RE.findall(md_text):
        if _SCHEME_RE.match(src):
            continue
        resolved = (md_dir / src).resolve()
        results.append((src, resolved))
    return results


def _prepare_images(chapters: List[dict]) -> tuple:
    """Collect images from all chapters, de-duplicate, handle missing files.

    Returns (image_files, chapter_rewrites, chapter_drops) where:
      image_files = {resolved_abs_path: epub_basename}
      chapter_rewrites = {chapter_path: [(old_src, new_src)]}
      chapter_drops = {chapter_path: set_of_missing_srcs}
    """
    # resolved_path → epub basename
    image_files: dict[Path, str] = {}
    # track basenames to disambiguate
    used_basenames: dict[str, Path] = {}
    chapter_rewrites: dict[Path, list] = {}
    chapter_drops: dict[Path, set] = {}

    for ch in chapters:
        ch_path = ch["path"]
        md_dir = ch_path.parent
        md_text = ch_path.read_text(encoding="utf-8")
        refs = _discover_images(md_text, md_dir)
        rewrites = []
        drops = set()
        for src, resolved in refs:
            if not resolved.is_file():
                print(f"⚠️  图片不存在: {ch_path.name}: {src}")
                drops.add(src)
                continue
            if resolved not in image_files:
                basename = resolved.name
                if basename in used_basenames and used_basenames[basename] != resolved:
                    stem, suffix = resolved.stem, resolved.suffix
                    n = 1
                    while f"{stem}-{n}{suffix}" in used_basenames:
                        n += 1
                    basename = f"{stem}-{n}{suffix}"
                used_basenames[basename] = resolved
                image_files[resolved] = basename
            rewrites.append((src, f"images/{image_files[resolved]}"))
        if rewrites:
            chapter_rewrites[ch_path] = rewrites
        if drops:
            chapter_drops[ch_path] = drops
    return image_files, chapter_rewrites, chapter_drops


def _rewrite_html(xhtml: str, rewrites: list, drops: set) -> str:
    """Rewrite img src paths, drop <figure> blocks for missing images, self-close <img>."""
    # Drop entire <figure> blocks referencing missing images
    if drops:
        def _drop_figure(m):
            block = m.group(0)
            for src in drops:
                if f'src="{src}"' in block:
                    return ""
            return block
        xhtml = _FIGURE_BLOCK_RE.sub(_drop_figure, xhtml)
    # Rewrite src paths
    for old_src, new_src in rewrites:
        xhtml = xhtml.replace(f'src="{old_src}"', f'src="{new_src}"')
    # Self-close <img> tags for XHTML well-formedness
    xhtml = re.sub(r'<img\b([^>]*?)(?<!/)>', r'<img\1/>', xhtml)
    return xhtml


# ---------------------------------------------------------------------------
# 输出目录
# ---------------------------------------------------------------------------
def _norm(s: str) -> str:
    return re.sub(r"[\s\-_]+", "", s).lower()


def resolve_desktop_dir(novel_name: str) -> Optional[Path]:
    """定位 ~/Desktop/<书名>（大小写/空格/连字符不敏感）；Desktop 不存在返回 None。"""
    candidates = [Path.home() / "Desktop", Path.home() / "OneDrive" / "Desktop", Path.home() / "桌面"]
    if sys.platform == "win32" and os.environ.get("USERPROFILE"):
        candidates.insert(0, Path(os.environ["USERPROFILE"]) / "Desktop")
    desktop = next((d for d in candidates if d.is_dir()), None)
    if desktop is None:
        return None
    target = _norm(novel_name)
    try:
        for entry in desktop.iterdir():
            if entry.is_dir() and _norm(entry.name) == target:
                return entry
    except OSError:
        pass
    return desktop / novel_name


def resolve_out_dir(args, root: Optional[Path], plan: Optional[dict], novel_name: str, target: Path) -> Path:
    if args.out:
        return Path(args.out).expanduser()
    if os.environ.get("NOVEL_EXPORT_DIR"):
        return Path(os.environ["NOVEL_EXPORT_DIR"]).expanduser()
    if plan and plan.get("exportDir"):
        return Path(str(plan["exportDir"])).expanduser()
    if args.desktop:
        d = resolve_desktop_dir(novel_name)
        if d is not None:
            return d
        base = root or (target if target.is_dir() else target.parent)
        print(f"⚠️ 未找到桌面目录，回退到 {base / 'exports'}")
        return base / "exports"
    base = root or (target if target.is_dir() else target.parent)
    return base / "exports"


# ---------------------------------------------------------------------------
# Markdown → XHTML（内置极简转换，覆盖小说正文常用语法）
# ---------------------------------------------------------------------------
def _inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"(?<![A-Za-z0-9])_(?!\s)(.+?)(?<!\s)_(?![A-Za-z0-9])", r"<em>\1</em>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def md_to_xhtml_body(md: str, lang: str) -> str:
    joiner = "" if lang == "zh" else " "
    out: List[str] = []
    para: List[str] = []
    quote: List[str] = []
    in_raw: List[str] = []

    def flush_para():
        if para:
            text = joiner.join(x.strip() for x in para)
            # Handle inline <mark>…</mark> inside paragraphs
            parts = re.split(r'(<mark>.*?</mark>)', text)
            processed = "".join(p if p.startswith("<mark>") else _inline(p) for p in parts)
            out.append(f"<p>{processed}</p>")
            para.clear()

    def flush_quote():
        if quote:
            text = joiner.join(quote)
            parts = re.split(r'(<mark>.*?</mark>)', text)
            processed = "".join(p if p.startswith("<mark>") else _inline(p) for p in parts)
            out.append(f"<blockquote><p>{processed}</p></blockquote>")
            quote.clear()

    for line in md.splitlines():
        s = line.rstrip()
        stripped = s.lstrip()
        # Raw HTML block passthrough: <figure>, </figure>, <img>, <figcaption>, </figcaption>
        if stripped.startswith(("<figure", "</figure")):
            flush_para()
            flush_quote()
            if stripped.startswith("<figure"):
                in_raw.append(s)
            else:
                in_raw.append(s)
                out.append("\n".join(in_raw))
                in_raw.clear()
            continue
        if in_raw:
            in_raw.append(s)
            continue
        if not s.strip():
            flush_para()
            flush_quote()
            continue
        m = re.match(r"^(#{1,6})\s*(.*)$", s)
        if m:
            flush_para()
            flush_quote()
            lvl = min(len(m.group(1)), 6)
            out.append(f"<h{lvl}>{_inline(m.group(2).strip())}</h{lvl}>")
            continue
        if re.match(r"^\s*([-*_])(\s*\1){2,}\s*$", s):
            flush_para()
            flush_quote()
            out.append("<hr/>")
            continue
        if s.lstrip().startswith(">"):
            flush_para()
            quote.append(s.lstrip()[1:].strip())
            continue
        flush_quote()
        para.append(s)
    flush_para()
    flush_quote()
    return "\n".join(out)


def chapter_xhtml(ch: dict, lang: str, book_title: str,
                  rewrites: list = (), drops: set = frozenset()) -> str:
    title = html.escape(ch["title"])
    pov = f'<p class="pov">{_inline("(POV: " + ch["pov"] + ")")}</p>' if ch["pov"] else ""
    heading = html.escape(re.sub(r"^#+\s*", "", ch["heading"]) or ch["title"])
    body = md_to_xhtml_body(ch["body"], lang)
    xhtml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{lang}" lang="{lang}">'
        f"<head><title>{title}</title><link rel=\"stylesheet\" type=\"text/css\" href=\"style.css\"/></head>"
        f"<body><h1>{heading}</h1>{pov}{body}</body></html>"
    )
    if rewrites or drops:
        xhtml = _rewrite_html(xhtml, list(rewrites), set(drops))
    return xhtml


# ---------------------------------------------------------------------------
# 引擎 1：ebooklib
# ---------------------------------------------------------------------------
def engine_ebooklib(chapters: List[dict], out: Path, title: str, author: str, lang: str, ident: str) -> None:
    from ebooklib import epub  # type: ignore

    image_files, chapter_rewrites, chapter_drops = _prepare_images(chapters)
    book = epub.EpubBook()
    book.set_identifier(ident)
    book.set_title(title)
    book.set_language(lang)
    book.add_author(author)
    style = epub.EpubItem(uid="style", file_name="style.css", media_type="text/css", content=CSS.encode("utf-8"))
    book.add_item(style)
    # Add images
    for resolved, basename in image_files.items():
        img = epub.EpubImage()
        img.file_name = f"images/{basename}"
        img.media_type = _image_media_type(resolved)
        img.content = resolved.read_bytes()
        book.add_item(img)
    items, toc = [], []
    for ch in chapters:
        fn = f"{ch['path'].stem}.xhtml"
        it = epub.EpubHtml(title=ch["title"], file_name=fn, lang=lang)
        rw = chapter_rewrites.get(ch["path"], [])
        dr = chapter_drops.get(ch["path"], set())
        it.content = chapter_xhtml(ch, lang, title, rw, dr).encode("utf-8")
        it.add_item(style)
        book.add_item(it)
        items.append(it)
        toc.append(epub.Link(fn, ch["title"], ch["path"].stem))
    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", *items]
    epub.write_epub(str(out), book, {})


# ---------------------------------------------------------------------------
# 引擎 2：pandoc
# ---------------------------------------------------------------------------
def engine_pandoc(chapters: List[dict], out: Path, title: str, author: str, lang: str, ident: str) -> None:
    if shutil.which("pandoc") is None:
        raise RuntimeError("pandoc 未安装")
    css = out.with_suffix(".tmp.css")
    css.write_text(CSS, encoding="utf-8")
    # Collect unique chapter directories for --resource-path so pandoc finds local images
    res_dirs = list(dict.fromkeys(str(c["path"].parent) for c in chapters))
    try:
        cmd = [
            "pandoc", *[str(c["path"]) for c in chapters], "-o", str(out), "--from", "markdown", "--to", "epub3",
            "--metadata", f"title={title}", "--metadata", f"author={author}", "--metadata", f"lang={lang}",
            "--css", str(css), "--split-level=1",
            "--resource-path", os.pathsep.join(res_dirs),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip()[:400])
    finally:
        css.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 引擎 3：内置零依赖
# ---------------------------------------------------------------------------
def engine_builtin(chapters: List[dict], out: Path, title: str, author: str, lang: str, ident: str) -> None:
    image_files, chapter_rewrites, chapter_drops = _prepare_images(chapters)
    manifest, spine, nav_li, ncx_pts = [], [], [], []
    files = {}
    binary_files: dict[str, bytes] = {}
    for i, ch in enumerate(chapters, 1):
        fn = f"{ch['path'].stem}.xhtml"
        cid = f"c{i}"
        rw = chapter_rewrites.get(ch["path"], [])
        dr = chapter_drops.get(ch["path"], set())
        files[f"OEBPS/{fn}"] = chapter_xhtml(ch, lang, title, rw, dr)
        manifest.append(f'<item id="{cid}" href="{fn}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="{cid}"/>')
        t = html.escape(ch["title"])
        nav_li.append(f'<li><a href="{fn}">{t}</a></li>')
        ncx_pts.append(
            f'<navPoint id="np{i}" playOrder="{i}"><navLabel><text>{t}</text></navLabel><content src="{fn}"/></navPoint>'
        )
    # Add images to manifest and binary_files
    for idx, (resolved, basename) in enumerate(image_files.items(), 1):
        iid = f"img{idx}"
        mt = _image_media_type(resolved)
        manifest.append(f'<item id="{iid}" href="images/{basename}" media-type="{mt}"/>')
        binary_files[f"OEBPS/images/{basename}"] = resolved.read_bytes()
    nav = (
        '<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml" '
        f'xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{lang}"><head><title>Contents</title>'
        '<link rel="stylesheet" type="text/css" href="style.css"/></head><body>'
        f'<nav epub:type="toc" id="toc"><h1>{html.escape(title)}</h1><ol>{"".join(nav_li)}</ol></nav></body></html>'
    )
    ncx = (
        '<?xml version="1.0" encoding="utf-8"?>\n<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
        f'<head><meta name="dtb:uid" content="{ident}"/><meta name="dtb:depth" content="1"/></head>'
        f"<docTitle><text>{html.escape(title)}</text></docTitle><navMap>{''.join(ncx_pts)}</navMap></ncx>"
    )
    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:identifier id="uid">{ident}</dc:identifier><dc:title>{html.escape(title)}</dc:title>'
        f"<dc:language>{lang}</dc:language><dc:creator>{html.escape(author)}</dc:creator>"
        f'<meta property="dcterms:modified">{now_iso()}</meta></metadata>'
        '<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
        '<item id="css" href="style.css" media-type="text/css"/>'
        f'{"".join(manifest)}</manifest><spine toc="ncx">{"".join(spine)}</spine></package>'
    )
    container = (
        '<?xml version="1.0" encoding="utf-8"?>\n<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'
    )
    tmp = out.with_suffix(".epub.part")
    with zipfile.ZipFile(tmp, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/nav.xhtml", nav, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/toc.ncx", ncx, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", CSS, compress_type=zipfile.ZIP_DEFLATED)
        for name, content in files.items():
            z.writestr(name, content, compress_type=zipfile.ZIP_DEFLATED)
        for name, data in binary_files.items():
            z.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
    tmp.replace(out)


ENGINES = {"ebooklib": engine_ebooklib, "pandoc": engine_pandoc, "builtin": engine_builtin}


def export(chapters: List[dict], out: Path, title: str, author: str, lang: str, engine: str, quiet: bool) -> Optional[str]:
    out.parent.mkdir(parents=True, exist_ok=True)
    ident = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, f"novel-writer/{title}/{out.stem}"))
    order = ["ebooklib", "pandoc", "builtin"] if engine == "auto" else [engine]
    errors = []
    for name in order:
        try:
            ENGINES[name](chapters, out, title, author, lang, ident)
            if not quiet:
                print(f"✅ [{name}] {out}")
            return name
        except Exception as e:  # noqa: BLE001 — 任何引擎失败都降级到下一个
            errors.append(f"{name}: {type(e).__name__}: {str(e)[:160]}")
    print(f"❌ 导出失败 {out.name}：" + " | ".join(errors))
    return None


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Novel Writer EPUB 导出器")
    ap.add_argument("target", help="chapter-NN.md 或项目目录")
    ap.add_argument("--desktop", action="store_true", help="输出到 ~/Desktop/<书名>/（找不到桌面时回退到项目 exports/）")
    ap.add_argument("--book", action="store_true", help="目录模式下合并为单个全本 EPUB")
    ap.add_argument("--out", help="输出目录")
    ap.add_argument("--output", help="输出文件（单章或 --book）")
    ap.add_argument("--name", help="书名（用于桌面目录匹配与全本标题）")
    ap.add_argument("--author", help="作者（默认读 plan.author，否则 'Author'）")
    ap.add_argument("--lang", choices=["zh", "en"], help="语言（默认读 plan.language）")
    ap.add_argument("--engine", choices=["auto", *ENGINES], default="auto")
    ap.add_argument("--no-plan-update", action="store_true", help="不把 epubPath 写回 plan.json")
    ap.add_argument("--illustrated", action="store_true", help="优先使用 illustrations/chapter-NN/ 下的插图版 markdown")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    target = Path(args.target).expanduser().resolve()
    if not target.exists():
        print(f"❌ 目标不存在: {target}")
        return 2
    root = find_project_root(target)
    plan = load_plan(root) if root else None
    lang = args.lang or plan_language(plan)
    novel_name = args.name or (plan or {}).get("displayTitle") or (plan or {}).get("novelName") or (
        target.parent.name if target.is_file() else target.name
    )
    author = args.author or (plan or {}).get("author") or "Author"
    out_dir = resolve_out_dir(args, root, plan, novel_name, target)

    def _maybe_illustrated(md_path: Path) -> Path:
        """If --illustrated and an illustrated variant exists, return it; else original."""
        if not args.illustrated or root is None:
            return md_path
        m = re.match(r"^(chapter-\d+)\.md$", md_path.name, re.IGNORECASE)
        if not m:
            return md_path
        stem = m.group(1)
        alt = root / "illustrations" / stem / f"{stem}-illustrated.md"
        return alt if alt.is_file() else md_path

    if target.is_file():
        if target.suffix.lower() != ".md":
            print("❌ 单文件模式仅支持 .md")
            return 2
        actual = _maybe_illustrated(target)
        jobs = [([parse_chapter(actual)], Path(args.output).expanduser() if args.output else out_dir / f"{target.stem}.epub", None)]
    else:
        chs = [parse_chapter(_maybe_illustrated(p)) for _, p in list_chapters(target)]
        if not chs:
            print(f"⚠️ {target} 下未找到 chapter-NN.md")
            return 2
        if args.book:
            safe_name = re.sub(r"[^\w\- ]+", "", novel_name).strip() or "book"
            fn = Path(args.output).expanduser() if args.output else out_dir / f"{safe_name}.epub"
            jobs = [(chs, fn, novel_name)]
        else:
            jobs = [([c], out_dir / f"{c['path'].stem}.epub", None) for c in chs]

    failed = 0
    exported = {}
    book_exported = None
    for chapters, out, book_title in jobs:
        title = book_title or (f"{novel_name} — {chapters[0]['title']}" if len(chapters) == 1 else novel_name)
        used = export(chapters, out, title, author, lang, args.engine, args.quiet)
        if used is None:
            failed += 1
        elif args.book:
            book_exported = out
        elif len(chapters) == 1:
            exported[chapters[0]["number"]] = out

    if exported and plan and root and not args.no_plan_update:
        by_no = {c.get("chapterNumber"): c for c in plan.get("chapters", [])}
        touched = False
        for n, p in exported.items():
            if n in by_no:
                by_no[n]["epubPath"] = str(p)
                by_no[n]["epubExportedAt"] = now_iso()
                touched = True
        if touched:
            save_plan(root, plan)
            if not args.quiet:
                print("🛠  已写回 04-generation-plan.json（epubPath / epubExportedAt）")
    if book_exported and plan and root and not args.no_plan_update:
        plan["bookEpubPath"] = str(book_exported)
        plan["bookEpubExportedAt"] = now_iso()
        save_plan(root, plan)
        if not args.quiet:
            print("🛠  已写回 04-generation-plan.json（bookEpubPath / bookEpubExportedAt）")

    print(f"— jobs={len(jobs)} ok={len(jobs) - failed} failed={failed} → {out_dir if not args.output else Path(args.output).expanduser().parent}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
