# -*- coding: utf-8 -*-
"""codeshots —— 把源码片段渲染成带语法高亮、行号栏、中英对齐的 PNG。

用途：往实验报告 / Word 文档里插代码图。图是**渲染生成**的，不是屏幕截图，
因此可复现、可控（列宽 / 字号 / 折行位置全部可调）。

依赖：Pillow、Pygments

三种输入：
  file      指定源码文件的某几行
  notebook  指定 .ipynb 的某个 cell
  text      预先抽好的纯文本片段

四种用法：
  codeshots.py file  <源文件> --start 10 --end 24 -o out.png [--lang python]
  codeshots.py nb    <notebook.ipynb> --cell 6 [-o out.png]
  codeshots.py text  <片段.txt> -o out.png
  codeshots.py batch <specs.json> -o <输出目录> [--manifest shots.json]

完整参数见 README.md，或 `codeshots.py -h`。
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pygments import lex
from pygments.lexers import get_lexer_by_name, get_lexer_for_filename, TextLexer
from pygments.styles import get_style_by_name
from pygments.util import ClassNotFound

__version__ = "1.0.0"

# ---------------------------------------------------------------- 字体 ------
# Windows 自带字体；缺失时回退到 PIL 默认字体（会退化但不崩）
FONT_CANDIDATES = {
    ("ascii", False): [r"C:\Windows\Fonts\consola.ttf"],
    ("ascii", True): [r"C:\Windows\Fonts\consolab.ttf", r"C:\Windows\Fonts\consola.ttf"],
    ("cjk", False): [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"],
    ("cjk", True): [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc"],
}


@dataclass
class Theme:
    """一套配色。light 用于白底报告，dark 用于深色预览。"""

    name: str
    style: str
    bg: tuple
    border: tuple
    gutter_fg: tuple
    gutter_sep: tuple
    fg_fallback: tuple

    @staticmethod
    def get(name: str, style_override: str | None = None) -> "Theme":
        if name == "dark":
            t = Theme("dark", style_override or "monokai",
                      bg=(30, 30, 32), border=(70, 70, 76),
                      gutter_fg=(120, 122, 130), gutter_sep=(60, 60, 66),
                      fg_fallback=(220, 220, 224))
        else:
            t = Theme("light", style_override or "friendly",
                      bg=(252, 252, 252), border=(206, 206, 206),
                      gutter_fg=(152, 152, 152), gutter_sep=(214, 214, 214),
                      fg_fallback=(0, 0, 0))
        if style_override:
            t.style = style_override
        return t


@dataclass
class Options:
    """渲染参数（所有可调项集中在这里）。"""

    font_size: int = 20          # 字号(px)
    line_height: int = 32        # 行高(px)
    pad: int = 16                # 内边距(px)
    gutter_pad: int = 11         # 行号栏与分隔线的间距
    max_cells: int = 72          # 每行最大"字符格"数（半角1格/全角2格），超出折行
    cont_indent: int = 8         # 续行缩进格数
    show_numbers: bool = True    # 是否画行号栏
    theme: Theme = field(default_factory=lambda: Theme.get("light"))


# ------------------------------------------------------- 全角/半角判定 ------
_WIDE_RANGES = [
    (0x1100, 0x115F), (0x2E80, 0x303E), (0x3041, 0x33FF), (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF), (0xA000, 0xA4CF), (0xAC00, 0xD7A3), (0xF900, 0xFAFF),
    (0xFE30, 0xFE4F), (0xFF00, 0xFF60), (0xFFE0, 0xFFE6), (0x20000, 0x3FFFD),
]
_WIDE_SINGLE = {0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2026, 0x00B7}


def is_wide(ch: str) -> bool:
    o = ord(ch)
    return o in _WIDE_SINGLE or any(a <= o <= b for a, b in _WIDE_RANGES)


def cells(seq) -> int:
    """一段 (字符, 样式) 序列占多少个字符格。"""
    return sum(2 if is_wide(c) else 1 for c, _ in seq)


# ------------------------------------------------------------- 字体缓存 ----
_font_cache: dict[tuple, object] = {}


def font_for(cjk: bool, bold: bool, size: int):
    key = ("cjk" if cjk else "ascii", bold, size)
    if key not in _font_cache:
        f = None
        for p in FONT_CANDIDATES[("cjk" if cjk else "ascii", bold)]:
            if Path(p).exists():
                try:
                    f = ImageFont.truetype(p, size)
                    break
                except OSError:
                    continue
        if f is None:
            try:
                f = ImageFont.load_default(size=size)
            except TypeError:
                f = ImageFont.load_default()
        _font_cache[key] = f
    return _font_cache[key]


# --------------------------------------------------------------- 取源码 ----
def pick_lexer(lang: str | None, filename: str | None):
    if lang:
        try:
            return get_lexer_by_name(lang)
        except ClassNotFound:
            raise SystemExit(f"!! 不认识的语法名：{lang}（试试 python / java / cpp / sql / bash）")
    if filename:
        try:
            return get_lexer_for_filename(filename)
        except ClassNotFound:
            pass
    return TextLexer()


def lines_from_file(path: Path, start: int | None, end: int | None) -> list[str]:
    src = path.read_text(encoding="utf-8").splitlines()
    s = (start if start is not None else 1) - 1
    e = end if end is not None else len(src)
    if s < 0 or e > len(src) or s >= e:
        raise SystemExit(f"!! 行号越界：文件共 {len(src)} 行，请求 {start}~{end}")
    return [ln.rstrip() for ln in src[s:e]]


def lines_from_notebook(path: Path, cell: int, start: int | None, end: int | None) -> list[str]:
    nb = json.loads(path.read_text(encoding="utf-8"))
    cells_ = nb.get("cells", [])
    if not 0 <= cell < len(cells_):
        raise SystemExit(f"!! cell 下标越界：该 notebook 共 {len(cells_)} 个 cell（0 基）")
    src = "".join(cells_[cell].get("source", [])).splitlines()
    s = (start if start is not None else 1) - 1
    e = end if end is not None else len(src)
    if s < 0 or e > len(src) or s >= e:
        raise SystemExit("!! Notebook 行号越界或片段为空")
    return [ln.rstrip() for ln in src[s:e]]


# ------------------------------------------------------------- 折行/排版 ---
def wrap_chars(chars, line_no, opt: Options):
    """把一行按 max_cells 折行；优先在空格处断，避免从 token 中间劈开。"""
    rows = []
    cur: list[tuple[str, object]] = []
    pending_no = line_no
    i, n = 0, len(chars)

    while i < n:
        ch, tp = chars[i]
        w = 2 if is_wide(ch) else 1
        if cur and cells(cur) + w > opt.max_cells:
            brk = len(cur)
            for j in range(len(cur) - 1, opt.cont_indent, -1):
                if cur[j][0] == " ":
                    brk = j
                    break
            head, rest = cur[:brk], cur[brk:]
            if not head:
                head, rest = cur, []
            rows.append((pending_no, head))
            pending_no = None
            cur = [(" ", tp)] * opt.cont_indent + rest
            continue
        cur.append((ch, tp))
        i += 1

    rows.append((pending_no, cur))
    return rows


def build_rows(lines: list[str], start_no: int, lexer, opt: Options):
    """源码行 -> [(行号|None, [(字符, 样式), ...]), ...]"""
    if opt.font_size <= 0 or opt.max_cells < 2 or not 0 <= opt.cont_indent <= opt.max_cells - 2:
        raise SystemExit("!! 字号必须为正数，列宽至少为 2，续行缩进须在 0 到列宽-2 之间")
    if opt.pad < 0 or opt.gutter_pad < 0:
        raise SystemExit("!! 内边距不能为负数")
    text = "\n".join(lines)
    raw: list[list[tuple[str, object]]] = [[]]
    for ttype, value in lex(text, lexer):
        for i, p in enumerate(value.split("\n")):
            if i > 0:
                raw.append([])
            if p:
                raw[-1].append((p, ttype))

    out = []
    for li, tokens in enumerate(raw[:len(lines)]):
        chars = [(ch, tp) for chunk, tp in tokens for ch in chunk]
        out.extend(wrap_chars(chars, start_no + li, opt))
    return out


def make_color_fn(theme: Theme):
    try:
        style = get_style_by_name(theme.style)
    except ClassNotFound:
        raise SystemExit(f"!! 不认识的 Pygments 配色：{theme.style}"
                         f"（可用值见 `python -c \"from pygments.styles import get_all_styles;print(list(get_all_styles()))\"`）")
    cache: dict[object, tuple] = {}

    def color_of(ttype):
        if ttype in cache:
            return cache[ttype]
        t = ttype
        while t is not None and t not in style.styles:
            t = t.parent
        s = style.styles.get(t, "") if t is not None else ""
        color, bold = theme.fg_fallback, False
        for part in s.split():
            if part.startswith("#") and len(part) == 7:
                color = (int(part[1:3], 16), int(part[3:5], 16), int(part[5:7], 16))
            elif part == "bold":
                bold = True
        cache[ttype] = (color, bold)
        return cache[ttype]

    return color_of


# ----------------------------------------------------------------- 渲染 ----
def render(lines: list[str], start_no: int, lexer, out: Path, opt: Options) -> dict:
    theme = opt.theme
    color_of = make_color_fn(theme)
    rows = build_rows(lines, start_no, lexer, opt)

    max_cells = max((cells(r) for _, r in rows), default=1) or 1
    n_rows = len(rows)

    ascii_font = font_for(False, False, opt.font_size)
    unit = ascii_font.getlength("M")

    gutter_w = 0
    if opt.show_numbers:
        digits = len(str(start_no + len(lines)))
        gutter_w = int(digits * unit + opt.gutter_pad * 2)

    width = int(opt.pad * 2 + gutter_w + max_cells * unit + opt.pad)
    height = int(opt.pad * 2 + n_rows * opt.line_height)

    img = Image.new("RGB", (width, height), theme.bg)
    d = ImageDraw.Draw(img)

    sep_x = opt.pad + gutter_w
    if opt.show_numbers:
        d.line([(sep_x, opt.pad - 4), (sep_x, height - opt.pad + 4)],
               fill=theme.gutter_sep, width=1)

    for r, (no, chars) in enumerate(rows):
        y = opt.pad + r * opt.line_height
        if opt.show_numbers and no is not None:
            ln = str(no)
            lw = ascii_font.getlength(ln)
            d.text((opt.pad + gutter_w - opt.gutter_pad - lw, y),
                   ln, font=ascii_font, fill=theme.gutter_fg)
        x = sep_x + (opt.gutter_pad if opt.show_numbers else 0)
        for ch, ttype in chars:
            color, bold = color_of(ttype)
            cjk = is_wide(ch)
            f = font_for(cjk, bold, opt.font_size)
            cw = (2 if cjk else 1) * unit
            dx = (cw - f.getlength(ch)) / 2 if cjk else 0
            d.text((x + dx, y), ch, font=f, fill=color)
            x += cw

    d.rectangle([0, 0, width - 1, height - 1], outline=theme.border, width=1)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return {"path": str(out), "width": width, "height": height,
            "src_lines": len(lines), "render_rows": n_rows}


# ------------------------------------------------------------------ CLI ----
def opt_from_args(a) -> Options:
    return Options(
        font_size=a.font_size,
        line_height=int(a.font_size * 1.6),
        pad=a.pad,
        gutter_pad=a.gutter_pad,
        max_cells=a.max_cells,
        cont_indent=a.cont_indent,
        show_numbers=not a.no_numbers,
        theme=Theme.get(a.bg, a.style),
    )


def common_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("-o", "--out", help="输出 PNG 路径（batch 模式下为输出目录）")
    p.add_argument("--lang", help="语法名（python/java/cpp/sql/...）；不给则按文件名推断")
    p.add_argument("--bg", choices=["light", "dark"], default=None,
                   help="配色底：light（默认，白底报告用）/ dark（深色预览用）")
    p.add_argument("--style", help="Pygments 配色名，覆盖 --bg 的默认值（如 friendly/monokai/dracula）")
    p.add_argument("--font-size", type=int, default=20, help="字号 px（默认 20）")
    p.add_argument("--pad", type=int, default=16, help="内边距 px（默认 16）")
    p.add_argument("--gutter-pad", type=int, default=11, help="行号栏间距 px（默认 11）")
    p.add_argument("--max-cells", type=int, default=72,
                   help="每行最大字符格数，超出折行（默认 72；报告页宽建议 68~76）")
    p.add_argument("--cont-indent", type=int, default=8, help="折行续行缩进格数（默认 8）")
    p.add_argument("--no-numbers", action="store_true", help="不画行号栏")
    p.add_argument("--start", type=int, help="起始行（1 基，含）")
    p.add_argument("--end", type=int, help="结束行（1 基，含）")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="codeshots",
        description="把源码片段渲染成带语法高亮、行号、中英对齐的 PNG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例：
  codeshots.py file main.py --start 10 --end 24 -o a.png
  codeshots.py file main.py --start 10 --end 24 -o a.png --bg dark
  codeshots.py nb demo.ipynb --cell 6 -o b.png
  codeshots.py text snippet.txt -o c.png --lang java
  codeshots.py batch specs.json -o shots/ --manifest shots/index.json
""")
    p.add_argument("--version", action="version", version=f"codeshots {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("file", help="渲染源码文件的若干行")
    pf.add_argument("src", type=Path)
    common_options(pf)

    pn = sub.add_parser("nb", help="渲染 .ipynb 的某个 cell")
    pn.add_argument("src", type=Path)
    pn.add_argument("--cell", type=int, required=True, help="cell 下标（0 基）")
    common_options(pn)

    pt = sub.add_parser("text", help="渲染已抽好的纯文本片段")
    pt.add_argument("src", type=Path)
    common_options(pt)

    pb = sub.add_parser("batch", help="按 JSON 配置批量渲染")
    pb.add_argument("spec", type=Path)
    pb.add_argument("-o", "--out", help="输出目录（默认用 spec 所在目录下的 shots/）")
    pb.add_argument("--manifest", help="写出清单 JSON（含图注/尺寸，便于后续插图脚本消费）")
    pb.add_argument("--bg", choices=["light", "dark"], default=None)
    pb.add_argument("--style")
    pb.add_argument("--font-size", type=int, default=None)
    pb.add_argument("--max-cells", type=int, default=None)
    pb.add_argument("--no-numbers", action="store_true")
    pb.add_argument("--quiet", action="store_true")
    return p


def cmd_one(a) -> int:
    opt = opt_from_args(a)
    if a.out is None:
        raise SystemExit("!! 请用 -o 指定输出路径")
    out = Path(a.out)

    if a.cmd == "file":
        lexer = pick_lexer(a.lang, str(a.src))
        lines = lines_from_file(a.src, a.start, a.end)
        start_no = a.start or 1
    elif a.cmd == "nb":
        lexer = pick_lexer(a.lang or "python", str(a.src))
        lines = lines_from_notebook(a.src, a.cell, a.start, a.end)
        start_no = a.start or 1
    else:  # text
        lexer = pick_lexer(a.lang, str(a.src))
        lines = lines_from_file(a.src, a.start, a.end)
        start_no = a.start or 1

    if not lines:
        raise SystemExit("!! 片段为空，检查 --start/--end 或源文件")
    info = render(lines, start_no, lexer, out, opt)
    print(f"[ok] {out}  {info['width']}x{info['height']}  "
          f"({info['src_lines']} 逻辑行 / {info['render_rows']} 显示行)")
    return 0


def cmd_batch(a) -> int:
    spec_path = Path(a.spec)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    base = spec_path.parent
    defaults = spec.get("defaults", {})
    items = spec.get("items", [])
    if not items:
        raise SystemExit("!! specs 里没有 items")

    outdir = Path(a.out) if a.out else base / "shots"

    def g(key, item_val, default):
        """取值优先级：命令行 > item > defaults > 内置默认"""
        cli = getattr(a, key.replace("-", "_"), None)
        if cli is not None:
            return cli
        if item_val is not None:
            return item_val
        return defaults.get(key.replace("-", "_"), default)

    manifest = []
    for it in items:
        bg = g("bg", it.get("bg"), "light")
        opt = Options(
            font_size=int(g("font-size", it.get("font_size"), 20)),
            line_height=int(g("font-size", it.get("font_size"), 20) * 1.6),
            pad=int(it.get("pad", defaults.get("pad", 16))),
            gutter_pad=int(it.get("gutter_pad", defaults.get("gutter_pad", 11))),
            max_cells=int(g("max-cells", it.get("max_cells"), 72)),
            cont_indent=int(it.get("cont_indent", defaults.get("cont_indent", 8))),
            show_numbers=not (a.no_numbers or it.get("no_numbers", defaults.get("no_numbers", False))),
            theme=Theme.get(bg, g("style", it.get("style"), None)),
        )

        kind = it.get("kind", "file")
        src = base / it["path"] if not Path(it["path"]).is_absolute() else Path(it["path"])
        start, end = it.get("start"), it.get("end")

        if kind == "notebook":
            lexer = pick_lexer(it.get("lang", "python"), str(src))
            lines = lines_from_notebook(src, it["cell"], start, end)
        elif kind == "text":
            lexer = pick_lexer(it.get("lang"), str(src))
            lines = lines_from_file(src, start, end)
        elif kind == "file":
            lexer = pick_lexer(it.get("lang"), str(src))
            lines = lines_from_file(src, start, end)
        else:
            raise SystemExit(f"!! 不支持的 kind：{kind}")

        out = outdir / it.get("out", f"{it.get('id', 'shot')}.png")
        info = render(lines, start or 1, lexer, out, opt)
        rec = {"id": it.get("id"), "caption": it.get("caption"),
               "out": str(out), "src": str(src), "kind": kind,
               "start": start, "end": end, **info}
        manifest.append(rec)
        if not a.quiet:
            print(f"[ok] {it.get('id', ''):<8} {out.name:<16} "
                  f"{info['width']}x{info['height']:<6} {rec['caption'] or ''}")

    if a.manifest:
        mp = Path(a.manifest)
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text(json.dumps({"shapes": manifest}, ensure_ascii=False, indent=2),
                      encoding="utf-8")
        print(f"\n清单已写出：{mp}")
    print(f"\n输出目录：{outdir}  共 {len(manifest)} 张")
    return 0


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    return cmd_batch(a) if a.cmd == "batch" else cmd_one(a)


if __name__ == "__main__":
    sys.exit(main())
