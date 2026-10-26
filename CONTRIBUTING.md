# 贡献指南

## 反馈问题

请在 [Issues](https://github.com/zhikkz/pymoji/issues/new/choose) 提供 Python 版本、操作系统、可复现的最小 `.pymoji` 程序、输入数据、预期结果和实际输出或报错。

## 提交修改

使用 Python 3.8+，保持解释器和测试仅依赖标准库。提交前运行：

```sh
python -m unittest -v test_pymoji
```

修复语义问题时添加能复现该问题的测试；调整语法或行为时同步更新 [语言使用说明](docs/language.md)。说明书以简洁的使用规则和必要示例为主。

示例源码保留 UTF-8 和行尾补齐空格；修改后可使用 `--format --width 48` 重新排版，再用 `--check-rectangle` 检查。

性能修改可用 `python benchmarks/runtime.py --compare-ref main` 对照改动前后的循环与递归耗时；同时保留资源保护与语义测试。

## 许可证

项目采用 [Apache License 2.0](LICENSE)。提交贡献即表示你有权提交这些内容，并同意以同一许可证授权该贡献。
