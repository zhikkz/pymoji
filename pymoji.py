#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
# Copyright 2026 zhikkz
"""
pymoji 解释器 v1.3
=======================

pymoji 是一门使用 emoji 语法、支持多语种名字、以矩形排版为规范的编程语言。
本文件就是它的完整实现（只依赖 Python 3.8+ 标准库），处理流程是：

    源代码 ──① 字符检查 + 忽略排版空白 + 词法分析──▶ 记号（Token）
           ──② 语法分析────────────▶ 语法树（AST）
           ──③ 树遍历解释执行──────▶ 运行结果

用法：
    python pymoji.py 程序.pymoji
    python pymoji.py -c '总数⬅️1➕2🔚📢总数'
    python pymoji.py 程序.pymoji --check         # 只检查语法，不执行
    python pymoji.py -                         # 从标准输入读取源码，读到 EOF 后执行
    python pymoji.py 程序.pymoji --max-mem 512 --max-depth 3000
    python pymoji.py 程序.pymoji --tokens          # 只做词法分析，列出记号（调试用）
    python pymoji.py 程序.pymoji --format --width 48 --output 矩形.pymoji
    python pymoji.py 矩形.pymoji --check-rectangle

物理空白在所有位置都被忽略，包括名字、数字、文字和注释内部。
🔚 表示逻辑换行，👉 / 👈 表示进入 / 离开代码块，🤜 / 🤛 代替括号，
🔤 / 🔡 包围文字。文字中的空格、换行、制表符分别写作 🛡️⬜、🛡️🔚、🛡️↔️。
无源代码行数、执行步数、输入输出行数或文字长度上限；保留可调内存、调用深度及整数保护。
"""

import argparse
from array import array
from bisect import bisect_right
from decimal import Decimal, ROUND_HALF_UP, localcontext
import functools
import operator
import os
import random
import re
import sys
import threading
import unicodedata

__version__ = '1.3'

# ════════════════════════════════════════════════════════════════
# 0. 资源上限（默认值，可用命令行参数修改）
# ════════════════════════════════════════════════════════════════
DEFAULT_MAX_MEM_MB = 256         # 程序运行期间最多额外占用多少内存（MB）
DEFAULT_MAX_DEPTH = 1000         # 函数最多一层套一层地调用多少层
DEPTH_HARD_LIMIT = 100_000       # --max-depth 能设的最大值
MAX_INT_BITS = 10_000            # 整数最多 10000 个二进制位（约 3000 位十进制）
TICK = 1024                      # 每走这么多步，顺便量一次内存
MEM_RECHECK = 4 * 1024 * 1024    # 大块数据累计新建了这么多字节，也立刻量一次内存
INF = float('inf')


# ════════════════════════════════════════════════════════════════
# 1. 错误类型
# ════════════════════════════════════════════════════════════════
class PymojiError(Exception):
    """pymoji 程序自身的错误。kind 取值：字符不合规 / 语法错误 / 运行错误 / 资源超限"""

    def __init__(self, kind, message, line=None):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.line = line
        self.trace = []  # 出错时的函数调用链 [(函数名, 调用所在行)]，由内向外


# ════════════════════════════════════════════════════════════════
# 2. 字形切分：把一行文字切成“人眼里的一个个字符”
# ════════════════════════════════════════════════════════════════
# 一个 emoji 在 Python 里可能由好几个码点组成，例如：
#   ⛰️ = U+26F0 + 变体选择符 U+FE0F        👍🏽 = 👍 + 肤色修饰符
#   1️⃣ = 1 + U+FE0F + 键帽 U+20E3           👨‍👩‍👧 = 👨 + ZWJ + 👩 + ZWJ + 👧
#   🇨🇳 = 两个“区域指示符”
# 解释器以“字形”为单位读源代码，这样每个 emoji 都被当成一个整体。

ZWJ = '‍'
KEYCAP = '⃣'
_VARIATION = {'︎', '️'}
_SKIN_TONES = {chr(c) for c in range(0x1F3FB, 0x1F400)}
_GENDER_SUFFIXES = (ZWJ + '♀', ZWJ + '♂')


def _is_extender(ch):
    """会“粘”在前一个字符上的码点：变体选择符、肤色、旗帜标签、组合符号（含键帽）。"""
    o = ord(ch)
    if 0xFE00 <= o <= 0xFE0F or 0x1F3FB <= o <= 0x1F3FF or 0xE0020 <= o <= 0xE007F:
        return True
    return unicodedata.category(ch) in ('Mn', 'Me', 'Mc')


def _is_regional(ch):
    return 0x1F1E6 <= ord(ch) <= 0x1F1FF


def split_graphemes(text):
    """把字符串切成字形列表（简化版 Unicode 字形规则，足够处理各种 emoji）。"""
    out = []
    i, n = 0, len(text)
    while i < n:
        start = i
        ch = text[i]
        i += 1
        if ch.isspace():                             # 空白自成一个字形，不和别的粘在一起
            out.append(ch)
            continue
        if _is_regional(ch) and i < n and _is_regional(text[i]):
            i += 1                                   # 两个区域指示符 = 一面国旗
        while i < n:
            c = text[i]
            if _is_extender(c):
                i += 1
            elif c == ZWJ and i + 1 < n and not text[i + 1].isspace():
                i += 2                               # 零宽连接符把下一个字符粘进来
            else:
                break
        out.append(text[start:i])
    return out


@functools.lru_cache(maxsize=1024)
def graphemes(text):
    """运行时使用：文字的长度、下标、遍历都以字形为单位。短文字的切分结果会被缓存。"""
    return tuple(split_graphemes(text))


SHORT_TEXT = 256                 # 不超过这么长的文字，切分结果放进公共缓存


def normalize(g):
    """同一个 emoji 的不同写法视为同一个：去掉变体选择符和肤色。"""
    if len(g) == 1:
        return g
    return ''.join(c for c in g if c not in _VARIATION and c not in _SKIN_TONES)


def keyword_form(g):
    """匹配关键字时还忽略性别后缀：🤷‍♂️ 🤷‍♀️ 🤷🏽 都算 🤷。"""
    g = normalize(g)
    for suffix in _GENDER_SUFFIXES:
        if g.endswith(suffix) and len(g) > len(suffix):
            return g[:-len(suffix)]
    return g


def digit_of(g):
    """Unicode 十进制数字 / 键帽数字 → ASCII 数字；不是数字则返回 None。"""
    g = normalize(g)
    if len(g) == 1:
        try:
            return str(unicodedata.decimal(g))
        except (ValueError, TypeError):
            return None
    if len(g) == 2 and g[1] == KEYCAP and '0' <= g[0] <= '9':
        return g[0]
    return None


# ════════════════════════════════════════════════════════════════
# 3. 记号表：每个 emoji / 符号对应什么意思
# ════════════════════════════════════════════════════════════════
_TOKENS = {
    # —— 流程控制 ——
    '🤔': 'IF', '🤷': 'ELSE', '🔁': 'WHILE', '🔂': 'FOR',
    '🛫': 'FROM', '🛬': 'TO', '👣': 'STEP', '∈': 'IN', ':': 'IN', '：': 'IN',
    '👉': 'BEGIN', '👈': 'END',
    '🏭': 'FUNC', '↩️': 'RETURN', '🛑': 'BREAK', '⏭️': 'CONTINUE',
    # —— 输入输出 ——
    '📢': 'PRINT', '💬': 'SAY', '👂': 'INPUT',
    # —— 赋值类语句 ——
    '⬅️': 'ASSIGN', '←': 'ASSIGN', '⬆️': 'INC', '↑': 'INC', '⬇️': 'DEC', '↓': 'DEC',
    '📥': 'PUSH',
    # —— 算术 ——
    '➕': '+', '+': '+', '＋': '+', '➖': '-', '-': '-', '−': '-', '－': '-',
    '✖️': '*', '*': '*', '×': '*', '＊': '*', '➗': '/', '/': '/', '÷': '/', '／': '/',
    '✂️': '//', '//': '//', '🥡': '%', '%': '%', '％': '%', '🚀': '^', '^': '^', '＾': '^',
    # —— 比较 ——
    '=': '==', '==': '==', '＝': '==', '⚖️': '==', '≠': '!=', '!=': '!=',
    '<': '<', '＜': '<', '>': '>', '＞': '>',
    '≤': '<=', '≦': '<=', '<=': '<=', '≥': '>=', '≧': '>=', '>=': '>=',
    # —— 逻辑 ——
    '🤝': 'AND', '🔀': 'OR', '🚫': 'NOT',
    # —— 列表与文字 ——
    '📍': 'AT', '📏': 'LEN', '📤': 'POP', '👀': 'PEEK',
    '🎁': 'LIST_OPEN', '🎀': 'LIST_CLOSE',
    # —— 显式布局与标点 ——
    '🔚': 'NEWLINE', '🤜': '(', '🤛': ')',
    # —— 字面量 ——
    '✅': 'TRUE', '❌': 'FALSE', '🕳️': 'NULL', '🔟': 'TEN', '💯': 'HUNDRED',
    # —— 标点（含中文全角写法） ——
    ',': ',', '，': ',', '、': ',',
}
TOKEN_TABLE = {keyword_form(k): v for k, v in _TOKENS.items()}
COMMENT = '💭'
STRING_OPEN, STRING_CLOSE, ESCAPE = '🔤', '🔡', '🛡'
STRING_ESCAPES = {'⬜': ' ', '🔚': '\n', '↔': '\t',
                  '🔤': '🔤', '🔡': '🔡', '🛡': '🛡️'}
FORBIDDEN = frozenset('()\"\'')
_NOT_KEYWORDS = ('NAME', 'NUM', 'STR', 'NEWLINE', 'EOF', '(', ')', ',')


# ════════════════════════════════════════════════════════════════
# 4. 词法分析：源代码 → 记号序列
# ════════════════════════════════════════════════════════════════
class Token:
    __slots__ = ('type', 'value', 'text', 'line', 'col')

    def __init__(self, type_, value, text, line, col):
        self.type = type_    # 记号类型，如 'NAME' 'NUM' 'IF' '+'
        self.value = value   # 数字的值 / 文字内容 / 名字的规范写法
        self.text = text     # 源代码里的原样写法（报错时显示）
        self.line = line
        self.col = col       # 第几个字形（从 1 数起）

    def __repr__(self):
        return f'Token({self.type}, {self.text!r}, 行{self.line})'


def describe(tok):
    if tok.type == 'NEWLINE':
        return '逻辑换行 🔚'
    if tok.type == 'EOF':
        return '文件结尾'
    return f'「{tok.text}」'


class SourceMap:
    """删除排版空白，但保留每个字形在原文件的物理位置。

    先删除空白再切分字形，因此在名字、数字甚至组合 emoji 的码点之间排版也不改变记号。
    用紧凑整数数组保存偏移，避免为每个字符创建一个行列元组。
    """
    def __init__(self, source):
        self.offsets = array('Q')
        self.starts = array('Q')
        self.line_starts = [0]
        self.source_length = len(source)
        chars = []
        for offset, ch in enumerate(source):
            if ch == '\n':
                self.line_starts.append(offset + 1)
            if offset == 0 and ch == '\ufeff':
                continue
            if ch.isspace():
                continue
            chars.append(ch)
            self.offsets.append(offset)
        self.gs = split_graphemes(''.join(chars))
        offset = 0
        for g in self.gs:
            self.starts.append(offset)
            offset += len(g)
        self.check_code_characters()

    def check_code_characters(self):
        """字符禁令只约束代码和注释，文字数据允许任意 Unicode 字符。

        在删除排版空白、合并字形之后识别文字，保证任意码点间插入空白仍不改变语义。
        注释中的 🔤 不开启文字；文字中转义的 🔡 不结束文字。
        """
        state, escaped = 'code', False
        for i, g in enumerate(self.gs):
            key = keyword_form(g)
            if state == 'string':
                if escaped:
                    escaped = False
                elif key == ESCAPE:
                    escaped = True
                elif key == STRING_CLOSE:
                    state = 'code'
                continue
            if state == 'code' and key == STRING_OPEN:
                state = 'string'
                continue
            for j, ch in enumerate(g):
                offset = self.offsets[self.starts[i] + j]
                if ch in FORBIDDEN:
                    self.char_error(offset, f'代码和注释中禁止使用 ASCII 括号和引号「{ch}」；'
                                    '括号请用 🤜🤛，文字请用 🔤🔡')
                cat = unicodedata.category(ch)
                if cat in ('Cc', 'Cs') or (cat == 'Cf' and ch != ZWJ
                                           and not 0xE0020 <= ord(ch) <= 0xE007F):
                    self.char_error(offset, f'不允许控制字符 U+{ord(ch):04X}')
            if key == COMMENT:
                state = 'comment'
            elif state == 'comment' and key == '🔚':
                state = 'code'

    def physical_location(self, offset):
        line = bisect_right(self.line_starts, offset)
        return line, offset - self.line_starts[line - 1] + 1

    def char_error(self, offset, message):
        line, col = self.physical_location(offset)
        raise PymojiError('字符不合规', f'{message}（物理列 {col}）', line)

    def location(self, index):
        offset = self.offsets[self.starts[index]] if index < len(self.gs) else self.source_length
        return self.physical_location(offset)

    def token(self, type_, value, start, end):
        line, col = self.location(start)
        return Token(type_, value, ''.join(self.gs[start:end]), line, col)


