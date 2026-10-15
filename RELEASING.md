# 发布检查清单

- 已确认 MIT 许可证，LICENSE 与包元数据已同步。
- 确认托管平台、账号、仓库名及公开范围；PyPI 名称可用性尚未核实。
- 仅发布本目录，不要将父目录的其他项目和虚拟环境加入仓库。
- examples/report_specs.json 是本地私有配置，已忽略，不应提交。
- manifest 包含源文件路径，分享前检查；不得将渲染图冒充真实 IDE 或运行截图。
- 用 python -m pip install . 验证安装，再用 codeshots --version 检查入口。
- 用 codeshots batch examples/demo_specs.json -o shots --manifest shots/index.json 生成示例，并检查中文与深浅色效果。
- 不同系统、字体、依赖版本可能产生不同像素结果；Windows 以外的中文字体支持尚未验证。
- 推送前用 git diff --cached 审查全部内容；不要自动公开未经检查的源码。
