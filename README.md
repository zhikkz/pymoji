# pymoji

使用 emoji 表达程序结构的编程语言，支持中文、假名、字母、下划线和 emoji 标识符。单文件解释器，仅依赖 Python 3.8+ 标准库。

支持变量、列表、字典、条件、循环、函数、递归和闭包，以及类型转换、文字处理、舍入与小数格式、切片、映射和筛选。`🔚` 分隔语句，`👉👈` 表示代码块，`🤜🤛` 表示括号，`🔤🔡` 包围文字；文字内可以直接写括号、引号等字符。

[语言使用说明](docs/language.md) · [版本更新](CHANGELOG.md) · [发行版](https://github.com/zhikkz/pymoji/releases) · [示例程序](examples) · [反馈问题](https://github.com/zhikkz/pymoji/issues/new/choose)

## 快速开始

安装 Python 3.8 或更新版本，然后克隆仓库；也可在发行版页面下载并解压源码。

```sh
git clone https://github.com/zhikkz/pymoji.git
cd pymoji
python pymoji.py examples/你好世界.pymoji
```

输出：`总数 7`。

也可以直接运行一段代码：

```sh
python pymoji.py -c '总数⬅️1➕2🔚📢总数'
```

输出：`3`。命令行中的单引号由 shell 处理，不属于 pymoji 源码。

1.1 支持将文字转为数字，内置函数同时提供 emoji 名字与中文别名：

```sh
python pymoji.py -c '📢🔢🤜🔤123🔡🤛➕1'
python pymoji.py -c '📢求和🤜映射🤜整数,分割🤜🔤12,34,56🔡,🔤,🔡🤛🤛🤛'
```

依次输出 `124`、`102`。字符串数据中的空白仍通过 `🛡️⬜` 等转义表示，保持任意矩形排版不改变程序含义。

1.2 加入四舍五入、小数格式和字典，可用于计数与记忆化：

```sh
python pymoji.py -c '📢四舍五入🤜0.1➕0.2,2🤛,小数格式🤜0.1➕0.2,2🤛'
python pymoji.py examples/字典与数值.pymoji
```

第一条输出 `0.3 0.30`；第二条演示字频统计和带缓存的斐波那契函数。

## 示例程序

| 程序 | 内容 |
| --- | --- |
| [你好世界](examples/你好世界.pymoji) | 汉字变量、赋值、计算和输出 |
| [函数与列表](examples/函数与列表.pymoji) | 混合标识符、闭包、列表追加和排序 |
| [文字与数据](examples/文字与数据.pymoji) | 自由文字、类型转换、拆分连接、切片、映射筛选 |
| [字典与数值](examples/字典与数值.pymoji) | 小数格式、字频统计、字典与记忆化 |
| [FizzBuzz](examples/FizzBuzz.pymoji) | 范围循环和条件分支 |
| [输入回显](examples/输入回显.pymoji) | 逐行读取并回显，EOF 时结束 |
| [接雨水](examples/接雨水.pymoji) | 双指针、单调栈和随机数据交叉验证 |

```sh
python pymoji.py examples/接雨水.pymoji --seed 1
```

## 排版与调试

规范代码排成矩形；空格、缩进和实际换行不改变程序含义。

```sh
python pymoji.py 程序.pymoji --format --width 48 -o 成品.pymoji
python pymoji.py 成品.pymoji --check-rectangle
python pymoji.py 成品.pymoji --tokens
python pymoji.py --help
```

`--format`、`--check-rectangle` 和 `--tokens` 均不执行程序。源码使用 UTF-8，扩展名建议为 `.pymoji`。

源码行数、执行步数、输入输出行数不设固定上限；内存、调用深度和整数保护详见[运行选项与边界](docs/language.md#运行选项与边界)。

## 开发

运行标准库测试：

```sh
python -m unittest -v test_pymoji
```

- [pymoji.py](pymoji.py)：解释器、命令行入口和矩形排版工具。
- [docs/language.md](docs/language.md)：完整而精简的语言使用说明。
- [examples](examples)：可直接运行的示例。
- [test_pymoji.py](test_pymoji.py)：语法、执行、输入输出及排版验证。

提交修改或反馈问题前，请参阅[贡献指南](CONTRIBUTING.md)。

可用 `python benchmarks/runtime.py` 测量循环与递归；用 `--compare-ref main` 在同一 Python 进程中对照 Git 中的解释器版本。结果取多次运行的中位数，不作为 CI 时间门槛。

## 许可证

本项目使用 [MIT License](LICENSE)，允许商业使用、修改和分发，须保留版权与许可声明。Copyright 2026 zhikkz。