def _can_be_name(g):
    """允许 Unicode 字母（含汉字、假名）、下划线及原版的非 ASCII 符号 / emoji。"""
    if not g:
        return False
    if g == '_' or unicodedata.category(g[0])[0] == 'L' or unicodedata.category(g[0]) == 'Nl':
        return True
    if KEYCAP in g and g[0] in '#*':
        return True                                      # 保留原版的 #️⃣ / *️⃣ 名字
    if digit_of(g) is not None or unicodedata.category(g[0]) == 'Nd' or ord(g[0]) < 128:
        return False
    return not (unicodedata.category(g[0])[0] in 'PZM' or
                unicodedata.category(g[0]) in ('Cc', 'Cf', 'Cs'))


def tokenize(source):
    """物理空白完全无语义；只有 🔚 产生 NEWLINE，💭 到 🔚 / EOF 是注释。"""
    sm = SourceMap(source)
    gs = sm.gs
    tokens = []
    i, n = 0, len(gs)
    while i < n:
        g, key = gs[i], keyword_form(gs[i])
        if key == COMMENT:
            i += 1
            while i < n and keyword_form(gs[i]) != '🔚':
                i += 1
            continue
        if digit_of(g) is not None:
            i = _lex_number(sm, i, tokens)
            continue
        if key == STRING_OPEN:
            i = _lex_string(sm, i, tokens)
            continue
        if i + 1 < n and len(g) == 1 and len(gs[i + 1]) == 1 and g + gs[i + 1] in TOKEN_TABLE:
            pair = g + gs[i + 1]                         # == != <= >= //
            tokens.append(sm.token(TOKEN_TABLE[pair], None, i, i + 2))
            i += 2
            continue
        if key in TOKEN_TABLE:
            ttype = TOKEN_TABLE[key]
            if ttype in ('TEN', 'HUNDRED'):
                tokens.append(sm.token('NUM', 10 if ttype == 'TEN' else 100, i, i + 1))
            else:
                tokens.append(sm.token(ttype, None, i, i + 1))
            i += 1
            continue
        if key in (STRING_CLOSE, ESCAPE):
            line, col = sm.location(i)
            raise PymojiError('语法错误', f'「{g}」只能用在 🔤🔡 文字内部（物理列 {col}）', line)
        if _can_be_name(g):
            i = _lex_name(sm, i, tokens)
            continue
        line, col = sm.location(i)
        raise PymojiError('语法错误', f'不认识的符号「{g}」（物理列 {col}）', line)
    tokens.append(sm.token('EOF', None, n, n))
    return tokens


def _lex_number(sm, i, tokens):
    gs = sm.gs
    line_no, _ = sm.location(i)
    start = i
    digits = []
    while i < len(gs) and digit_of(gs[i]) is not None:
        digits.append(digit_of(gs[i]))
        i += 1
    text = ''.join(digits)
    is_float = False
    if i + 1 < len(gs) and gs[i] in ('.', '．') and digit_of(gs[i + 1]) is not None:
        i += 1
        frac = []
        while i < len(gs) and digit_of(gs[i]) is not None:
            frac.append(digit_of(gs[i]))
            i += 1
        text += '.' + ''.join(frac)
        is_float = True
    if len(text) > 3000:
        raise PymojiError('语法错误', '数字写得太长了（最多 3000 位）', line_no)
    value = float(text) if is_float else int(text)
    if value == INF:
        raise PymojiError('语法错误', '这个小数太大了，超出了能表示的范围', line_no)
    if i < len(gs) and _can_be_name(gs[i]) and keyword_form(gs[i]) not in TOKEN_TABLE \
            and keyword_form(gs[i]) not in (COMMENT, STRING_OPEN, STRING_CLOSE, ESCAPE):
        raise PymojiError('语法错误', '名字不能以数字开头；数字后接名字需要运算符或 🔚', line_no)
    tokens.append(sm.token('NUM', value, start, i))
    return i


def _lex_string(sm, i, tokens):
    gs = sm.gs
    line_no, col = sm.location(i)
    j = i + 1
    chars = []
    while j < len(gs):
        key = keyword_form(gs[j])
        if key == STRING_CLOSE:
            tokens.append(sm.token('STR', ''.join(chars), i, j + 1))
            return j + 1
        if key == STRING_OPEN:
            line, _ = sm.location(j)
            raise PymojiError('语法错误', '文字里的 🔤 请写成 🛡️🔤；文字结尾应为 🔡', line)
        if key == ESCAPE:
            if j + 1 < len(gs) and gs[j + 1] in ('u', 'U'):
                size = 4 if gs[j + 1] == 'u' else 8
                digits = ''.join(gs[j + 2:j + 2 + size])
                if len(digits) != size or not re.fullmatch('[0-9a-fA-F]{%d}' % size, digits):
                    line, _ = sm.location(j)
                    raise PymojiError('语法错误', f'Unicode 转义需要 {size} 位十六进制数字', line)
                value = int(digits, 16)
                if value > 0x10FFFF or 0xD800 <= value <= 0xDFFF:
                    line, _ = sm.location(j)
                    raise PymojiError('语法错误', 'Unicode 转义必须是有效的 Unicode 码点（不含代理项）', line)
                chars.append(chr(value))
                j += 2 + size
                continue
            if j + 1 >= len(gs) or keyword_form(gs[j + 1]) not in STRING_ESCAPES:
                line, _ = sm.location(j)
                raise PymojiError('语法错误', '🛡️ 后面需要 ⬜、🔚、↔️、🔤、🔡、🛡️ 或 Unicode 转义 u/U', line)
            chars.append(STRING_ESCAPES[keyword_form(gs[j + 1])])
            j += 2
            continue
        chars.append(gs[j])
        j += 1
    raise PymojiError('语法错误', f'文字没有结束：物理列 {col} 的 🔤 缺少配对的 🔡', line_no)


def _lex_name(sm, i, tokens):
    """名字忽略物理空白，以关键字 / 标点为边界；字母和组合标记按 NFC 规范化。"""
    gs = sm.gs
    start = i
    keys, raw = [], []
    while i < len(gs):
        g = gs[i]
        d = digit_of(g)
        if raw and d is not None:
            keys.append(d)                               # 📦2 与 📦2️⃣ 是同一个名字
        elif not _can_be_name(g) or keyword_form(g) in TOKEN_TABLE \
                or keyword_form(g) in (COMMENT, STRING_OPEN, STRING_CLOSE, ESCAPE) or d is not None:
            break
        else:
            keys.append(normalize(g))
        raw.append(g)
        i += 1
    tokens.append(sm.token('NAME', unicodedata.normalize('NFC', ''.join(keys)), start, i))
    return i


# ════════════════════════════════════════════════════════════════
# 5. 语法树节点
# ════════════════════════════════════════════════════════════════
class Node:
    __slots__ = ('line',)


def _node(name, *fields):
    """生成一个语法树节点类：第一个构造参数是行号，其余依次是各字段。"""
    def __init__(self, line, *values):
        self.line = line
        for f, v in zip(fields, values):
            setattr(self, f, v)
    return type(name, (Node,), {'__slots__': fields, '__init__': __init__})


# —— 表达式 ——
Const = _node('Const', 'value')                    # 数字、文字、✅ ❌ 🕳️
Name = _node('Name', 'key', 'text')                # 变量名
ListLit = _node('ListLit', 'items')                # 🎁 … 🎀
Index = _node('Index', 'obj', 'index')             # 列表📍位置
Call = _node('Call', 'func', 'args')               # 函数(参数…)
Unary = _node('Unary', 'op', 'operand')            # ➖x 📏x 📤x 👀x 🚫x
Logic = _node('Logic', 'op', 'left', 'right')      # 🤝 🔀
Compare = _node('Compare', 'ops', 'operands')      # = ≠ < > ≤ ≥（可连写）
Input = _node('Input')                             # 👂
# —— 语句 ——
Assign = _node('Assign', 'target', 'value')        # 🍎 ⬅️ 值
Push = _node('Push', 'target', 'value')            # 列表 📥 值
ExprStmt = _node('ExprStmt', 'expr')               # 单独一行的函数调用 / 📤 / 👂
Print = _node('Print', 'args', 'newline')          # 📢 / 💬
If = _node('If', 'cond', 'body', 'orelse')         # 🤔 … 👉 … 👈 🤷 👉 … 👈
While = _node('While', 'cond', 'body')             # 🔁 条件 👉 … 👈
ForRange = _node('ForRange', 'var', 'start', 'end', 'step', 'body')  # 🔂 x 🛫 a 🛬 b 👣 s
ForEach = _node('ForEach', 'var', 'iterable', 'body')                # 🔂 x ∈ 列表
FuncDef = _node('FuncDef', 'name', 'params', 'body', 'local_names')  # 🏭 名字(参数) 👉 … 👈
Return = _node('Return', 'value')                  # ↩️
Break = _node('Break')                             # 🛑
Continue = _node('Continue')                       # ⏭️


class Binary(Node):
    __slots__ = ('op', 'left', 'right', 'integer_op')

    def __init__(self, line, op, left, right):
        self.line, self.op, self.left, self.right = line, op, left, right
        self.integer_op = INTEGER_OPS.get(op)


class Update(Node):
    __slots__ = ('target', 'op', 'value', 'integer_op')

    def __init__(self, line, target, op, value):
        self.line, self.target, self.op, self.value = line, target, op, value
        self.integer_op = INTEGER_OPS[op]


BLOCK_STATEMENTS = (If, While, ForRange, ForEach, FuncDef)


def _collect_assigned(stmts, names):
    """找出函数体里所有被赋值的名字：它们都是这个函数自己的局部变量。"""
    for s in stmts:
        t = type(s)
        if t is Assign or t is Update:
            if type(s.target) is Name:
                names.add(s.target.key)
        elif t is ForRange or t is ForEach:
            names.add(s.var.key)
            _collect_assigned(s.body, names)
        elif t is If:
            _collect_assigned(s.body, names)
            if s.orelse:
                _collect_assigned(s.orelse, names)
        elif t is While:
            _collect_assigned(s.body, names)
        elif t is FuncDef:
            names.add(s.name.key)
    return names


