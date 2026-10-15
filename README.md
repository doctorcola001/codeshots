# CodeShots

[English](README.md) | [简体中文](README.zh-CN.md)

Render source snippets into syntax-highlighted PNGs **without opening an editor**.
Made for reports, documentation, and batch code illustrations, with line numbers,
light/dark themes, and Chinese/English character-cell layout.

These are rendered illustrations, not real IDE screenshots. Input code is never executed.

## Install

Requires Python 3.10+. From the project directory:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install .
.venv/Scripts/codeshots --version
```

On macOS/Linux, use `.venv/bin/python` and `.venv/bin/codeshots` instead.
Alternatively, install `requirements.txt` and run `python codeshots.py`.
Replace `codeshots` below with the executable inside your virtual environment if it is not on PATH.

## Quick start

```powershell
codeshots file main.cpp --start 10 --end 35 --lang cpp -o fig.png
codeshots nb demo.ipynb --cell 0 -o notebook.png
codeshots text snippet.txt --lang java -o snippet.png
codeshots batch examples/demo_specs.json -o shots --manifest shots/index.json
```

Source files must use UTF-8. Line ranges are **1-based and inclusive**;
Notebook cell indices are **0-based**. Notebook outputs are not rendered.

| Option | Default | Purpose |
| --- | --- | --- |
| `--bg` | `light` | Light or dark background |
| `--style` | Theme-dependent | Pygments style |
| `--font-size` | `20` | Font size in pixels |
| `--max-cells` | `72` | Wrap width in character cells |
| `--cont-indent` | `8` | Continuation indentation |
| `--pad` | `16` | Image padding |
| `--gutter-pad` | `11` | Line-number gutter spacing |
| `--no-numbers` | Off | Hide line numbers |

Half-width characters occupy one cell and full-width characters two. Width must
be at least 2; continuation indentation must be between 0 and width minus 2.
Run `codeshots --help` or a subcommand with `--help` for its supported options;
batch exposes only a subset of the single-image CLI overrides.

## Batch configuration

```json
{
  "defaults": {"bg": "light", "font_size": 20, "max_cells": 72},
  "items": [
    {"id": "fig-1", "kind": "file", "path": "main.cpp",
     "start": 10, "end": 35, "out": "fig1.png", "caption": "Core implementation"}
  ]
}
```

- Input paths are relative to the configuration file; absolute paths also work.
- Supported kinds: `file`, `notebook`, and `text`. Notebook items require `cell`.
- Precedence: CLI overrides > item > defaults > built-in defaults.
- JSON option names use underscores, such as `font_size` and `max_cells`.
- An explicit output directory is relative to the working directory; by default,
  output goes to `shots` beside the configuration file.
- The manifest has a top-level `shapes` array with IDs, captions, output/source
  paths, dimensions, source-line counts, and rendered-row counts.
- **Inspect manifests before sharing: they contain source paths.**

## Fonts and limitations

Primarily designed for Windows, using installed Consolas and Microsoft YaHei.
Fonts are not bundled. Pillow's default font is used as a fallback and may lack
Chinese glyphs. macOS/Linux CJK font configuration is not yet implemented.
The installation commands above do not imply verified cross-platform font support.

Repeatable rendering requires the same source, options, fonts, and dependency
versions. Pixel-identical output across environments is not guaranteed.
The tool cannot capture editor UI, compiler output, debugger state, or runtime windows.
CLI messages are currently in Chinese.

## Verification and release

The batch demo is self-contained and uses this project's source as its input.
Run the batch command above to generate three images, then inspect Chinese text,
line wrapping, and both themes. Release notes/checklist: [RELEASING.md](RELEASING.md) (Chinese).

## License

[MIT](LICENSE). No PyPI release has been made by this project.
