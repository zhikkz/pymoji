# pymoji

使用 emoji 语法、支持多语种名字的编程语言。正式版本：**1.0**。解释器仅依赖 Python 3.8+ 标准库。

```sh
python pymoji.py examples/你好世界.pymoji
python pymoji.py -c '总数⬅️1➕2🔚📢总数'
```

[语言使用说明](docs/language.md)包含生成和执行 pymoji 代码所需的全部规则。

规范代码排成矩形；空格、缩进和实际换行不改变程序含义。

```sh
python pymoji.py 程序.pymoji --format --width 48 -o 成品.pymoji
python pymoji.py 成品.pymoji --check-rectangle
python pymoji.py 成品.pymoji
```

`--format` 和 `--check-rectangle` 不执行程序。示例位于 [examples](examples)，运行测试：

```sh
python -m unittest -v test_pymoji
```