# ════════════════════════════════════════════════════════════════
# 6. 语法分析：记号序列 → 语法树（递归下降）
# ════════════════════════════════════════════════════════════════
COMPARE_OPS = ('==', '!=', '<', '>', '<=', '>=')
END_OF_STATEMENT = ('NEWLINE', 'END', 'EOF')


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.depth = 0        # 处在几层 🤜🤛 或 🎁🎀 里面：忽略其中的逻辑换行 🔚
        self.loop_depth = 0   # 用来检查 🛑 ⏭️ 是否在循环里
        self.func_depth = 0   # 用来检查 ↩️ 是否在函数里

    # —— 基本工具 ——
    def peek(self):
        if self.depth:
            while self.tokens[self.pos].type == 'NEWLINE':
                self.pos += 1
        return self.tokens[self.pos]

    def advance(self):
        tok = self.peek()
        if tok.type != 'EOF':
            self.pos += 1
        return tok

    def check(self, *types):
        return self.peek().type in types

    def expect(self, ttype, message):
        tok = self.peek()
        if tok.type != ttype:
            hint = ''
            if ttype == 'NAME' and tok.type not in _NOT_KEYWORDS:
                hint = f'（「{tok.text}」是 pymoji 的关键字，不能拿来当名字）'
            self.error(f'{message}，但这里是{describe(tok)}{hint}', tok)
        return self.advance()

    def error(self, message, tok=None):
        tok = tok or self.peek()
        raise PymojiError('语法错误', message, tok.line)

    def skip_newlines(self):
        while self.tokens[self.pos].type == 'NEWLINE':
            self.pos += 1

    # —— 程序与代码块 ——
    def parse_program(self):
        return self.parse_statements(top_level=True)

    def parse_statements(self, top_level, opener=None):
        stmts = []
        while True:
            self.skip_newlines()
            tok = self.peek()
            if tok.type == 'EOF':
                if not top_level:
                    raise PymojiError('语法错误', '这里的 👉 一直没有等到配对的 👈', opener.line)
                return stmts
            if tok.type == 'END':
                if top_level:
                    self.error('多了一个 👈（前面没有和它配对的 👉）', tok)
                return stmts
            stmt = self.parse_statement()
            stmts.append(stmt)
            if type(stmt) in BLOCK_STATEMENTS:
                continue                     # 以 👈 收尾的语句后面，同一行可以接着写下一句
            tok = self.peek()
            if tok.type not in END_OF_STATEMENT:
                self.error(f'这句话后面多了{describe(tok)}。两句之间请加 🔚；要打印多个值请用逗号隔开', tok)

    def parse_block(self):
        self.skip_newlines()
        opener = self.expect('BEGIN', '这里需要 👉 来开始一段代码')
        body = self.parse_statements(top_level=False, opener=opener)
        self.expect('END', '这里需要 👈 来结束代码')
        return body

    # —— 语句 ——
    def parse_statement(self):
        tok = self.peek()
        t = tok.type
        if t == 'IF':
            return self.parse_if()
        if t == 'WHILE':
            return self.parse_while()
        if t == 'FOR':
            return self.parse_for()
        if t == 'FUNC':
            return self.parse_func()
        if t == 'RETURN':
            return self.parse_return()
        if t in ('BREAK', 'CONTINUE'):
            self.advance()
            if not self.loop_depth:
                self.error(f'{tok.text} 只能用在循环（🔁 / 🔂）里面', tok)
            return Break(tok.line) if t == 'BREAK' else Continue(tok.line)
        if t in ('PRINT', 'SAY'):
            return self.parse_print()
        if t == 'ELSE':
            self.error('🤷 前面要先有 🤔 条件 👉 … 👈', tok)
        if t == 'BEGIN':
            self.error('👉 只能跟在 🤔 / 🔁 / 🔂 / 🏭 后面，用来开始一段代码', tok)
        return self.parse_simple()

    def parse_if(self):
        tok = self.advance()
        cond = self.parse_expr()
        body = self.parse_block()
        orelse = None
        save = self.pos
        self.skip_newlines()                 # 🤷 可以和 👈 同一行，也可以另起一行
        if self.check('ELSE'):
            self.advance()
            self.skip_newlines()
            orelse = [self.parse_if()] if self.check('IF') else self.parse_block()
        else:
            self.pos = save
        return If(tok.line, cond, body, orelse)

    def parse_while(self):
        tok = self.advance()
        cond = self.parse_expr()
        self.loop_depth += 1
        body = self.parse_block()
        self.loop_depth -= 1
        return While(tok.line, cond, body)

    def parse_for(self):
        tok = self.advance()
        v = self.expect('NAME', '🔂 后面要先写循环变量的名字')
        var = Name(v.line, v.value, v.text)
        if self.check('FROM'):
            self.advance()
            start = self.parse_expr()
            self.expect('TO', '🛫 起点后面要用 🛬 写终点')
            end = self.parse_expr()
            step = None
            if self.check('STEP'):
                self.advance()
                step = self.parse_expr()
            self.loop_depth += 1
            body = self.parse_block()
            self.loop_depth -= 1
            return ForRange(tok.line, var, start, end, step, body)
        if self.check('IN'):
            self.advance()
            iterable = self.parse_expr()
            self.loop_depth += 1
            body = self.parse_block()
            self.loop_depth -= 1
            return ForEach(tok.line, var, iterable, body)
        self.error('循环变量后面要写「🛫 起点 🛬 终点」或者「∈ 列表」')

    def parse_func(self):
        tok = self.advance()
        n = self.expect('NAME', '🏭 后面要写函数的名字')
        self.expect('(', '函数名后面要用 🤜🤛 写参数')
        self.depth += 1
        params = []
        if not self.check(')'):
            while True:
                p = self.expect('NAME', '参数要写成名字')
                if any(q.key == p.value for q in params):
                    self.error(f'参数「{p.text}」重复了', p)
                params.append(Name(p.line, p.value, p.text))
                if not self.check(','):
                    break
                self.advance()
        self.expect(')', '参数写完要用 🤛 结束')
        self.depth -= 1
        saved_loop, self.loop_depth = self.loop_depth, 0
        self.func_depth += 1
        body = self.parse_block()
        self.func_depth -= 1
        self.loop_depth = saved_loop
        local_names = _collect_assigned(body, {p.key for p in params})
        return FuncDef(tok.line, Name(n.line, n.value, n.text), params, body, frozenset(local_names))

    def parse_return(self):
        tok = self.advance()
        if not self.func_depth:
            self.error('↩️ 只能用在 🏭 函数里面', tok)
        value = None if self.check(*END_OF_STATEMENT) else self.parse_expr()
        return Return(tok.line, value)

    def parse_print(self):
        tok = self.advance()
        args = []
        if not self.check(*END_OF_STATEMENT):
            args.append(self.parse_expr())
            while self.check(','):
                self.advance()
                args.append(self.parse_expr())
        return Print(tok.line, args, tok.type == 'PRINT')

    def parse_simple(self):
        tok = self.peek()
        expr = self.parse_expr()
        nxt = self.peek()
        if nxt.type in ('ASSIGN', 'INC', 'DEC', 'PUSH'):
            if not isinstance(expr, (Name, Index)):
                self.error(f'{nxt.text} 左边必须是一个名字（或「名字📍位置」）', nxt)
            self.advance()
            value = self.parse_expr()
            if nxt.type == 'ASSIGN':
                return Assign(nxt.line, expr, value)
            if nxt.type == 'PUSH':
                return Push(nxt.line, expr, value)
            return Update(nxt.line, expr, '+' if nxt.type == 'INC' else '-', value)
        if isinstance(expr, (Call, Input)) or (isinstance(expr, Unary) and expr.op == 'POP'):
            return ExprStmt(expr.line, expr)
        if isinstance(expr, Compare) and expr.ops[0] == '==':
            hint = '（想赋值请用 ⬅️；= 的意思是“判断是否相等”）'
        elif isinstance(expr, Name):
            hint = f'（想给「{expr.text}」赋值请用 ⬅️；如果它是函数，请写 {expr.text}🤜🤛）'
        else:
            hint = ''
        self.error('这条语句算出了一个值，却没有使用它' + hint, tok)

    # —— 表达式（优先级从低到高） ——
    def parse_expr(self):
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.check('OR'):
            tok = self.advance()
            left = Logic(tok.line, 'OR', left, self.parse_and())
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.check('AND'):
            tok = self.advance()
            left = Logic(tok.line, 'AND', left, self.parse_not())
        return left

    def parse_not(self):
        if self.check('NOT'):
            tok = self.advance()
            return Unary(tok.line, 'NOT', self.parse_not())
        return self.parse_compare()

    def parse_compare(self):
        left = self.parse_sum()
        if not self.check(*COMPARE_OPS):
            return left
        line = self.peek().line
        ops, operands = [], [left]
        while self.check(*COMPARE_OPS):           # 支持连写：0 ≤ 🐌 < 10
            ops.append(self.advance().type)
            operands.append(self.parse_sum())
        return Compare(line, ops, operands)

    def parse_sum(self):
        left = self.parse_product()
        while self.check('+', '-'):
            tok = self.advance()
            left = Binary(tok.line, tok.type, left, self.parse_product())
        return left

    def parse_product(self):
        left = self.parse_unary()
        while self.check('*', '/', '//', '%'):
            tok = self.advance()
            left = Binary(tok.line, tok.type, left, self.parse_unary())
        return left

    def parse_unary(self):
        if self.check('-', 'LEN', 'POP', 'PEEK'):
            tok = self.advance()
            return Unary(tok.line, tok.type, self.parse_unary())
        return self.parse_power()

    def parse_power(self):
        base = self.parse_postfix()
        if self.check('^'):                        # 右结合：2🚀3🚀2 = 2🚀(3🚀2)
            tok = self.advance()
            return Binary(tok.line, '^', base, self.parse_unary())
        return base

    def parse_postfix(self):
        node = self.parse_primary()
        while True:
            if self.check('('):
                node = self.parse_call(node)
            elif self.check('AT'):                 # 📍 后面只跟一个“小单元”，复杂的位置请加括号
                tok = self.advance()
                index = self.parse_primary()
                while self.check('('):
                    index = self.parse_call(index)
                node = Index(tok.line, node, index)
            else:
                return node

    def parse_call(self, func):
        tok = self.advance()
        self.depth += 1
        args = []
        if not self.check(')'):
            args.append(self.parse_expr())
            while self.check(','):
                self.advance()
                if self.check(')'):
                    break
                args.append(self.parse_expr())
        self.expect(')', '函数调用的参数写完要用 🤛 结束')
        self.depth -= 1
        return Call(tok.line, func, args)

    def parse_primary(self):
        tok = self.peek()
        t = tok.type
        if t in ('NUM', 'STR'):
            self.advance()
            return Const(tok.line, tok.value)
        if t in ('TRUE', 'FALSE', 'NULL'):
            self.advance()
            return Const(tok.line, {'TRUE': True, 'FALSE': False, 'NULL': None}[t])
        if t == 'INPUT':
            self.advance()
            return Input(tok.line)
        if t == 'NAME':
            self.advance()
            return Name(tok.line, tok.value, tok.text)
        if t == '(':
            self.advance()
            self.depth += 1
            expr = self.parse_expr()
            self.expect(')', '🤜 没有用 🤛 关上')
            self.depth -= 1
            return expr
        if t == 'LIST_OPEN':
            return self.parse_list()
        if t == 'AT':
            self.error('📍 前面要有一个列表或文字', tok)
        if t == 'NOT':
            self.error('🚫 的优先级很低，只能放在一个条件的最前面；放在这里请加括号：🤜🚫 …🤛', tok)
        self.error(f'这里需要一个值，但遇到了{describe(tok)}', tok)

    def parse_list(self):
        tok = self.advance()
        self.depth += 1
        items = []
        if not self.check('LIST_CLOSE'):
            items.append(self.parse_expr())
            while self.check(','):
                self.advance()
                if self.check('LIST_CLOSE'):
                    break
                items.append(self.parse_expr())
        nxt = self.peek()
        if nxt.type != 'LIST_CLOSE':
            if nxt.type == 'EOF':
                raise PymojiError('语法错误', '这里的 🎁 一直没有等到收尾的 🎀', tok.line)
            self.error(f'列表里的东西要用逗号隔开、最后用 🎀 收尾，但这里是{describe(nxt)}', nxt)
        self.advance()
        self.depth -= 1
        return ListLit(tok.line, items)


# ════════════════════════════════════════════════════════════════
# 7. 运行时的值
# ════════════════════════════════════════════════════════════════
#   数字 → int / float      文字 → str      列表 → list      字典 → Dictionary
#   ✅ ❌ → True / False      🕳️ → None       函数 → Function / Builtin

class Function:
    __slots__ = ('name', 'params', 'body', 'closure', 'local_names')

    def __init__(self, name, params, body, closure, local_names):
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure          # 定义函数时所在的作用域
        self.local_names = local_names  # 函数体里会被赋值的名字


class Builtin:
    __slots__ = ('name', 'fn', 'arities')

    def __init__(self, name, fn, arities):
        self.name = name
        self.fn = fn
        self.arities = arities          # 允许的参数个数；None 表示不限


class Dictionary:
    """保持插入顺序；内部键带类型标签，避免 Python 把 ✅、1 当成同一个键。"""
    __slots__ = ('data',)

    def __init__(self):
        self.data = {}              # (类型标签, 键) → (首次插入的键, 值)

    def __len__(self):
        return len(self.data)


def _dict_value_pairs(left, right):
    for key, (_, value) in left.data.items():
        yield value, right.data[key][1]


class Env:
    """一层作用域。全局一层；每调用一次函数新建一层，parent 指向函数定义处的作用域。"""
    __slots__ = ('vars', 'parent', 'local_names')

    def __init__(self, parent=None, local_names=None):
        self.vars = {}
        self.parent = parent
        self.local_names = local_names


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


class ReturnSignal:
    __slots__ = ('value',)

    def __init__(self, value):
        self.value = value


class _Enough(Exception):
    """内部用：要显示的文字已经够长了，提前停下。"""


def type_name(v):
    if v is None:
        return '空值🕳️'
    if v is True or v is False:
        return '真假值'
    t = type(v)
    if t is int or t is float:
        return '数字'
    if t is str:
        return '文字'
    if t is list:
        return '列表'
    if t is Dictionary:
        return '字典'
    if t is Function or t is Builtin:
        return '函数'
    return '未知的值'


