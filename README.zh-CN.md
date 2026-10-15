# CodeShots

[English](README.md) | [简体中文](README.zh-CN.md)

无需打开编辑器，将源码片段渲染成带语法高亮、行号和中英字符格排版的 PNG。
适合实验报告、技术文档和批量代码插图。图片由源码生成，不是真实 IDE 截图，也不会执行输入代码。



## 安装

需要 Python 3.10+。在项目根目录执行：

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install .
.venv/Scripts/codeshots --version
```

也可用 `python -m pip install -r requirements.txt` 后运行 `python codeshots.py`。
macOS / Linux 的可执行文件位于 `.venv/bin/`；中文字体支持仍有限，命令行提示目前为中文。
安装后下列示例的 `codeshots` 可替换为 `.venv/Scripts/codeshots`。

## 快速开始

```powershell
codeshots file main.cpp --start 10 --end 35 --lang cpp -o fig.png
codeshots nb demo.ipynb --cell 0 -o notebook.png
codeshots text snippet.txt --lang java -o snippet.png
codeshots batch examples/demo_specs.json -o shots --manifest shots/index.json
```

源码使用 UTF-8。行号从 1 开始，两端包含；Notebook cell 下标从 0 开始。
支持 `--bg light|dark`、`--style`、`--font-size`、`--max-cells`、`--cont-indent`、`--pad`、`--gutter-pad` 和 `--no-numbers`。
完整参数见 `codeshots --help` 及各子命令的 `--help`。
默认字号 20、列宽 72、续行缩进 8；半角占 1 格，全角占 2 格，超宽自动折行。
列宽至少为 2，续行缩进不能超过列宽减 2。

## 批量配置

```json
{
  "defaults": {"bg": "light", "font_size": 20, "max_cells": 72},
  "items": [
    {"id": "fig-1", "kind": "file", "path": "main.cpp",
     "start": 10, "end": 35, "out": "fig1.png", "caption": "核心实现"}
  ]
}
```

- 输入路径相对配置文件所在目录解析；也接受绝对路径。
- kind 支持 file、notebook 和 text；notebook 需要 cell 字段。
- 参数优先级为命令行 > item > defaults > 内置默认。
- JSON 参数使用下划线，例如 font_size 和 max_cells。
- 输出目录相对当前工作目录解析，未指定时使用配置目录下的 shots。
- manifest 顶层字段为 shapes，每项包含 id、caption、out、src、width、height、src_lines 和 render_rows 等信息。
- manifest 包含源文件路径，对外分享前请检查隐私。

## 字体与限制

优先使用 Windows 的 Consolas 和微软雅黑，不随项目分发字体。缺失时回退 Pillow 默认字体，中文可能无法显示。
目前主要面向 Windows；macOS / Linux 的中文字体配置尚未完善。
固定源码、参数、字体及依赖环境便于复现；不保证跨操作系统或依赖版本逐像素相同。
不支持截取编辑器窗口、编译输出、调试状态或 Notebook 输出单元。

## 验证与发布

批量示例自包含，使用本项目源码作为素材，无需外部课程文件。
运行快速开始中的 batch 命令应生成三张图，再人工检查中文、折行及深浅配色。
发布流程和待确认事项见 RELEASING.md。
本项目采用 MIT 许可证，详见 LICENSE。