def format_number(x):
    if type(x) is int:
        return str(x)
    if x != x:
        return '❓'
    if x == INF or x == -INF:
        return '∞' if x > 0 else '-∞'
    if x.is_integer() and abs(x) < 1e16:
        return str(int(x))            # 3.0 显示成 3
    s = repr(x)
    if 'e' in s:                      # 科学计数法里的 e 是字母，改写成 ×10^
        mantissa, exp = s.split('e')
        return f'{mantissa}×10^{int(exp)}'
    return s


def _mb(nbytes):
    mb = nbytes / 1048576
    return f'{mb:.1f}' if mb < 10 else f'{mb:,.0f}'


OP_SYMBOL = {'+': '➕', '-': '➖', '*': '✖️', '/': '➗', '//': '✂️', '%': '🥡', '^': '🚀'}
_NUMBER_RE = re.compile(r'[+-]?[0-9]+(\.[0-9]+)?')
_NUMBER_TYPES = frozenset((int, float))
_UNBOUND = object()


def _divide(a, b):
    return a // b if type(a) is int and type(b) is int and a % b == 0 else a / b


NUMERIC_OPS = {'+': operator.add, '-': operator.sub, '*': operator.mul,
               '/': _divide, '//': operator.floordiv, '%': operator.mod}
INTEGER_OPS = {op: NUMERIC_OPS[op] for op in ('+', '-', '*')}


# ════════════════════════════════════════════════════════════════
# 8. 内存测量：读取本进程用过的最大内存
# ════════════════════════════════════════════════════════════════
def _peak_memory_reader():
    """返回一个函数，读取本进程到目前为止用过的最大内存（字节）；这个系统读不到就返回 None。"""
    try:
        import resource                                    # Linux / macOS / BSD
        scale = 1 if sys.platform == 'darwin' else 1024    # macOS 的单位是字节，其他系统是 KB

        def read():
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale
        read()
        return read
    except Exception:
        pass
    try:
        import ctypes                                      # Windows
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
                (f, ctypes.c_size_t) for f in (
                    'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage',
                    'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]

        kernel32 = ctypes.WinDLL('kernel32')
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        get_info = kernel32.K32GetProcessMemoryInfo
        get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        get_info.restype = wintypes.BOOL
        process = kernel32.GetCurrentProcess()
        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)

        def read():
            if not get_info(process, ctypes.byref(counters), counters.cb):
                raise OSError('GetProcessMemoryInfo 调用失败')
            return max(counters.PeakWorkingSetSize, counters.PeakPagefileUsage)
        read()
        return read
    except Exception:
        return None


PEAK_MEMORY = _peak_memory_reader()


# ════════════════════════════════════════════════════════════════
# 9. 解释器：遍历语法树并执行
# ════════════════════════════════════════════════════════════════
class Interpreter:
    def __init__(self, out=None, inp=None, max_mem_mb=DEFAULT_MAX_MEM_MB,
                 max_depth=DEFAULT_MAX_DEPTH, seed=None):
        self.out = out if out is not None else sys.stdout
        self.inp = inp if inp is not None else sys.stdin
        self.max_mem = max_mem_mb * 1048576 if max_mem_mb and max_mem_mb > 0 else INF
        self.max_depth = max_depth if max_depth and max_depth > 0 else DEFAULT_MAX_DEPTH
        self.steps = 0
        self.next_tick = TICK                        # 工作量只用于定期测量内存，没有执行步数上限
        self.depth = 0
        self.read_mem = PEAK_MEMORY if self.max_mem != INF else None
        self.mem_base = self._read_memory() or 0     # 开始运行前的内存，作为基准
        self.mem_used = 0                            # 最近一次量到的、程序额外用掉的内存
        self.alloc_since = 0                         # 上次量过之后，新建的大块数据有多少字节
        self.long_text, self.long_glyphs = '', ()    # 最近一段长文字及其字形（见 glyphs）
        self.rng = random.Random(seed)
        self.globals = Env()
        for name, fn, arities in BUILTINS:
            self.globals.vars[normalize(name)] = Builtin(name, fn, arities)
        self.exec_table = {
            Assign: self.exec_assign, Update: self.exec_update, Push: self.exec_push,
            ExprStmt: self.exec_expr, Print: self.exec_print, If: self.exec_if,
            While: self.exec_while, ForRange: self.exec_for_range, ForEach: self.exec_for_each,
            FuncDef: self.exec_funcdef, Return: self.exec_return,
            Break: self.exec_break, Continue: self.exec_continue,
        }
        self.eval_table = {
            Const: self.eval_const, Name: self.lookup, ListLit: self.eval_list,
            Index: self.eval_index, Call: self.eval_call, Unary: self.eval_unary,
            Binary: self.eval_binary, Logic: self.eval_logic, Compare: self.eval_compare,
            Input: self.eval_input,
        }

    def run(self, program):
        self.exec_block(program, self.globals)

    # ─────────────── 报错与资源控制 ───────────────
    def fail(self, node, message):
        raise PymojiError('运行错误', message, node.line if node is not None else None)

    def tick(self, node):
        """按工作量定期测量内存，不检查或限制执行步数。"""
        self.measure_memory(node)
        self.next_tick = self.steps + TICK

    def charge(self, units, node):
        """记录大块操作的工作量，只用于内存检查的调度。"""
        if units:
            self.steps += units
            if self.steps > self.next_tick:
                self.tick(node)

    def _read_memory(self):
        if self.read_mem is None:
            return None
        try:
            return self.read_mem()
        except Exception:
            self.read_mem = None
            return None

    def measure_memory(self, node):
        self.alloc_since = 0
        now = self._read_memory()
        if now is None:
            return
        self.mem_used = max(0, now - self.mem_base)
        if self.mem_used > self.max_mem:
            raise PymojiError('资源超限', f'程序占用的内存超过了上限 {_mb(self.max_mem)} MB'
                                        f'（可用 --max-mem 调整）', node.line)

    def ensure_fits(self, nbytes, node):
        """新建大块数据之前先估一下：放不下就直接拒绝，不去真的分配。"""
        if self.mem_used + nbytes > self.max_mem:
            if nbytes > self.max_mem:
                msg = f'要新建的数据太大了（约 {_mb(nbytes)} MB），超过了内存上限 {_mb(self.max_mem)} MB'
            else:
                msg = (f'内存不够了：程序已经用了约 {_mb(self.mem_used)} MB，再新建约 {_mb(nbytes)} MB '
                       f'的数据就会超过上限 {_mb(self.max_mem)} MB')
            raise PymojiError('资源超限', msg + '（可用 --max-mem 调整）', node.line)

    def note_alloc(self, nbytes, node):
        """记下新建了多少大块数据；累计够多就立刻量一次内存，不等下一个 TICK。"""
        self.alloc_since += nbytes
        if self.alloc_since >= MEM_RECHECK:
            self.measure_memory(node)

    # ─────────────── 语句 ───────────────
    def exec(self, node, env):
        self.steps += 1
        if self.steps > self.next_tick:
            self.tick(node)
        return self.exec_table[type(node)](node, env)

    def exec_block(self, stmts, env):
        dispatch = self.exec_table
        for s in stmts:
            # 热路径直接分派，省去每条语句额外一次 Python 方法调用。
            self.steps += 1
            if self.steps > self.next_tick:
                self.tick(s)
            result = dispatch[type(s)](s, env)
            if result is not None:
                return result

    def exec_assign(self, node, env):
        value = self.eval(node.value, env)
        target = node.target
        if type(target) is Name:
            env.vars[target.key] = value
        else:
            seq, i = self.locate(target, env)
            if type(seq) is Dictionary:
                self.dict_set(seq, i, value, target)
            else:
                seq[i] = value

    def locate(self, target, env):
        """算出 📍 指向的列表位置或字典键（用于修改）。"""
        seq = self.eval(target.obj, env)
        if type(seq) is Dictionary:
            key = self.eval(target.index, env)
            self.dict_key(key, target)
            return seq, key
        if type(seq) is not list:
            if type(seq) is str:
                self.fail(target, '文字里的字符不能单独修改（可以拼出一段新的文字）')
            self.fail(target, f'只有列表才能用 📍 修改格子，这里是{type_name(seq)}')
        return seq, self.index_of(self.eval(target.index, env), len(seq), target)

    def exec_update(self, node, env):
        delta = self.eval(node.value, env)
        target = node.target
        if type(target) is Name:
            old = self.lookup(target, env)
            if type(old) is int and type(delta) is int:
                env.vars[target.key] = self.checked_number(node.integer_op(old, delta), node)
            else:
                env.vars[target.key] = self.binary(node.op, old, delta, node)
        else:
            seq, i = self.locate(target, env)
            if type(seq) is Dictionary:
                value = self.binary(node.op, self.dict_get(seq, i, target), delta, node)
                self.dict_set(seq, i, value, target)
            else:
                seq[i] = self.binary(node.op, seq[i], delta, node)

    def exec_push(self, node, env):
        seq = self.eval(node.target, env)
        if type(seq) is not list:
            self.fail(node, f'📥 只能往列表里放东西，这里是{type_name(seq)}')
        seq.append(self.eval(node.value, env))

    def exec_expr(self, node, env):
        self.eval(node.expr, env)

    def exec_print(self, node, env):
        """每算出一个值就立刻变成文字：📢 🍎, 📤🍎 显示的是 📤 之前的 🍎。"""
        buf = []
        for k, a in enumerate(node.args):
            v = self.eval(a, env)
            if k:
                buf.append(' ')
            t = type(v)
            if t is str:
                buf.append(v)
            elif t is list or t is Dictionary:
                self.render(v, self.emitter(buf), node)
            else:
                buf.append(self.scalar(v))
        if node.newline:
            buf.append('\n')
        self.out.write(''.join(buf))

    def emitter(self, buf):
        """显示长列表时用：攒够一批就先写出去，不在内存里拼一个巨大的字符串。"""
        out = self.out

        def emit(s):
            buf.append(s)
            if len(buf) >= 4096:
                out.write(''.join(buf))
                buf.clear()
        return emit

    def exec_if(self, node, env):
        if self.truthy(self.eval(node.cond, env)):
            return self.exec_block(node.body, env)
        elif node.orelse is not None:
            return self.exec_block(node.orelse, env)

    def exec_while(self, node, env):
        while True:
            self.steps += 1
            if self.steps > self.next_tick:
                self.tick(node)
            if not self.truthy(self.eval(node.cond, env)):
                break
            try:
                result = self.exec_block(node.body, env)
                if result is not None:
                    return result
            except BreakSignal:
                break
            except ContinueSignal:
                pass

    def exec_for_range(self, node, env):
        start = self.number(self.eval(node.start, env), node, '🛫 起点')
        end = self.number(self.eval(node.end, env), node, '🛬 终点')
        step = 1 if node.step is None else self.number(self.eval(node.step, env), node, '👣 步长')
        if step == 0:
            self.fail(node, '👣 步长不能是 0（那样永远走不到终点）')
        key = node.var.key
        k = 0
        while True:
            try:
                value = start + k * step                 # 用乘法算，避免小数累加的误差
            except OverflowError:
                self.fail(node, '范围循环的数字超出了能表示的范围')
            if (step > 0 and value > end) or (step < 0 and value < end):
                break
            self.steps += 1
            if self.steps > self.next_tick:
                self.tick(node)
            env.vars[key] = value
            try:
                result = self.exec_block(node.body, env)
                if result is not None:
                    return result
            except BreakSignal:
                break
            except ContinueSignal:
                pass
            k += 1

    def exec_for_each(self, node, env):
        coll = self.eval(node.iterable, env)
        if type(coll) is list:
            self.charge(len(coll) >> 6, node)
            items = list(coll)                           # 遍历开始那一刻的快照
        elif type(coll) is str:
            items = self.glyphs(coll, node)
        elif type(coll) is Dictionary:
            items = builtin_keys(self, [coll], node)
        else:
            self.fail(node, f'∈ 后面要是列表、文字或字典，这里是{type_name(coll)}')
        key = node.var.key
        for item in items:
            self.steps += 1
            if self.steps > self.next_tick:
                self.tick(node)
            env.vars[key] = item
            try:
                result = self.exec_block(node.body, env)
                if result is not None:
                    return result
            except BreakSignal:
                break
            except ContinueSignal:
                pass

    def exec_funcdef(self, node, env):
        env.vars[node.name.key] = Function(node.name.text, node.params, node.body, env, node.local_names)

    def exec_return(self, node, env):
        return ReturnSignal(None if node.value is None else self.eval(node.value, env))

    def exec_break(self, node, env):
        raise BreakSignal()

    def exec_continue(self, node, env):
        raise ContinueSignal()

    # ─────────────── 表达式 ───────────────
    def eval(self, node, env):
        kind = type(node)
        if kind is Const:
            return node.value
        if kind is Name:
            value = env.vars.get(node.key, _UNBOUND)
            if value is not _UNBOUND:
                return value
        return self.eval_table[kind](node, env)

    def eval_const(self, node, env):
        return node.value

    def lookup(self, node, env):
        key = node.key
        e = env
        while e is not None:
            value = e.vars.get(key, _UNBOUND)
            if value is not _UNBOUND:
                return value
            if e.local_names is not None and key in e.local_names:
                outer = e.parent
                while outer is not None and key not in outer.vars:
                    outer = outer.parent
                if outer is not None:
                    self.fail(node, f'「{node.text}」在这个函数里会被赋值，所以函数里的「{node.text}」是一个'
                                    f'新的局部变量，和外面的那个无关，而它现在还没有值。函数不能直接给外面的变量'
                                    f'重新赋值，可以用 ↩️ 把结果交出去')
                break
            e = e.parent
        self.fail(node, f'「{node.text}」还没有值（先用 ⬅️ 给它赋值）')

    def eval_list(self, node, env):
        return [self.eval(x, env) for x in node.items]

    def eval_index(self, node, env):
        seq = self.eval(node.obj, env)
        idx = self.eval(node.index, env)
        if type(seq) is list:
            return seq[self.index_of(idx, len(seq), node)]
        if type(seq) is str:
            gs = self.glyphs(seq, node)
            return gs[self.index_of(idx, len(gs), node)]
        if type(seq) is Dictionary:
            return self.dict_get(seq, idx, node)
        self.fail(node, f'📍 只能用在列表、文字或字典上，这里是{type_name(seq)}')

    def dict_key(self, key, node):
        t = type(key)
        if t is int or t is float:
            return int, key
        if t is str or t is bool or key is None:
            return t, key
        self.fail(node, f'字典的键必须是数字、文字、真假或空值，这里是{type_name(key)}')

    def dict_get(self, mapping, key, node):
        item = mapping.data.get(self.dict_key(key, node))
        if item is None:
            self.fail(node, f'字典里没有键「{self.brief(key)}」（可用 取值 指定默认值）')
        return item[1]

    def dict_set(self, mapping, key, value, node):
        canonical = self.dict_key(key, node)
        old = mapping.data.get(canonical)
        self.ensure_fits(160, node)
        mapping.data[canonical] = (key if old is None else old[0], value)
        self.note_alloc(160, node)

    def index_of(self, idx, length, node):
        if type(idx) is float and idx.is_integer():
            idx = int(idx)
        if type(idx) is not int:
            self.fail(node, f'📍 后面的位置要是整数，这里是{type_name(idx)}「{self.brief(idx)}」')
        if not 0 <= idx < length:
            if length == 0:
                self.fail(node, f'📍 位置 {idx} 不存在：这里是空的，一个格子都没有')
            self.fail(node, f'📍 位置 {idx} 超出范围：一共 {length} 个格子，能用的位置是 0 ~ {length - 1}')
        return idx

    def glyphs(self, text, node):
        """取文字的字形序列。长文字切分一次代价不小：按长度多算步数，并记住最近一段的结果。"""
        if len(text) <= SHORT_TEXT:
            return graphemes(text)
        if text is self.long_text or text == self.long_text:
            return self.long_glyphs
        self.charge(len(text), node)
        self.long_text, self.long_glyphs = text, tuple(split_graphemes(text))
        return self.long_glyphs

    def eval_call(self, node, env):
        func = self.eval(node.func, env)
        args = [self.eval(a, env) for a in node.args]
        return self.call(func, args, node)

    def call(self, func, args, node):
        if type(func) is Builtin:
            if func.arities is not None and len(args) not in func.arities:
                need = ' 或 '.join(str(a) for a in func.arities)
                self.fail(node, f'🏭{func.name} 需要 {need} 个参数，这里给了 {len(args)} 个')
            return func.fn(self, args, node)
        if type(func) is not Function:
            self.fail(node, f'{type_name(func)}「{self.brief(func)}」不是函数，不能调用')
        if len(args) != len(func.params):
            self.fail(node, f'🏭{func.name} 需要 {len(func.params)} 个参数，这里给了 {len(args)} 个')
        self.steps += 1
        if self.steps > self.next_tick:
            self.tick(node)
        if self.depth >= self.max_depth:
            raise PymojiError('资源超限', f'函数调用一层套一层，超过了 {self.max_depth:,} 层（递归忘了写结束条件？'
                                        f'确实需要的话可以用 --max-depth 调大）', node.line)
        env = Env(func.closure, func.local_names)
        for p, a in zip(func.params, args):
            env.vars[p.key] = a
        self.depth += 1
        try:
            result = self.exec_block(func.body, env)
            return None if result is None else result.value
        except PymojiError as e:
            e.trace.append((func.name, node.line))
            raise e.with_traceback(None)        # 丢掉 Python 自己的回溯记录，深层递归出错时不占内存
        except RecursionError:
            raise PymojiError('资源超限', '嵌套得太深了：函数一层套一层，Python 的调用栈不够用了'
                                        '（可以把递归改写成循环）', node.line) from None
        finally:
            self.depth -= 1

    def eval_unary(self, node, env):
        v = self.eval(node.operand, env)
        op = node.op
        if op == '-':
            if type(v) is int or type(v) is float:
                return -v
            self.fail(node, f'➖ 只能放在数字前面，这里是{type_name(v)}')
        if op == 'NOT':
            return not self.truthy(v)
        if op == 'LEN':
            if type(v) is list or type(v) is Dictionary:
                return len(v)
            if type(v) is str:
                return len(self.glyphs(v, node))
            self.fail(node, f'📏 只能量列表、文字或字典的长度，这里是{type_name(v)}')
        symbol = '📤' if op == 'POP' else '👀'
        if type(v) is not list:
            self.fail(node, f'{symbol} 只能用在列表上，这里是{type_name(v)}')
        if not v:
            self.fail(node, f'{symbol} 用在了空列表上：里面已经什么都没有了')
        return v.pop() if op == 'POP' else v[-1]

    def eval_binary(self, node, env):
        a, b = self.eval(node.left, env), self.eval(node.right, env)
        if node.integer_op is not None and type(a) is int and type(b) is int:
            return self.checked_number(node.integer_op(a, b), node)
        return self.binary(node.op, a, b, node)

    def binary(self, op, a, b, node):
        ta, tb = type(a), type(b)
        a_num = ta is int or ta is float
        b_num = tb is int or tb is float
        try:
            if a_num and b_num:
                r = self.power(a, b, node) if op == '^' else NUMERIC_OPS[op](a, b)
                return self.checked_number(r, node)
            if op == '+':
                if ta is str or tb is str:
                    return self.concat_text(self.text(a, node), self.text(b, node), node)
                if ta is list and tb is list:
                    n = len(a) + len(b)
                    self.ensure_fits(56 + 8 * n, node)
                    self.charge(n >> 6, node)
                    r = a + b
                    self.note_alloc(56 + 8 * n, node)
                    return r
            elif op == '*':
                if (ta is str or ta is list) and b_num:
                    return self.repeat(a, b, node)
                if (tb is str or tb is list) and a_num:
                    return self.repeat(b, a, node)
        except ZeroDivisionError:
            self.fail(node, '不能对 0 取余数' if op == '%' else '不能除以 0')
        except OverflowError:
            self.fail(node, '数字超出了能表示的范围')
        self.fail(node, f'{OP_SYMBOL[op]} 不能用在{type_name(a)}和{type_name(b)}之间')

    def concat_text(self, sa, sb, node):
        n = len(sa) + len(sb)
        self.ensure_fits(80 + 4 * n, node)
        self.charge(n >> 6, node)
        s = sa + sb
        self.note_alloc(80 + 4 * n, node)
        return s

    def power(self, a, b, node):
        if type(a) is int and type(b) is int and b >= 0:
            if abs(a) > 1 and b * (abs(a).bit_length() - 1) > MAX_INT_BITS:
                raise PymojiError('资源超限', '算出来的整数太大了（超过约 3000 位）', node.line)
            return a ** b
        if a == 0 and b < 0:
            self.fail(node, '0 不能做负数次方')
        r = a ** b
        if type(r) is complex:
            self.fail(node, '负数不能开分数次方（结果不是实数）')
        return r

    def checked_number(self, r, node):
        if type(r) is int:
            if r.bit_length() > MAX_INT_BITS:
                raise PymojiError('资源超限', '算出来的整数太大了（超过约 3000 位）', node.line)
        elif r != r or r == INF or r == -INF:
            self.fail(node, '数字超出了能表示的范围')
        return r

    def repeat(self, seq, k, node):
        """文字 ✖️ 次数、列表 ✖️ 次数。列表里的列表会被真正复制，得到互不干扰的格子。"""
        k = max(self.integer(k, node, '✖️ 复制的次数'), 0)
        if type(seq) is str:
            n = len(seq) * k
            self.ensure_fits(80 + 4 * n, node)
            self.charge(n >> 6, node)
            r = seq * k
            self.note_alloc(80 + 4 * n, node)
            return r
        n = len(seq) * k
        inner_bytes, inner_slots = self.nested_size(seq)
        cost = 56 + 8 * n + inner_bytes * k
        self.ensure_fits(cost, node)
        self.charge((n >> 6) + ((inner_slots * k) >> 2), node)
        if inner_bytes:
            r = [self.deep_copy(x, {}) if type(x) in (list, Dictionary) else x
                 for _ in range(k) for x in seq]
        else:
            r = seq * k
        self.note_alloc(cost, node)
        return r

    @staticmethod
    def nested_size(seq):
        """列表里嵌套的子列表一共占多少字节、有多少个格子（不算 seq 自己）。"""
        seen = {id(seq)}
        todo = [x for x in seq if type(x) in (list, Dictionary)]
        nbytes = slots = 0
        while todo:
            v = todo.pop()
            if id(v) in seen:
                continue
            seen.add(id(v))
            nbytes += 56 + (160 if type(v) is Dictionary else 8) * len(v)
            slots += len(v)
            children = (item[1] for item in v.data.values()) if type(v) is Dictionary else v
            todo.extend(x for x in children if type(x) in (list, Dictionary))
        return nbytes, slots

    def deep_copy(self, v, memo):
        if id(v) in memo:
            return memo[id(v)]
        new = Dictionary() if type(v) is Dictionary else []
        memo[id(v)] = new
        if type(v) is Dictionary:
            for key, (raw, value) in v.data.items():
                new.data[key] = (raw, self.deep_copy(value, memo)
                                 if type(value) in (list, Dictionary) else value)
        else:
            new.extend(self.deep_copy(x, memo) if type(x) in (list, Dictionary) else x for x in v)
        return new

    def eval_logic(self, node, env):
        left = self.truthy(self.eval(node.left, env))
        if node.op == 'AND':
            return left and self.truthy(self.eval(node.right, env))
        return left or self.truthy(self.eval(node.right, env))

    def eval_compare(self, node, env):
        left = self.eval(node.operands[0], env)
        for op, right_node in zip(node.ops, node.operands[1:]):
            right = self.eval(right_node, env)
            if not self.compare(op, left, right, node):
                return False
            left = right
        return True

    def compare(self, op, a, b, node):
        if op == '==':
            return self.equal(a, b, node)
        if op == '!=':
            return not self.equal(a, b, node)
        c = self.order(a, b, node)
        if op == '<':
            return c < 0
        if op == '>':
            return c > 0
        if op == '<=':
            return c <= 0
        return c >= 0

    def equal(self, a, b, node=None):
        """逐格比较；正在比较的对象对再次出现时视为相等，离开该层后移除。"""
        ta, tb = type(a), type(b)
        if ta not in (list, Dictionary) or tb is not ta:
            if (ta is int or ta is float) and (tb is int or tb is float):
                return a == b
            if ta is not tb:
                return False
            if ta is Function or ta is Builtin:
                return a is b
            if ta is str and node is not None:
                self.charge(max(len(a), len(b)) >> 6, node)
            return a == b
        if node is None:
            node = Const(None, None)
        active, stack = set(), []
        while True:
            self.charge(1, node)
            ta, tb = type(a), type(b)
            if (ta is int or ta is float) and (tb is int or tb is float):
                if a != b:
                    return False
            elif ta is not tb:
                return False                              # ✅ 不等于 1，"1" 也不等于 1
            elif ta is list or ta is Dictionary:
                if len(a) != len(b):
                    return False
                pair = (id(a), id(b))
                if a is not b and pair not in active:
                    if ta is Dictionary:
                        self.charge(len(a), node)
                        if a.data.keys() != b.data.keys():
                            return False
                        items = _dict_value_pairs(a, b)
                    else:
                        items = zip(a, b)
                    self.ensure_fits(512, node)
                    active.add(pair)
                    stack.append((iter(items), pair))
                    self.note_alloc(512, node)
            elif ta is Function or ta is Builtin:
                if a is not b:
                    return False
            else:
                if ta is str:
                    self.charge(max(len(a), len(b)) >> 6, node)
                if a != b:
                    return False
            while stack:
                items, pair = stack[-1]
                try:
                    a, b = next(items)
                    break
                except StopIteration:
                    stack.pop()
                    active.remove(pair)
            else:
                return True

    def order(self, a, b, node):
        """比较大小：返回 -1 / 0 / 1。只有 数字和数字、文字和文字、列表和列表 能比。"""
        ta, tb = type(a), type(b)
        if ((ta is int or ta is float) and (tb is int or tb is float)):
            return (a > b) - (a < b)
        active, stack = set(), []
        while True:
            self.charge(1, node)
            ta, tb = type(a), type(b)
            if ((ta is int or ta is float) and (tb is int or tb is float)) or (ta is str and tb is str):
                if ta is str:
                    self.charge(max(len(a), len(b)) >> 6, node)
                result = (a > b) - (a < b)
                if result:
                    return result
            elif ta is list and tb is list:
                pair = (id(a), id(b))
                if a is not b and pair not in active:
                    self.ensure_fits(512, node)
                    active.add(pair)
                    stack.append((iter(zip(a, b)), pair, (len(a) > len(b)) - (len(a) < len(b))))
                    self.note_alloc(512, node)
            else:
                # 列表的相等元素无需比较大小，例如 🎁✅🎀 与 🎁✅🎀。
                if not stack or not self.equal(a, b, node):
                    self.fail(node, f'{type_name(a)}和{type_name(b)}不能比较大小')
            while stack:
                items, pair, length_order = stack[-1]
                try:
                    a, b = next(items)
                    break
                except StopIteration:
                    stack.pop()
                    active.remove(pair)
                    if length_order:
                        return length_order
                    continue
            else:
                return 0

    def eval_input(self, node, env):
        try:
            self.out.flush()
        except Exception:
            pass
        line = self.inp.readline()
        if line == '':
            return None                                   # 没有更多输入了
        line = line.rstrip('\r\n')
        s = line.strip()
        if len(s) <= 3000 and _NUMBER_RE.fullmatch(s):    # 看起来像数字，就当数字
            value = float(s) if '.' in s else int(s)
            if value != INF and value != -INF:
                return value
        self.note_alloc(80 + 4 * len(line), node)
        return line

    # ─────────────── 显示与小工具 ───────────────
    @staticmethod
    def truthy(v):
        """什么算“真”：❌、🕳️、0、空文字、空列表、空字典算假，其余都算真。"""
        if v is None or v is False:
            return False
        if v is True:
            return True
        t = type(v)
        if t is int or t is float:
            return v != 0
        if t is str or t is list or t is Dictionary:
            return len(v) > 0
        return True

    def number(self, v, node, what):
        if type(v) is int or type(v) is float:
            return v
        self.fail(node, f'{what}要是数字，这里是{type_name(v)}')

    def integer(self, v, node, what):
        if type(v) is float and v.is_integer():
            v = int(v)
        if type(v) is not int:
            self.fail(node, f'{what}要是整数，这里是{type_name(v)}「{self.brief(v)}」')
        return v

    @staticmethod
    def scalar(v):
        """非列表的值怎么显示。"""
        if v is True:
            return '✅'
        if v is False:
            return '❌'
        if v is None:
            return '🕳️'
        t = type(v)
        if t is int or t is float:
            return format_number(v)
        if t is str:
            return v
        if t is Function or t is Builtin:
            return '🏭' + v.name
        return '?'

    def render(self, v, emit, node, nested=False, active=None):
        """把值一段一段地交给 emit。列表显示成 🎁1, 2🎀，列表里的文字带引号。node 为 None 时不计步数。"""
        t = type(v)
        if t is str:
            if nested:
                emit(STRING_OPEN)
                # 列表内的文字使用 emoji 引号和转义，不截断；输入数据可以含被禁用的源码字符。
                reverse = {' ': '🛡️⬜', '\n': '🛡️🔚', '\t': '🛡️↔️',
                           '🔤': '🛡️🔤', '🔡': '🛡️🔡'}
                for g in split_graphemes(v):
                    emit('🛡️🛡️' if keyword_form(g) == ESCAPE else reverse.get(g, g))
                emit(STRING_CLOSE)
            else:
                emit(v)
        elif t is list or t is Dictionary:
            if active is None:
                active = set()
            if id(v) in active:
                emit('🎁…🎀' if t is list else '🗃️…')        # 容器里装着它自己
                return
            active.add(id(v))
            if node is not None:
                self.charge(len(v) >> 2, node)
            if t is Dictionary:
                emit('🗃️🤜🎁')
                for k, (key, value) in enumerate(v.data.values()):
                    if k:
                        emit(', ')
                    emit('🎁')
                    self.render(key, emit, node, True, active)
                    emit(', ')
                    self.render(value, emit, node, True, active)
                    emit('🎀')
                emit('🎀🤛')
                active.remove(id(v))
                return
            emit('🎁')
            for k, x in enumerate(v):
                if k:
                    emit(', ')
                tx = type(x)
                if tx is list or tx is str or tx is Dictionary:
                    self.render(x, emit, node, True, active)
                else:
                    emit(self.scalar(x))
            emit('🎀')
            active.discard(id(v))
        else:
            emit(self.scalar(v))

    def text(self, v, node):
        """把值变成文字（用于 文字 ➕ 其他值）。"""
        if type(v) is str:
            return v
        if type(v) is not list and type(v) is not Dictionary:
            return self.scalar(v)
        parts = []
        self.render(v, parts.append, node)
        n = sum(map(len, parts))
        self.ensure_fits(80 + 4 * n, node)
        result = ''.join(parts)
        self.note_alloc(80 + 4 * n, node)
        return result

    def brief(self, v, limit=40):
        """报错信息里用的简短显示：太长就截断。"""
        parts = []
        total = 0

        def emit(s):
            nonlocal total
            parts.append(s)
            total += len(s)
            if total > limit:
                raise _Enough

        try:
            self.render(v, emit, None)
            return ''.join(parts)
        except _Enough:
            return ''.join(split_graphemes(''.join(parts)[:limit * 2])[:limit]) + '…'


# ════════════════════════════════════════════════════════════════
# 10. 内置函数（emoji 名字与中文别名均为可覆盖的普通名字）
# ════════════════════════════════════════════════════════════════
def _values(args):
    """👑(3, 9, 4) 和 👑(🎁3, 9, 4🎀) 两种写法都支持。"""
    if len(args) == 1 and type(args[0]) is list:
        return args[0]
    return args


def _pick(interp, args, node, symbol, sign):
    vals = _values(args)
    if not vals:
        interp.fail(node, f'🏭{symbol} 至少需要一个值（空列表里挑不出来）')
    kinds = set(map(type, vals))
    if kinds <= _NUMBER_TYPES or kinds == {str}:          # 全是数字或全是文字：直接用 Python 的 max/min
        interp.charge(len(vals) >> 6, node)
        return max(vals) if sign > 0 else min(vals)
    interp.charge(len(vals) >> 2, node)
    it = iter(vals)
    best = next(it)
    for v in it:
        if interp.order(v, best, node) * sign > 0:
            best = v
    return best


def builtin_max(interp, args, node):
    return _pick(interp, args, node, '👑', 1)


def builtin_min(interp, args, node):
    return _pick(interp, args, node, '🐜', -1)


def builtin_random(interp, args, node):
    """🎲(6) → 1~6；🎲(a, b) → a~b（都包含）。"""
    lo, hi = (1, args[0]) if len(args) == 1 else args
    lo = interp.integer(lo, node, '🎲 的范围')
    hi = interp.integer(hi, node, '🎲 的范围')
    if lo > hi:
        interp.fail(node, f'🎲 的范围不对：{lo} 比 {hi} 还大')
    return interp.rng.randint(lo, hi)


def builtin_sort(interp, args, node):
    """🔃(列表) → 从小到大排好的新列表，原列表不变。"""
    seq = args[0]
    if type(seq) is not list:
        interp.fail(node, f'🏭🔃 只能给列表排序，这里是{type_name(seq)}')
    n = len(seq)
    work = n * max(n.bit_length(), 1)
    interp.ensure_fits(56 + 8 * n, node)             # 先看内存够不够，再按工作量算步数
    kinds = set(map(type, seq))
    if kinds <= _NUMBER_TYPES or kinds == {str}:
        interp.charge(work >> 6, node)
        result = sorted(seq)
    else:
        interp.charge(work >> 2, node)
        result = sorted(seq, key=functools.cmp_to_key(lambda a, b: interp.order(a, b, node)))
    interp.note_alloc(56 + 8 * n, node)
    return result


def _numeric_text(interp, value, node):
    text = value.strip()
    if len(text) > 3000:
        interp.fail(node, '待转换的数字文字太长了（最多 3000 字符）')
    symbols = {'➕': '+', '＋': '+', '➖': '-', '−': '-', '－': '-', '．': '.'}
    return ''.join(digit_of(g) if digit_of(g) is not None else symbols.get(normalize(g), g)
                   for g in split_graphemes(text))


def builtin_int(interp, args, node):
    value = args[0]
    if len(args) == 2:
        if type(value) is not str:
            interp.fail(node, '🔢 指定进制时，第一个参数必须是文字')
        base = interp.integer(args[1], node, '🔢 的进制')
        if base != 0 and not 2 <= base <= 36:
            interp.fail(node, '🔢 的进制必须是 0 或 2–36；0 表示按 0b/0o/0x 前缀识别')
    else:
        base = 10
    if type(value) not in (str, int, float, bool):
        interp.fail(node, f'🔢 不能把{type_name(value)}转成整数')
    try:
        result = int(_numeric_text(interp, value, node), base) if type(value) is str else int(value)
    except (ValueError, OverflowError):
        interp.fail(node, '🔢 无法转成整数：需要有效的整数文字或有限数字')
    return interp.checked_number(result, node)


def builtin_float(interp, args, node):
    value = args[0]
    if type(value) not in (str, int, float, bool):
        interp.fail(node, f'🔣 不能把{type_name(value)}转成小数')
    try:
        if type(value) is str:
            value = _numeric_text(interp, value, node)
            # 与 format_number 的 ×10^ 科学计数写法互通；格式仍交给 float 校验。
            value = value.replace('×10^', 'e')
        result = float(value)
    except (ValueError, OverflowError):
        interp.fail(node, '🔣 无法转成小数：需要有效的数字文字或可表示的数字')
    return interp.checked_number(result, node)


def builtin_text(interp, args, node):
    return interp.text(args[0], node)


def builtin_bool(interp, args, node):
    return interp.truthy(args[0])


def builtin_type(interp, args, node):
    return {int: '整数', float: '小数', str: '文字', list: '列表',
            Dictionary: '字典', bool: '真假', type(None): '空值',
            Function: '函数', Builtin: '函数'}[type(args[0])]


def _text_arg(interp, value, node, symbol):
    if type(value) is not str:
        interp.fail(node, f'{symbol} 需要文字，这里是{type_name(value)}')
    return value


def _list_arg(interp, value, node, symbol):
    if type(value) is not list:
        interp.fail(node, f'{symbol} 需要列表，这里是{type_name(value)}')
    return value


def _sequence_arg(interp, value, node, symbol):
    if type(value) is str:
        return interp.glyphs(value, node)
    if type(value) is list:
        return value
    interp.fail(node, f'{symbol} 需要列表或文字，这里是{type_name(value)}')


def _make_list(interp, values, length, node, item_bytes=0):
    if length > sys.maxsize:
        raise PymojiError('资源超限', '要新建的列表太长，超出了宿主能表示的长度', node.line)
    cost = 56 + (8 + item_bytes) * length
    interp.ensure_fits(cost, node)
    interp.charge(length >> 6, node)
    result = list(values)
    interp.note_alloc(cost, node)
    return result


def _join_text(interp, parts, sep, node):
    length = sum(len(p) for p in parts) + len(sep) * max(0, len(parts) - 1)
    cost = 80 + 4 * length
    interp.ensure_fits(cost, node)
    interp.charge(length >> 6, node)
    result = sep.join(parts)
    interp.note_alloc(cost, node)
    return result


def _text_matches(interp, text, needle, node, start=0, limit=None):
    """返回不重叠的（码点起点、码点终点、字形下标），只匹配完整字形。

    用 str.find 搜索、紧凑数组检查边界，避免把组合 emoji 的一部分误认为匹配。
    """
    gs = interp.glyphs(text, node)
    cost = 8 * (len(gs) + 1)
    interp.ensure_fits(cost, node)
    offsets = array('Q', [0])
    for g in gs:
        offsets.append(offsets[-1] + len(g))
    interp.note_alloc(cost, node)
    interp.charge(len(text), node)
    pos, found = offsets[start], 0
    while limit is None or found < limit:
        pos = text.find(needle, pos)
        if pos < 0:
            return
        end = pos + len(needle)
        index = bisect_right(offsets, pos) - 1
        end_index = bisect_right(offsets, end) - 1
        if offsets[index] == pos and offsets[end_index] == end:
            yield pos, end, index
            found += 1
            pos = end
        else:
            pos += 1


def builtin_split(interp, args, node):
    text = _text_arg(interp, args[0], node, '🧩')
    if len(args) == 1 or args[1] is None:
        # 空白切分不拆字形；例如带组合标记的空白字形作为整体处理。
        gs = interp.glyphs(text, node)
        parts, start, offset = [], None, 0
        for g in gs:
            if g.isspace():
                if start is not None:
                    interp.ensure_fits(56 + 88 * (len(parts) + 1) + 4 * len(text), node)
                    parts.append(text[start:offset])
                    start = None
            elif start is None:
                start = offset
            offset += len(g)
        if start is not None:
            interp.ensure_fits(56 + 88 * (len(parts) + 1) + 4 * len(text), node)
            parts.append(text[start:])
    else:
        sep = _text_arg(interp, args[1], node, '🧩 的分隔符')
        if not sep:
            gs = interp.glyphs(text, node)
            return _make_list(interp, gs, len(gs), node)
        parts, last = [], 0
        for start, end, _ in _text_matches(interp, text, sep, node):
            interp.ensure_fits(56 + 88 * (len(parts) + 1) + 4 * len(text), node)
            parts.append(text[last:start])
            last = end
        interp.ensure_fits(56 + 88 * (len(parts) + 1) + 4 * len(text), node)
        parts.append(text[last:])
    interp.note_alloc(4 * len(text), node)
    return _make_list(interp, parts, len(parts), node, 80)  # 每段另有文字对象


def builtin_join(interp, args, node):
    seq = _list_arg(interp, args[0], node, '🪢')
    sep = _text_arg(interp, args[1], node, '🪢 的分隔符') if len(args) == 2 else ''
    interp.ensure_fits(56 + 8 * len(seq), node)
    parts = [interp.text(v, node) for v in seq]
    return _join_text(interp, parts, sep, node)


def builtin_strip(interp, args, node):
    text = _text_arg(interp, args[0], node, '🧼')
    gs = interp.glyphs(text, node)
    start, end = 0, len(gs)
    while start < end and gs[start].isspace():
        start += 1
    while end > start and gs[end - 1].isspace():
        end -= 1
    return _join_text(interp, gs[start:end], '', node)


def builtin_replace(interp, args, node):
    text, old, new = [_text_arg(interp, v, node, '🪄') for v in args[:3]]
    if not old:
        interp.fail(node, '🪄 要替换的旧文字不能为空')
    count = interp.integer(args[3], node, '🪄 的次数') if len(args) == 4 else None
    if count is not None and count < 0:
        interp.fail(node, '🪄 的次数不能为负数')
    if count == 0:
        return text
    parts, last, length = [], 0, 0
    for start, end, _ in _text_matches(interp, text, old, node, limit=count):
        length += start - last + len(new)
        interp.ensure_fits(80 + 4 * (length + len(text) - end) + 16 * (len(parts) + 2), node)
        parts.extend((text[last:start], new))
        last = end
    parts.append(text[last:])
    return _join_text(interp, parts, '', node)


def builtin_find(interp, args, node):
    value, needle = args[:2]
    seq = _sequence_arg(interp, value, node, '🔎')
    start = interp.integer(args[2], node, '🔎 的起点') if len(args) == 3 else 0
    if start < 0:
        start = max(0, len(seq) + start)
    if type(value) is str:
        _text_arg(interp, needle, node, '🔎 在文字中查找的值')
        if start > len(seq):
            return -1
        if not needle:
            return start
        return next((index for _, _, index in _text_matches(interp, value, needle, node, start)), -1)
    for i in range(start, len(seq)):
        interp.charge(1, node)
        if interp.equal(seq[i], needle, node):
            return i
    return -1


def builtin_slice(interp, args, node):
    value = args[0]
    seq = _sequence_arg(interp, value, node, '🍰')
    bounds = [None if v is None else interp.integer(v, node, '🍰 的位置和步长') for v in args[1:]]
    bounds += [None] * (3 - len(bounds))
    if bounds[2] == 0:
        interp.fail(node, '🍰 的步长不能是 0')
    indices = range(*slice(*bounds).indices(len(seq)))
    if type(value) is str:
        parts = _make_list(interp, (seq[i] for i in indices), len(indices), node)
        return _join_text(interp, parts, '', node)
    return _make_list(interp, (seq[i] for i in indices), len(indices), node)


def builtin_copy(interp, args, node):
    if type(args[0]) is str:
        return args[0]
    if type(args[0]) is Dictionary:
        return builtin_dict(interp, args, node)
    seq = _sequence_arg(interp, args[0], node, '📋')
    return _make_list(interp, seq, len(seq), node)


def builtin_reverse(interp, args, node):
    return builtin_slice(interp, [args[0], None, None, -1], node)


def builtin_range(interp, args, node):
    lo, hi = (1, args[0]) if len(args) == 1 else args[:2]
    lo, hi = (interp.integer(v, node, '🌱 的范围') for v in (lo, hi))
    step = interp.integer(args[2], node, '🌱 的步长') if len(args) == 3 else 1
    if step == 0:
        interp.fail(node, '🌱 的步长不能是 0')
    length = max(0, (hi - lo) // step + 1)
    values = range(lo, hi + (1 if step > 0 else -1), step)
    item_bytes = 32 + max(abs(lo).bit_length(), abs(hi).bit_length()) // 8
    return _make_list(interp, values, length, node, item_bytes)


def builtin_sum(interp, args, node):
    seq = _list_arg(interp, args[0], node, '🧮')
    result = interp.number(args[1], node, '🧮 的初值') if len(args) == 2 else 0
    for value in seq:
        interp.charge(1, node)
        result = interp.binary('+', result, interp.number(value, node, '🧮 的元素'), node)
    return result


def builtin_abs(interp, args, node):
    return interp.checked_number(abs(interp.number(args[0], node, '📐 的参数')), node)


def _rounded_decimal(interp, value, digits, node):
    if not -3000 <= digits <= 3000:
        interp.fail(node, '小数位数必须在 -3000 到 3000 之间')
    value = Decimal(str(interp.number(value, node, '待舍入的值')))
    precision = max(len(value.as_tuple().digits), value.adjusted() + 1, 1) + abs(digits) + 2
    interp.ensure_fits(128 + 4 * precision, node)
    interp.charge(precision >> 6, node)
    with localcontext() as context:
        context.prec = precision
        return value.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)


def builtin_round(interp, args, node):
    digits = interp.integer(args[1], node, '🎯 的小数位数') if len(args) == 2 else 0
    result = _rounded_decimal(interp, args[0], digits, node)
    value = int(result) if len(args) == 1 or type(args[0]) is int else float(result)
    return interp.checked_number(value, node)


def builtin_fixed(interp, args, node):
    digits = interp.integer(args[1], node, '🖋️ 的小数位数') if len(args) == 2 else 2
    if digits < 0:
        interp.fail(node, '🖋️ 的小数位数不能为负数')
    value = _rounded_decimal(interp, args[0], digits, node)
    # 避免显示舍入后为零的负号。
    result = format(abs(value) if value.is_zero() else value, 'f')
    interp.note_alloc(80 + 4 * len(result), node)
    return result


def _dict_arg(interp, value, node):
    if type(value) is not Dictionary:
        interp.fail(node, f'这里需要字典，收到的是{type_name(value)}')
    return value


def builtin_dict(interp, args, node):
    result = Dictionary()
    if not args:
        return result
    source = args[0]
    if type(source) is Dictionary:
        interp.ensure_fits(64 + 160 * len(source), node)
        interp.charge(len(source), node)
        result.data = source.data.copy()
        interp.note_alloc(64 + 160 * len(result), node)
        return result
    pairs = _list_arg(interp, source, node, '🗃️ 的键值对')
    interp.ensure_fits(64 + 160 * len(pairs), node)
    for pair in pairs:
        interp.charge(1, node)
        if type(pair) is not list or len(pair) != 2:
            interp.fail(node, '🗃️ 的每个键值对必须是恰有两项的列表')
        interp.dict_set(result, pair[0], pair[1], node)
    return result


def builtin_keys(interp, args, node):
    mapping = _dict_arg(interp, args[0], node)
    return _make_list(interp, (key for key, _ in mapping.data.values()), len(mapping), node)


def builtin_values(interp, args, node):
    mapping = _dict_arg(interp, args[0], node)
    return _make_list(interp, (value for _, value in mapping.data.values()), len(mapping), node)


def builtin_items(interp, args, node):
    mapping = _dict_arg(interp, args[0], node)
    return _make_list(interp, ([key, value] for key, value in mapping.data.values()),
                      len(mapping), node, 72)


def builtin_get(interp, args, node):
    mapping = _dict_arg(interp, args[0], node)
    item = mapping.data.get(interp.dict_key(args[1], node))
    return (args[2] if len(args) == 3 else None) if item is None else item[1]


def builtin_contains(interp, args, node):
    mapping = _dict_arg(interp, args[0], node)
    return interp.dict_key(args[1], node) in mapping.data


def builtin_delete(interp, args, node):
    mapping = _dict_arg(interp, args[0], node)
    canonical = interp.dict_key(args[1], node)
    if canonical not in mapping.data:
        interp.fail(node, f'字典里没有键「{interp.brief(args[1])}」')
    return mapping.data.pop(canonical)[1]


def _transform(interp, args, node, filtering):
    func, seq = args
    if type(func) not in (Function, Builtin):
        interp.fail(node, '映射和筛选的第一个参数必须是函数')
    _list_arg(interp, seq, node, '筛选' if filtering else '映射')
    snapshot = _make_list(interp, seq, len(seq), node)
    interp.ensure_fits(56 + 8 * len(snapshot), node)
    result = []
    for value in snapshot:
        interp.charge(1, node)
        mapped = interp.call(func, [value], node)
        if filtering:
            if interp.truthy(mapped):
                result.append(value)
        else:
            result.append(mapped)
    interp.note_alloc(56 + 8 * len(result), node)
    return result


def builtin_map(interp, args, node):
    return _transform(interp, args, node, False)


def builtin_filter(interp, args, node):
    return _transform(interp, args, node, True)


_BUILTIN_SPECS = [
    ('👑', '最大', builtin_max, None),
    ('🐜', '最小', builtin_min, None),
    ('🎲', '随机', builtin_random, (1, 2)),
    ('🔃', '排序', builtin_sort, (1,)),
    ('🔢', '整数', builtin_int, (1, 2)),
    ('🔣', '小数', builtin_float, (1,)),
    ('🧵', '文字', builtin_text, (1,)),
    ('🔘', '真假', builtin_bool, (1,)),
    ('🏷️', '类型', builtin_type, (1,)),
    ('🧩', '分割', builtin_split, (1, 2)),
    ('🪢', '连接', builtin_join, (1, 2)),
    ('🧼', '去空白', builtin_strip, (1,)),
    ('🪄', '替换', builtin_replace, (3, 4)),
    ('🔎', '查找', builtin_find, (2, 3)),
    ('🍰', '切片', builtin_slice, (1, 2, 3, 4)),
    ('📋', '复制', builtin_copy, (1,)),
    ('🪞', '反转', builtin_reverse, (1,)),
    ('🌱', '范围', builtin_range, (1, 2, 3)),
    ('🧮', '求和', builtin_sum, (1, 2)),
    ('📐', '绝对值', builtin_abs, (1,)),
    ('🎯', '四舍五入', builtin_round, (1, 2)),
    ('🖋️', '小数格式', builtin_fixed, (1, 2)),
    ('🗃️', '字典', builtin_dict, (0, 1)),
    ('🔑', '键', builtin_keys, (1,)),
    ('💎', '值', builtin_values, (1,)),
    ('🗂️', '键值对', builtin_items, (1,)),
    ('🫴', '取值', builtin_get, (2, 3)),
    ('🔐', '含键', builtin_contains, (2,)),
    ('🗑️', '删除', builtin_delete, (2,)),
    ('🗺️', '映射', builtin_map, (2,)),
    ('🧹', '筛选', builtin_filter, (2,)),
]
BUILTINS = [(name, fn, arities) for emoji, alias, fn, arities in _BUILTIN_SPECS
            for name in (emoji, alias)]


# ════════════════════════════════════════════════════════════════
# 11. 运行入口
# ════════════════════════════════════════════════════════════════
_ICONS = {'字符不合规': '🚫', '语法错误': '🧩', '运行错误': '💥', '资源超限': '⛔', '排版错误': '📐'}


def cell_width(g):
    """pymoji 规范列宽；不依赖终端或第三方库。组合字形不拆开计算。

    含 emoji 区码点、VS16、ZWJ 或键帽的字形为 2 列；否则取基字符
    East Asian Width：W / F 为 2 列，其余为 1 列；孤立组合标记为 0 列。
    """
    if any(0x1F000 <= ord(c) <= 0x1FAFF or 0x2600 <= ord(c) <= 0x27BF
           or c in ('\ufe0f', ZWJ, KEYCAP) for c in g):
        return 2
    bases = [c for c in g if not _is_extender(c) and unicodedata.category(c) != 'Cf']
    if not bases:
        return 0
    return max(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in bases)


def format_rectangle(source, width=48):
    """校验语法并排成等宽矩形。只移动 / 删除 / 添加物理空白，不执行程序。"""
    if type(width) is not int or width < 2:
        raise ValueError('矩形宽度必须是至少 2 的整数')
    Parser(tokenize(source)).parse_program()
    compact = ''.join(c for c in source.lstrip('\ufeff') if not c.isspace())
    rows, parts, used = [], [], 0
    for g in split_graphemes(compact):
        w = cell_width(g)
        if used + w > width:
            rows.append(''.join(parts) + ' ' * (width - used))
            parts, used = [], 0
        parts.append(g)
        used += w
    if parts or not rows:
        rows.append(''.join(parts) + ' ' * (width - used))
    return '\n'.join(rows) + '\n'


def check_rectangle(source):
    """检查语法及矩形排版，返回（规范列宽，物理行数）；不执行程序。"""
    Parser(tokenize(source)).parse_program()
    text = source[1:] if source.startswith('\ufeff') else source
    rows = text.replace('\r\n', '\n').split('\n')
    if rows and rows[-1] == '':
        rows.pop()
    if not rows:
        raise PymojiError('排版错误', '矩形至少需要一行；可用 --format 生成')
    expected = None
    for line, row in enumerate(rows, 1):
        if any(c.isspace() and c != ' ' for c in row):
            raise PymojiError('排版错误', '矩形行内只使用普通空格填充；请用 --format 重新排版', line)
        width = sum(cell_width(g) for g in split_graphemes(row))
        if expected is None:
            expected = width
        if width == 0 or width != expected:
            raise PymojiError('排版错误', f'这一行宽 {width} 列，矩形要求每行同为 {expected} 列；'
                            '可用 --format 重新排版', line)
    return expected, len(rows)


def format_error(err, source_lines):
    head = f'{_ICONS.get(err.kind, "💥")} {err.kind}'
    if err.line:
        head += f'（第 {err.line} 行）'
    out = [head]
    if err.line and 1 <= err.line <= len(source_lines):
        code = split_graphemes(source_lines[err.line - 1].rstrip('\r').strip())
        if code:
            shown = ''.join(code[:80]) + (' …' if len(code) > 80 else '')
            out.append(f'   {err.line} │ {shown}')
    out.append('   ' + err.message)
    if err.trace:
        calls = []                                   # 连续重复的调用合并成一项：递归出错时不刷屏
        for name, line in reversed(err.trace):
            item = f'第 {line} 行调用 🏭{name}'
            if calls and calls[-1][0] == item:
                calls[-1][1] += 1
            else:
                calls.append([item, 1])
        shown = [item if n == 1 else f'{item}（×{n:,}）' for item, n in calls]
        if len(shown) > 8:
            shown = shown[:3] + [f'…（中间省略 {len(shown) - 6} 处）…'] + shown[-3:]
        out.append('   📞 调用路径：' + ' → '.join(shown))
    return '\n'.join(out)


def _flush(stream):
    try:
        stream.flush()
    except BrokenPipeError:
        _silence_stdout()
    except Exception:
        pass


def _silence_stdout():
    """读输出的那一端已经关闭：把标准输出接到空设备上，免得 Python 退出时再报一次错。"""
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
    except Exception:
        pass


def run_source(source, out=None, err=None, inp=None, max_mem_mb=DEFAULT_MAX_MEM_MB,
               max_depth=DEFAULT_MAX_DEPTH, seed=None):
    """运行一段 pymoji 源代码。成功返回 0，出错返回 1（错误信息写到 err）。"""
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr
    if source.startswith('﻿'):
        source = source[1:]
    lines = source.split('\n')
    code = 1
    try:
        program = Parser(tokenize(source)).parse_program()     # 先整体检查语法，再开始运行
        Interpreter(out, inp, max_mem_mb, max_depth, seed).run(program)
        code = 0
    except PymojiError as e:
        _flush(out)
        err.write(format_error(e, lines) + '\n')
    except RecursionError:
        _flush(out)
        err.write('⛔ 资源超限\n   嵌套得太深了（递归层数、括号层数或列表套列表的层数太多）\n')
    except MemoryError:
        _flush(out)
        err.write('⛔ 资源超限\n   电脑内存不够用了\n')
    except BrokenPipeError:                                     # 输出被提前关掉了（比如接了 | head）
        _silence_stdout()
        return 0
    except Exception as e:                                      # 解释器自己的 bug
        _flush(out)
        err.write(f'🐞 解释器内部错误：{type(e).__name__}: {e}\n')
    _flush(out)
    return code


def dump_tokens(source, out=None):
    """--tokens：只做词法分析，把记号逐个列出来。"""
    out = out if out is not None else sys.stdout
    if source.startswith('﻿'):
        source = source[1:]
    try:
        tokens = tokenize(source)
    except PymojiError as e:
        sys.stderr.write(format_error(e, source.split('\n')) + '\n')
        return 1
    for tok in tokens:
        shown = '' if tok.type in ('NEWLINE', 'EOF') else tok.text
        extra = f'  → {tok.value!r}' if tok.type in ('NUM', 'STR') else ''
        out.write(f'{tok.line:>4}:{tok.col:<3} {tok.type:<10} {shown}{extra}\n')
    return 0


def _setup_stdio():
    """保证在 Windows 控制台、管道重定向等情况下都按 UTF-8 收发 emoji。"""
    for stream in (sys.stdout, sys.stderr, sys.stdin):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


def main(argv=None):
    # argparse 的 --help 和参数错误会提前输出并退出，也必须使用 UTF-8。
    _setup_stdio()
    ap = argparse.ArgumentParser(prog='pymoji', description=f'pymoji v{__version__}：emoji 语法、多语种名字、矩形排版。')
    ap.add_argument('file', nargs='?', help='程序文件（UTF-8，建议用 .pymoji）；- 表示从标准输入读取源码')
    ap.add_argument('-c', dest='code', metavar='代码', help='直接运行一段 pymoji 代码')
    ap.add_argument('--max-mem', type=int, default=DEFAULT_MAX_MEM_MB, metavar='MB',
                    help=f'运行时最多额外占用多少内存（MB），0 表示不限（默认 {DEFAULT_MAX_MEM_MB}）')
    ap.add_argument('--max-depth', type=int, default=DEFAULT_MAX_DEPTH, metavar='N',
                    help=f'函数最多嵌套调用多少层，最大 {DEPTH_HARD_LIMIT:,}（默认 {DEFAULT_MAX_DEPTH}）')
    ap.add_argument('--seed', type=int, default=None, metavar='N', help='🎲 的随机种子，让随机结果可以重现')
    modes = ap.add_mutually_exclusive_group()
    modes.add_argument('--check', action='store_true', help='只检查字符和语法，不执行；通过时不输出')
    modes.add_argument('--tokens', action='store_true', help='只做词法分析，列出所有记号（调试用）')
    modes.add_argument('--format', dest='format_code', action='store_true', help='只排成矩形，不运行')
    modes.add_argument('--check-rectangle', action='store_true', help='只检查语法和矩形排版，不运行')
    ap.add_argument('--width', type=int, default=48, metavar='N', help='矩形排版的列宽，至少 2（默认 48）')
    ap.add_argument('-o', '--output', metavar='文件', help='将矩形排版结果保存到文件，仅用于 --format')
    ap.add_argument('--version', action='version', version=f'pymoji {__version__}')
    args = ap.parse_args(argv)

    if args.file and args.code is not None:
        ap.error('文件和 -c 只能选择一个')
    if args.max_mem < 0:
        ap.error('--max-mem 不能小于 0')
    if not 1 <= args.max_depth <= DEPTH_HARD_LIMIT:
        ap.error(f'--max-depth 必须在 1 到 {DEPTH_HARD_LIMIT} 之间')
    if args.width < 2:
        ap.error('--width 至少为 2')
    if args.output and not args.format_code:
        ap.error('--output 仅用于 --format')

    if args.code is not None:
        source = args.code
    elif args.file:
        source_name = '标准输入' if args.file == '-' else args.file
        try:
            if args.file == '-':
                # 源码严格按 UTF-8 解码，不能沿用运行时输入的替换错误字符策略。
                stream = getattr(sys.stdin, 'buffer', None)
                source = sys.stdin.read() if stream is None else stream.read().decode('utf-8-sig')
            else:
                with open(args.file, encoding='utf-8-sig') as f:
                    source = f.read()
        except UnicodeDecodeError:
            sys.stderr.write(f'📂 {source_name} 不是 UTF-8 编码的文本，请转换为 UTF-8 后再试\n')
            return 2
        except OSError as e:
            sys.stderr.write(f'📂 无法读取 {source_name}：{e.strerror or e}\n')
            return 2
        except KeyboardInterrupt:
            sys.stderr.write('\n⏹️ 已中断\n')
            return 130
    else:
        ap.print_help()
        return 2

    if args.tokens:
        return dump_tokens(source)

    if args.check or args.format_code or args.check_rectangle:
        try:
            if args.check:
                Parser(tokenize(source)).parse_program()
            elif args.format_code:
                formatted = format_rectangle(source, args.width)
                if args.output:
                    with open(args.output, 'w', encoding='utf-8', newline='\n') as f:
                        f.write(formatted)
                else:
                    sys.stdout.write(formatted)
            else:
                width, height = check_rectangle(source)
                sys.stdout.write(f'✅ 矩形排版：{width} 列 × {height} 行\n')
            return 0
        except PymojiError as e:
            sys.stderr.write(format_error(e, source.split('\n')) + '\n')
            return 1
        except OSError as e:
            sys.stderr.write(f'📂 写入文件失败：{e.strerror or e}\n')
            return 2
        except (RecursionError, MemoryError):
            sys.stderr.write('⛔ 资源超限\n   语法或排版检查时嵌套过深或可用内存不足\n')
            return 1

    max_depth = args.max_depth
    return run_with_big_stack(
        lambda: run_source(source, max_mem_mb=args.max_mem,
                           max_depth=max_depth, seed=args.seed),
        max_depth)


def run_with_big_stack(fn, max_depth):
    """在栈空间更大的线程里运行 fn()，并按栈的大小调高 Python 的递归上限。

    树遍历解释器每调用一层 pymoji 函数，要用掉十几到几十层 Python 调用。
    Python 3.11 起，这些调用不再占用系统栈，64 MB 的栈绰绰有余；更老的版本每层
    大约占 1 KB 系统栈，栈不够深时 Python 会直接崩溃，所以要开大栈，并按栈的大小
    把递归上限算保守一些。（Windows 会把整个栈预先记入内存承诺，所以栈不宜无谓地开大。）
    """
    result = []
    sizes = (64 << 20, 16 << 20) if sys.version_info >= (3, 11) else (512 << 20, 128 << 20, 32 << 20)
    for size in sizes:
        try:
            threading.stack_size(size)
        except (ValueError, RuntimeError, OverflowError):
            continue
        frames = max_depth * 60 + 10_000
        if sys.version_info < (3, 11):
            frames = min(frames, size // 3072)

        def target(frames=frames):
            sys.setrecursionlimit(max(sys.getrecursionlimit(), frames))
            result.append(fn())

        worker = threading.Thread(target=target, daemon=True)
        try:
            worker.start()
        except RuntimeError:                         # 这个系统不给开这么大的栈，换小一点再试
            continue
        try:
            while worker.is_alive():
                worker.join(0.1)
        except KeyboardInterrupt:
            sys.stderr.write('\n⏹️ 已中断\n')
            return 130
        return result[0] if result else 1
    return fn()                                      # 实在开不了新线程，就在当前线程里用默认设置运行


if __name__ == '__main__':
    sys.exit(main())
