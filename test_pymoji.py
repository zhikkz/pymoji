#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pymoji 语义回归、任意排版、边界与命令行验证。只依赖 Python 标准库。"""
import io
import math
import os
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import pymoji


class PymojiTests(unittest.TestCase):
    @staticmethod
    def cli(*args, data=None, env=None):
        script = os.path.join(os.path.dirname(__file__), 'pymoji.py')
        return subprocess.run([sys.executable, script, *args], input=data, env=env, encoding='utf-8',
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)

    def execute(self, source, data='', **options):
        out, err = io.StringIO(), io.StringIO()
        rc = pymoji.run_source(source, out=out, err=err, inp=io.StringIO(data), **options)
        return rc, out.getvalue(), err.getvalue()

    def assert_program(self, source, expected, data='', **options):
        rc, out, err = self.execute(source, data, **options)
        self.assertEqual((rc, out, err), (0, expected, ''))

    def test_value_and_operator_regressions(self):
        cases = [
            ('📢1➕2✖️3', '7\n'),
            ('📢🤜1➕2🤛✖️3', '9\n'),
            ('📢2🚀3🚀2', '512\n'),
            ('📢➖2🚀2,🤜➖2🤛🚀2', '-4 4\n'),
            ('📢6➗3,7➗2,➖7✂️2,➖7🥡3', '2 3.5 -4 2\n'),
            ('📢0<2≤3,0<2>3', '✅ ❌\n'),
            ('📢🚫1=2,🚫✅🤝❌,❌🔀✅', '✅ ❌ ✅\n'),
            ('📢❌🤝🤜1➗0🤛,✅🔀未定义', '❌ ✅\n'),
            ('📢✅=1,❌=0,1=1.0,🕳️=🕳️', '❌ ❌ ✅ ✅\n'),
            ('📢🔤1🔡=1,🎁1,2🎀=🎁1,2🎀', '❌ ✅\n'),
            ('📢🎁1,2🎀<🎁1,3🎀,🔤甲🔡>🔤乙🔡', '✅ ✅\n'),
            ('📢🔤🍓🔡➕3,🔤🍎🔡✖️3,➖2✖️🔤🍎🔡', '🍓3 🍎🍎🍎 \n'),
            ('a⬅️3🔚a⬆️4🔚a⬇️2🔚📢a', '5\n'),
            ('a⬅️🔤甲🔡🔚a⬆️2🔚📢a', '甲2\n'),
            ('📢🎁1🎀➕🎁2🎀,🎁1,2🎀✖️2', '🎁1, 2🎀 🎁1, 2, 1, 2🎀\n'),
            ('a⬅️🎁🎁0🎀✖️2🎀✖️2🔚a📍0📍0⬅️8🔚📢a', '🎁🎁8, 0🎀, 🎁0, 0🎀🎀\n'),
            ('a⬅️🎁1,2🎀🔚a📥3🔚a📍0⬆️5🔚📢👀a,📤a,a📍0,📏a', '3 3 6 2\n'),
            ('a⬅️🎁1,2🎀🔚📢a,📤a', '🎁1, 2🎀 2\n'),
            ('a⬅️🎁🎀🔚a📥a🔚📢a', '🎁🎁…🎀🎀\n'),
            ('📢📏🔤👨‍👩‍👧🇨🇳👍🏽🔡,🔤👨‍👩‍👧🇨🇳👍🏽🔡📍1', '3 🇨🇳\n'),
            ('📢🔟,💯,１２.５,1️⃣2️⃣,١٢', '10 100 12.5 12 12\n'),
            ('📢🔤🔡,🎁🔤甲🛡️⬜乙🔡🎀', ' 🎁🔤甲🛡️⬜乙🔡🎀\n'),
            ('💬1🔚💬2🔚📢🔚📢3', '12\n3\n'),
            ('📢👑🤜3,9,4🤛,🐜🤜🎁3,➖4🎀🤛,🔃🤜🎁3,1,2🎀🤛', '9 -4 🎁1, 2, 3🎀\n'),
            ('a⬅️🎁3,1,2🎀🔚📢🔃🤜a🤛,a', '🎁1, 2, 3🎀 🎁3, 1, 2🎀\n'),
            ('📢👑🤜🔤乙🔡,🔤甲🔡🤛,🐜🤜🎁🎁1🎀,🎁2🎀🎀🤛', '甲 🎁1🎀\n'),
            ('📢👑🤜5,🤛,🎁1,2,🎀', '5 🎁1, 2🎀\n'),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assert_program(source, expected)

    def test_control_flow_and_scope_regressions(self):
        cases = [
            ('🤔❌👉📢1👈🤷🤔✅👉📢2👈🤷👉📢3👈📢4', '2\n4\n'),
            ('a⬅️0🔚🔁a<3👉a⬆️1🔚📢a👈', '1\n2\n3\n'),
            ('🔂i🛫1🛬3👉📢i👈', '1\n2\n3\n'),
            ('🔂i🛫10🛬1👣➖3👉📢i👈', '10\n7\n4\n1\n'),
            ('🔂i🛫0🛬1👣0.25👉📢i👈', '0\n0.25\n0.5\n0.75\n1\n'),
            ('🔂i🛫1🛬5👉🤔i=2👉⏭️👈🤔i=4👉🛑👈📢i👈', '1\n3\n'),
            ('a⬅️🎁1,2🎀🔚🔂i∈a👉📢i🔚a📥9👈📢📏a', '1\n2\n4\n'),
            ('🔂i∈🔤甲👨‍👩‍👧🔡👉📢i👈', '甲\n👨‍👩‍👧\n'),
            ('🏭f🤜a,b🤛👉↩️a➕b👈📢f🤜3,4🤛', '7\n'),
            ('🏭f🤜🤛👉↩️👈📢f🤜🤛', '🕳️\n'),
            ('🏭f🤜🤛👉👈📢f🤜🤛', '🕳️\n'),
            ('🏭f🤜n🤛👉🤔n≤1👉↩️1👈↩️n✖️f🤜n➖1🤛👈📢f🤜6🤛', '720\n'),
            ('🏭外🤜a🤛👉🏭内🤜b🤛👉↩️a➕b👈↩️内👈f⬅️外🤜100🤛🔚📢f🤜5🤛', '105\n'),
            ('a⬅️2🔚🏭f🤜🤛👉a⬅️9🔚↩️a👈📢f🤜🤛,a', '9 2\n'),
            ('a⬅️🎁1🎀🔚🏭f🤜🤛👉a📍0⬅️9👈f🤜🤛🔚📢a', '🎁9🎀\n'),
            ('🏭f🤜a🤛👉↩️a✖️2👈🏭g🤜h,x🤛👉↩️h🤜x🤛👈📢g🤜f,7🤛', '14\n'),
            ('📢👑🤜🔚1,🔚2🔚🤛🔚📢🎁🔚3,🔚4🔚🎀', '2\n🎁3, 4🎀\n'),
            ('🤔✅🔚👉📢1👈🔚🤷🔚👉📢2👈', '1\n'),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assert_program(source, expected)

    def test_range_overflow_preserves_language_error_and_call_trace(self):
        for start, step in (('2🚀2000', '0.5'), ('0.5', '2🚀2000')):
            source = ('🏭f🤜🤛👉\n🔂i🛫' + start + '🛬2🚀2000👣' + step +
                      '👉👈\n👈\nf🤜🤛')
            with self.subTest(start=start, step=step):
                rc, out, err = self.execute(source)
                self.assertEqual((rc, out), (1, ''))
                self.assertIn('运行错误（第 2 行）', err)
                self.assertIn('范围循环的数字超出了能表示的范围', err)
                self.assertIn('第 4 行调用 🏭f', err)
                self.assertNotIn('解释器内部错误', err)
        # 仍允许大整数范围和普通的小数范围。
        self.assert_program('n⬅️2🚀2000🔚🔂i🛫n🛬n➕2👉📢i➖n👈', '0\n1\n2\n')
        self.assert_program('🔂i🛫0.5🛬1.5👣0.5👉📢i👈', '0.5\n1\n1.5\n')

    def test_cyclic_comparisons_find_sort_and_extrema(self):
        setup = 'a⬅️🎁🎀🔚a📥a🔚b⬅️🎁🎀🔚b📥b🔚'
        self.assert_program(setup + '📢a=b,a≠b,a<b,a>b,a≤b,a≥b', '✅ ❌ ❌ ❌ ✅ ✅\n')
        self.assert_program(setup + '📢🔎🤜🎁a🎀,b🤛,📏🔃🤜🎁a,b🎀🤛', '0 2\n')
        self.assert_program(setup + '📢👑🤜a,b🤛=a,🐜🤜a,b🤛=b', '✅ ✅\n')
        # 循环之外的元素仍须比较，长度也不能忽略。
        self.assert_program(setup + 'a📥1🔚b📥2🔚📢a=b,a<b,b>a,🔎🤜🎁a🎀,b🤛',
                            '❌ ✅ ✅ -1\n')
        self.assert_program(setup + 'b📥0🔚📢a=b,a<b,b>a', '❌ ✅ ✅\n')
        # 相互引用，以及共享子列表在不同位置出现。
        self.assert_program('a⬅️🎁🎀🔚x⬅️🎁a🎀🔚a📥x🔚b⬅️🎁🎀🔚y⬅️🎁b🎀🔚b📥y🔚📢a=b,a≤b',
                            '✅ ✅\n')
        self.assert_program('a⬅️🎁1🎀🔚b⬅️🎁1🎀🔚📢🎁a,a🎀=🎁b,🎁2🎀🎀,🎁a,a🎀=🎁b,b🎀',
                            '❌ ✅\n')

    def test_deep_comparisons_use_bounded_python_stack(self):
        interp = pymoji.Interpreter(max_mem_mb=0)
        node = pymoji.Const(7, None)
        a, b, c = 1, 1, 2
        for _ in range(5000):
            a, b, c = [a], [b], [c]
        self.assertTrue(interp.equal(a, b, node))
        self.assertFalse(interp.equal(a, c, node))
        self.assertEqual(interp.order(a, b, node), 0)
        self.assertEqual(interp.order(a, c, node), -1)

    def test_comparisons_check_memory_and_keep_location(self):
        a, b = [0] * (pymoji.TICK * 2), [0] * (pymoji.TICK * 2)
        node = pymoji.Const(7, None)
        operations = [lambda i: i.equal(a, b, node), lambda i: i.order(a, b, node),
                      lambda i: pymoji.builtin_find(i, [[a], b], node),
                      lambda i: pymoji.builtin_sort(i, [[a, b]], node)]
        for operation in operations:
            interp = pymoji.Interpreter(max_mem_mb=0)
            interp.max_mem = 1048576
            interp.mem_base = 0
            interp.read_mem = lambda: 2 * 1048576
            with self.assertRaises(pymoji.PymojiError) as raised:
                operation(interp)
            self.assertEqual((raised.exception.kind, raised.exception.line), ('资源超限', 7))
        source = 'a⬅️🎁0🎀✖️3000🔚b⬅️🎁0🎀✖️3000🔚\n🏭f🤜🤛👉↩️a=b👈\n📢f🤜🤛'
        # 直接验证比较产生的资源错误经函数调用保留原行号和调用路径。
        program = pymoji.Parser(pymoji.tokenize(source)).parse_program()
        interp = pymoji.Interpreter(max_mem_mb=0)
        interp.run(program[:2])
        interp.max_mem, interp.mem_base = 1048576, 0
        interp.read_mem = lambda: 2 * 1048576
        with self.assertRaises(pymoji.PymojiError) as raised:
            interp.run(program[2:])
        self.assertEqual(raised.exception.line, 2)
        self.assertEqual(raised.exception.trace, [('f', 3)])

    def test_return_propagates_through_blocks_and_loops(self):
        for loop in ('🔁✅', '🔂i🛫1🛬3', '🔂i∈🎁1,2🎀', '🔂i∈字典🤜🎁🎁1,2🎀🎀🤛'):
            with self.subTest(loop=loop):
                self.assert_program('🏭f🤜🤛👉' + loop + '👉🤔✅👉↩️42👈📢0👈📢0👈📢f🤜🤛', '42\n')
        self.assert_program('🏭f🤜🤛👉🔂i🛫1🛬3👉🔁✅👉↩️👈👈📢0👈📢f🤜🤛', '🕳️\n')
        self.assert_program('🏭f🤜x🤛👉↩️x👈🏭g🤜🤛👉f🤜1🤛🔚📢2🔚↩️f🤜3🤛👈📢g🤜🤛', '2\n3\n')

    def test_arithmetic_dispatch_preserves_types_and_limits(self):
        self.assert_program('a⬅️1.0🔚a⬆️1🔚📢类型🤜a🤛,类型🤜1➕2🤛,类型🤜1.0➕2🤛',
                            '小数 整数 小数\n')
        for source in ('📢2🚀9999➕2🚀9999', 'a⬅️2🚀9999🔚a⬆️a', '📢2🚀9999✖️2'):
            rc, _, err = self.execute(source)
            self.assertEqual(rc, 1)
            self.assertIn('整数太大', err)
        for source in ('📢✅➕1', 'a⬅️✅🔚a⬆️1'):
            rc, _, err = self.execute(source)
            self.assertEqual(rc, 1)
            self.assertIn('➕ 不能用在真假值和数字之间', err)

    def test_multilingual_names_and_normalization(self):
        cases = [
            ('汉字_2⬅️1🔚abc3⬅️2🔚かなカナ⬅️3🔚_值⬅️4🔚📢汉字_2➕abc3➕かなカナ➕_值', '10\n'),
            ('变量🍎2⬅️9🔚📢变量🍎２', '9\n'),
            ('👍🏽⬅️6🔚📢👍🏿', '6\n'),
            ('📦2️⃣⬅️7🔚📢📦２', '7\n'),
            ('🙋‍♂️⬅️1🔚🙋‍♀️⬅️2🔚📢🙋‍♂️,🙋‍♀️', '1 2\n'),
            ('🤔❌👉📢1👈🤷🏽‍♀️👉🏔️⬅️2🔚📢🏔👈', '2\n'),
            ('é⬅️8🔚📢e\u0301', '8\n'),
            ('#️⃣⬅️9🔚*️⃣⬅️10🔚📢#️⃣,*️⃣', '9 10\n'),
            ('名称١⬅️4🔚📢名称1', '4\n'),
            ('🏭计算🤜入力_2,値🍎🤛👉↩️入力_2➕値🍎👈📢计算🤜3,4🤛', '7\n'),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assert_program(source, expected)

    def test_whitespace_is_globally_ignored(self):
        self.assert_program('数 字\n⬅️1 \n 2🔚📢数\t字', '12\n')
        self.assert_program('📢🔤甲 \n\t乙\u3000 丙🔡', '甲乙丙\n')
        self.assert_program('💭注释跨\n物理行📢999🔚📢2', '2\n')
        self.assert_program('💭直到文件结尾\n📢999', '')
        self.assert_program('\ufeffa⬅️1\r\n🔚\r\n📢a', '1\n')

    def test_string_escapes(self):
        self.assert_program('📢🔤甲🛡️⬜乙🛡️🔚丙🛡️↔️丁🛡️🔤🛡️🔡🛡️🛡️🔡',
                            '甲 乙\n丙\t丁🔤🔡🛡️\n')
        self.assert_program('📢🔤💭👉👈🤜🤛🔚🔡', '💭👉👈🤜🤛🔚\n')

    def test_arbitrary_codepoint_relayout_invariance(self):
        source = ('💭测试注释🔚变量🍎2️⃣⬅️１２.５🔚'
                  '🏭かな🤜输入🤛👉🤔输入>0👉↩️🔤你好🛡️⬜👨‍👩‍👧🛡️🔚🔡➕输入👈↩️🔤空🔡👈'
                  '📢かな🤜变量🍎２🤛🔚📢🎁🔤甲🛡️⬜乙🔡,2🎀')
        expected = self.execute(source)
        self.assertEqual(expected[0], 0)
        signature = [(t.type, t.value) for t in pymoji.tokenize(source)]
        rng = random.Random(20261022)
        for trial in range(100):
            altered = ''.join(c + rng.choice(('', ' ', '\t', '\n', '\r\n', '\u3000', ' \n\t')) for c in source)
            with self.subTest(trial=trial):
                self.assertEqual(self.execute(altered), expected)
                self.assertEqual([(t.type, t.value) for t in pymoji.tokenize(altered)], signature)

    def test_rectangle_format_and_check(self):
        source = '💭注释🔚a⬅️🎁1,2,🔤甲🛡️⬜乙🔡🎀🔚📢a,👑🤜1,3🤛'
        expected = self.execute(source)
        signature = [(t.type, t.value) for t in pymoji.tokenize(source)]
        for width in (2, 3, 7, 13, 48, 80):
            with self.subTest(width=width):
                formatted = pymoji.format_rectangle(source, width)
                w, h = pymoji.check_rectangle(formatted)
                self.assertEqual(w, width)
                self.assertGreater(h, 0)
                self.assertEqual(self.execute(formatted), expected)
                self.assertEqual([(t.type, t.value) for t in pymoji.tokenize(formatted)], signature)
                self.assertEqual(pymoji.format_rectangle(formatted, width), formatted)
        self.assertEqual(pymoji.check_rectangle(pymoji.format_rectangle('', 6)), (6, 1))
        with self.assertRaises(pymoji.PymojiError):
            pymoji.check_rectangle('📢1\n ')
        with self.assertRaises(pymoji.PymojiError):
            pymoji.check_rectangle('📢1\t')
        with self.assertRaises(ValueError):
            pymoji.format_rectangle(source, 1)

    def test_ascii_delimiters_allowed_only_in_strings(self):
        for ch in '()\"\'':
            self.assert_program('📢🔤' + ch + '🔡', ch + '\n')
            for source in ('💭' + ch, '💭🔤' + ch + '🔡', '📢🔤甲🔡' + ch, ch):
                with self.subTest(source=source):
                    rc, out, err = self.execute(source)
                    self.assertEqual(rc, 1)
                    self.assertEqual(out, '')
                    self.assertIn('字符不合规', err)
        for source in ('📢（1）', '📢“甲”'):
            self.assertEqual(self.execute(source)[0], 1)

    def test_unrestricted_string_data_and_unicode_escapes(self):
        data = '''()"'[]{};:@#$&!?\\中文“引号”（括号）\x00\x1b\u200b\u202e'''
        self.assert_program('📢🔤' + data + '🔡', data + '\n')
        self.assert_program('📢🔤🛡️u0020🛡️u000D🛡️u00A0🛡️U0001F600🔡', ' \r\u00a0😀\n')
        self.assert_program('📢🔤🛡️uD7FF🛡️uE000🛡️U0010FFFF🔡', '\ud7ff\ue000\U0010ffff\n')
        self.assert_program('📢🔤🛡️🔡()🔡', '🔡()\n')
        for source, fragment in [
            ('📢🔤🛡️u12🔡', '4 位'), ('📢🔤🛡️uXYZW🔡', '4 位'),
            ('📢🔤🛡️U00110000🔡', '有效的 Unicode'), ('📢🔤🛡️uD800🔡', '代理项'),
            ('📢🔤🛡️U0000DFFF🔡', '代理项'),
        ]:
            with self.subTest(source=source):
                self.assertIn(fragment, self.execute(source)[2])
        source = 'a⬅️🔤()\"\'🛡️u00A0🛡️U0001F600🛡️🔡🔡🔚📢a'
        signature = [(t.type, t.value) for t in pymoji.tokenize(source)]
        for altered in (' \n'.join(source), pymoji.format_rectangle(source, 7)):
            self.assertEqual([(t.type, t.value) for t in pymoji.tokenize(altered)], signature)
            self.assertEqual(self.execute(altered), self.execute(source))

    def test_type_conversions(self):
        cases = [
            ('📢🔢🤜🔤123🔡🤛➕1,整数🤜🔤➖１２🔡🤛,🔢🤜🔤1️⃣2️⃣🔡🤛', '124 -12 12\n'),
            ('📢🔢🤜➖3.9🤛,🔢🤜✅🤛,🔢🤜❌🤛,🔢🤜🔤🛡️⬜+42🛡️⬜🔡🤛', '-3 1 0 42\n'),
            ('📢🔢🤜🔤ff🔡,16🤛,🔢🤜🔤0b101🔡,0🤛,🔢🤜🔤1_000🔡🤛', '255 5 1000\n'),
            ('📢🔣🤜🔤➖１２．５🔡🤛,小数🤜🔤1e3🔡🤛,🔣🤜✅🤛', '-12.5 1000 1\n'),
            ('📢🧵🤜🎁1,✅🎀🤛,文字🤜🕳️🤛,文字🤜🔤原样🔡🤛', '🎁1, ✅🎀 🕳️ 原样\n'),
            ('📢🔘🤜0🤛,真假🤜🔤0🔡🤛,真假🤜🎁🎀🤛,真假🤜🕳️🤛', '❌ ✅ ❌ ❌\n'),
            ('📢🏷️🤜1🤛,类型🤜1.0🤛,类型🤜✅🤛,类型🤜🕳️🤛,类型🤜🎁🎀🤛,类型🤜🔢🤛',
             '整数 小数 真假 空值 列表 函数\n'),
            ('🏭f🤜🤛👉👈📢类型🤜f🤛,类型🤜🔤🔡🤛', '函数 文字\n'),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assert_program(source, expected)

    def test_numeric_text_variants_and_scientific_roundtrip(self):
        self.assert_program('📢🔢🤜🔤➖️5🔡🤛,🔢🤜🔤➕︎１２🔡🤛,🔣🤜🔤➖️1×10^➖️3🔡🤛', '-5 12 -0.001\n')
        self.assert_program('📢🔣🤜🧵🤜🔣🤜🔤1e16🔡🤛🤛🤛=🔣🤜🔤1e16🔡🤛', '✅\n')
        rng = random.Random(16)
        interp, node = pymoji.Interpreter(max_mem_mb=0), pymoji.Const(1, None)
        values = [1e16, -1e16, 1e-16, 5e-324, sys.float_info.max, 0.0]
        values += [math.ldexp(rng.random() - 0.5, rng.randrange(-1073, 1024)) for _ in range(300)]
        for value in values:
            with self.subTest(value=value):
                text = pymoji.builtin_text(interp, [value], node)
                self.assertEqual(pymoji.builtin_float(interp, [text], node), value)
        for value in ('1×10^', '1×10^2e3', 'nan', 'inf'):
            self.assertEqual(self.execute('📢🔣🤜🔤' + value + '🔡🤛')[0], 1)

    def test_rounding_and_fixed_decimal_format(self):
        cases = [
            ('📢🎯🤜0.1➕0.2,2🤛,🖋️🤜0.1➕0.2,2🤛', '0.3 0.30\n'),
            ('📢四舍五入🤜2.5🤛,四舍五入🤜➖2.5🤛,四舍五入🤜2.675,2🤛', '3 -3 2.68\n'),
            ('📢四舍五入🤜125,➖1🤛,四舍五入🤜➖125,➖1🤛', '130 -130\n'),
            ('📢小数格式🤜1.2🤛,小数格式🤜➖0.001,2🤛,小数格式🤜9.999,2🤛', '1.20 0.00 10.00\n'),
            ('📢小数格式🤜12,0🤛,类型🤜小数格式🤜1🤛🤛,类型🤜四舍五入🤜1.2🤛🤛', '12 文字 整数\n'),
            ('📢四舍五入🤜2🚀200,2🤛=2🚀200,📏小数格式🤜1,3000🤛', '✅ 3002\n'),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assert_program(source, expected)
        for source in ('📢四舍五入🤜✅🤛', '📢小数格式🤜🔤1🔡🤛', '📢四舍五入🤜1,0.5🤛',
                       '📢小数格式🤜1,➖1🤛', '📢四舍五入🤜1,3001🤛', '📢四舍五入🤜1,➖3001🤛',
                       '📢小数格式🤜1,2🚀200🤛', '📢四舍五入🤜🔣🤜🔤1.79e308🔡🤛,➖308🤛'):
            rc, _, err = self.execute(source)
            with self.subTest(source=source):
                self.assertEqual(rc, 1)
                self.assertNotIn('解释器内部错误', err)
        self.assertIn('内存上限', self.execute('📢小数格式🤜1,3000🤛', max_mem_mb=0.001)[2])

    def test_dictionary_operations_and_key_semantics(self):
        cases = [
            ('d⬅️🗃️🤜🤛🔚📢📏d,真假🤜d🤛,类型🤜d🤛,取值🤜d,🔤x🔡🤛', '0 ❌ 字典 🕳️\n'),
            ('d⬅️字典🤜🎁🎁🔤a🔡,1🎀,🎁🔤b🔡,2🎀🎀🤛🔚d📍🔤a🔡⬆️3🔚d📍🔤b🔡⬇️1🔚'
             'd📍🔤c🔡⬅️5🔚📢d📍🔤a🔡,键🤜d🤛,值🤜d🤛', '4 🎁🔤a🔡, 🔤b🔡, 🔤c🔡🎀 🎁4, 1, 5🎀\n'),
            ('d⬅️字典🤜🎁🎁1,🔤数🔡🎀,🎁✅,🔤真🔡🎀,🎁🕳️,0🎀,🎁🔤1🔡,9🎀🎀🤛🔚'
             'd📍1.0⬅️2🔚📢📏d,d📍1,d📍✅,d📍🕳️,d📍🔤1🔡', '4 2 真 0 9\n'),
            ('d⬅️字典🤜🎁🎁1,2🎀,🎁1.0,3🎀🎀🤛🔚📢键🤜d🤛,键值对🤜d🤛', '🎁1🎀 🎁🎁1, 3🎀🎀\n'),
            ('d⬅️字典🤜🤛🔚📢🔐🤜d,1🤛,🫴🤜d,1,0🤛🔚d📍1⬅️🕳️🔚📢含键🤜d,1🤛,取值🤜d,1,9🤛,🗑️🤜d,1🤛,📏d',
             '❌ 0\n✅ 🕳️ 🕳️ 0\n'),
            ('d⬅️字典🤜🎁🎁1,🎁0🎀🎀🎀🤛🔚c⬅️复制🤜d🤛🔚c📍1📍0⬅️8🔚c📍2⬅️9🔚📢d📍1,📏d,📏c',
             '🎁8🎀 1 2\n'),
            ('d⬅️字典🤜🎁🎁1,0🎀,🎁2,0🎀🎀🤛🔚🔂k∈d👉📢k🔚d📍3⬅️0👈📢📏d', '1\n2\n3\n'),
            ('d⬅️字典🤜🎁🎁🔤a🔡,1🎀🎀🤛🔚📢d,文字🤜d🤛',
             '🗃️🤜🎁🎁🔤a🔡, 1🎀🎀🤛 🗃️🤜🎁🎁🔤a🔡, 1🎀🎀🤛\n'),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assert_program(source, expected)

    def test_dictionary_cycles_equality_and_copying(self):
        setup = 'a⬅️字典🤜🤛🔚a📍1⬅️a🔚b⬅️字典🤜🤛🔚b📍1⬅️b🔚'
        self.assert_program(setup + '📢a=b,a,查找🤜🎁a🎀,b🤛', '✅ 🗃️🤜🎁🎁1, 🗃️…🎀🎀🤛 0\n')
        self.assert_program(setup + 'a📍2⬅️1🔚b📍2⬅️2🔚📢a=b', '❌\n')
        self.assert_program('a⬅️字典🤜🎁🎁1,2🎀,🎁3,4🎀🎀🤛🔚b⬅️字典🤜🎁🎁3,4🎀,🎁1,2🎀🎀🤛🔚📢a=b', '✅\n')
        self.assert_program('a⬅️字典🤜🤛🔚x⬅️🎁a🎀🔚a📍0⬅️x🔚b⬅️字典🤜🤛🔚y⬅️🎁b🎀🔚b📍0⬅️y🔚📢a=b', '✅\n')
        self.assert_program('d⬅️字典🤜🎁🎁1,🎁0🎀🎀🎀🤛🔚a⬅️🎁d🎀✖️2🔚a📍0📍1📍0⬅️8🔚📢a📍1📍1,d📍1',
                            '🎁0🎀 🎁0🎀\n')
        self.assert_program('a⬅️🎁字典🤜🤛🎀✖️2🔚a📍0📍1⬅️8🔚📢📏a📍1', '0\n')
        self.assert_program(setup + 'c⬅️🎁a🎀✖️2🔚c📍0📍2⬅️8🔚📢c📍0📍1=c📍0,📏c📍1', '✅ 1\n')

    def test_dictionary_errors_and_resource_limits(self):
        cases = [('📢字典🤜1🤛', '需要列表'), ('📢字典🤜🎁1🎀🤛', '恰有两项'),
                 ('📢字典🤜🎁🎁🎁🎀,1🎀🎀🤛', '键必须'), ('📢键🤜1🤛', '需要字典'),
                 ('📢字典🤜🤛📍1', '没有键'), ('d⬅️字典🤜🤛🔚d📍1⬆️1', '没有键'),
                 ('📢删除🤜字典🤜🤛,1🤛', '没有键'), ('📢取值🤜字典🤜🤛,🎁🎀🤛', '键必须'),
                 ('📢字典🤜🤛<字典🤜🤛', '不能比较大小')]
        for source, fragment in cases:
            with self.subTest(source=source):
                rc, _, err = self.execute(source)
                self.assertEqual(rc, 1)
                self.assertIn(fragment, err)
                self.assertIn('第 1 行', err)
                self.assertNotIn('解释器内部错误', err)
        interp, node = pymoji.Interpreter(max_mem_mb=0), pymoji.Const(1, None)
        interp.max_mem = 1000
        with self.assertRaises(pymoji.PymojiError):
            pymoji.builtin_dict(interp, [[[i, i] for i in range(100)]], node)

    def test_text_builtins(self):
        cases = [
            ('📢🧩🤜🔤🛡️⬜甲🛡️↔️乙🛡️🔚🔡🤛', '🎁🔤甲🔡, 🔤乙🔡🎀\n'),
            ('📢分割🤜🔤a,,b,🔡,🔤,🔡🤛', '🎁🔤a🔡, 🔤🔡, 🔤b🔡, 🔤🔡🎀\n'),
            ('📢🧩🤜🔤🔡🤛,🧩🤜🔤🔡,🔤,🔡🤛,🧩🤜🔤🔡,🔤🔡🤛', '🎁🎀 🎁🔤🔡🎀 🎁🎀\n'),
            ('📢🪢🤜🎁1,✅,🕳️🎀,🔤,🔡🤛,连接🤜🎁🔤a🔡,🔤b🔡🎀🤛', '1,✅,🕳️ ab\n'),
            ('📢🪢🤜🎁🎀,🔤,🔡🤛', '\n'),
            ('📢🧼🤜🔤🛡️u00A0甲🛡️⬜乙🛡️u000D🔡🤛', '甲 乙\n'),
            ('📢🪄🤜🔤aaaa🔡,🔤aa🔡,🔤b🔡🤛,替换🤜🔤aaaa🔡,🔤a🔡,🔤b🔡,2🤛', 'bb bbaa\n'),
            ('📢替换🤜🔤甲🔡,🔤甲🔡,🔤🔡,0🤛,替换🤜🔤甲🔡,🔤甲🔡,🔤🔡🤛', '甲 \n'),
            ('📢🔎🤜🔤甲乙甲🔡,🔤甲🔡,1🤛,查找🤜🔤甲🔡,🔤乙🔡🤛', '2 -1\n'),
            ('📢查找🤜🔤abc🔡,🔤🔡,3🤛,查找🤜🔤abc🔡,🔤🔡,4🤛', '3 -1\n'),
            ('📢查找🤜🎁✅,1,2🎀,1🤛,查找🤜🎁1,2,1🎀,1,➖1🤛', '1 2\n'),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assert_program(source, expected)

    def test_grapheme_safe_text_operations(self):
        family, flag, toned = '👨‍👩‍👧', '🇨🇳', '👍🏽'
        text = family + flag + toned + 'e\u0301'
        self.assert_program('📢🪢🤜🧩🤜🔤' + text + '🔡,🔤🔡🤛🤛', text + '\n')
        self.assert_program('📢🪞🤜🔤' + text + '🔡🤛', 'e\u0301' + toned + flag + family + '\n')
        self.assert_program('📢🍰🤜🔤' + text + '🔡,1,3🤛', flag + toned + '\n')
        self.assert_program('📢查找🤜🔤' + text + '🔡,🔤' + toned + '🔡🤛', '2\n')
        for fragment in ('👨', '🇨', '👍', 'e', '\u0301'):
            with self.subTest(fragment=fragment):
                literal = '🛡️u0301' if fragment == '\u0301' else fragment
                self.assert_program('📢查找🤜🔤' + text + '🔡,🔤' + literal + '🔡🤛', '-1\n')
                self.assert_program('📢替换🤜🔤' + text + '🔡,🔤' + literal + '🔡,🔤x🔡🤛', text + '\n')
                self.assert_program('📢📏分割🤜🔤' + text + '🔡,🔤' + literal + '🔡🤛', '1\n')

    def test_sequence_numeric_and_higher_order_builtins(self):
        cases = [
            ('📢🌱🤜4🤛,范围🤜3,1,➖1🤛,范围🤜0🤛,范围🤜1,5,2🤛',
             '🎁1, 2, 3, 4🎀 🎁3, 2, 1🎀 🎁🎀 🎁1, 3, 5🎀\n'),
            ('📢范围🤜4,2🤛,范围🤜1,3,➖1🤛,范围🤜2,2,➖2🤛', '🎁🎀 🎁🎀 🎁2🎀\n'),
            ('📢🍰🤜🌱🤜5🤛,1,4🤛,切片🤜🌱🤜5🤛,🕳️,🕳️,➖2🤛', '🎁2, 3, 4🎀 🎁5, 3, 1🎀\n'),
            ('📢切片🤜🌱🤜4🤛,➖2🤛,切片🤜🌱🤜4🤛,➖99,99🤛', '🎁3, 4🎀 🎁1, 2, 3, 4🎀\n'),
            ('a⬅️🎁🎁1🎀,2🎀🔚b⬅️📋🤜a🤛🔚b📥3🔚b📍0📍0⬅️8🔚📢a,b',
             '🎁🎁8🎀, 2🎀 🎁🎁8🎀, 2, 3🎀\n'),
            ('a⬅️🌱🤜3🤛🔚📢🪞🤜a🤛,a,复制🤜🔤甲🔡🤛', '🎁3, 2, 1🎀 🎁1, 2, 3🎀 甲\n'),
            ('📢🧮🤜🌱🤜10🤛🤛,求和🤜🎁🎀,2.5🤛,📐🤜➖3.5🤛', '55 2.5 3.5\n'),
            ('🏭平方🤜n🤛👉↩️n🚀2👈📢🗺️🤜平方,🌱🤜4🤛🤛', '🎁1, 4, 9, 16🎀\n'),
            ('🏭偶数🤜n🤛👉↩️n🥡2=0👈📢🧹🤜偶数,🌱🤜6🤛🤛', '🎁2, 4, 6🎀\n'),
            ('📢映射🤜🔢,🎁🔤1🔡,🔤2🔡🎀🤛,筛选🤜🔘,🎁0,1,🕳️,🔤甲🔡🎀🤛',
             '🎁1, 2🎀 🎁1, 🔤甲🔡🎀\n'),
            ('a⬅️🌱🤜2🤛🔚🏭f🤜n🤛👉a📥9🔚↩️n👈📢映射🤜f,a🤛,a', '🎁1, 2🎀 🎁1, 2, 9, 9🎀\n'),
            ('a⬅️🎁🎀🔚a📥a🔚b⬅️复制🤜a🤛🔚📢查找🤜b,a🤛,📏b', '0 1\n'),
            ('整数⬅️7🔚📢整数,🔢🤜🔤8🔡🤛', '7 8\n'),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assert_program(source, expected)

    def test_builtin_errors_and_resource_limits(self):
        cases = [
            ('📢🔢🤜🔤abc🔡🤛', '无法转成整数'), ('📢🔢🤜🔤1.2🔡🤛', '无法转成整数'),
            ('📢🔢🤜🕳️🤛', '不能把'), ('📢🔢🤜1,16🤛', '必须是文字'),
            ('📢🔢🤜🔤1🔡,1🤛', '进制必须'), ('📢🔢🤜🔤1🔡,✅🤛', '要是整数'),
            ('📢🔣🤜🎁🎀🤛', '不能把'), ('📢🔣🤜🔤abc🔡🤛', '无法转成小数'),
            ('📢🔣🤜🔤NaN🔡🤛', '数字超出'), ('📢🔣🤜🔤1e999🔡🤛', '数字超出'),
            ('📢🔣🤜2🚀5000🤛', '无法转成小数'),
            ('📢分割🤜1🤛', '需要文字'), ('📢分割🤜🔤甲🔡,1🤛', '需要文字'),
            ('📢连接🤜🔤甲🔡🤛', '需要列表'), ('📢去空白🤜1🤛', '需要文字'),
            ('📢替换🤜🔤甲🔡,🔤🔡,🔤乙🔡🤛', '不能为空'),
            ('📢替换🤜🔤甲🔡,🔤甲🔡,🔤乙🔡,➖1🤛', '不能为负数'),
            ('📢查找🤜🔤甲🔡,1🤛', '需要文字'), ('📢查找🤜🎁🎀,1,0.5🤛', '要是整数'),
            ('📢切片🤜1🤛', '需要列表或文字'), ('📢切片🤜🎁🎀,0,1,0🤛', '不能是 0'),
            ('📢范围🤜1,3,0🤛', '不能是 0'), ('📢范围🤜1.2🤛', '要是整数'),
            ('📢求和🤜🎁1,✅🎀🤛', '要是数字'), ('📢求和🤜🎁🎀,🔤甲🔡🤛', '要是数字'),
            ('📢绝对值🤜✅🤛', '要是数字'), ('📢映射🤜1,🎁🎀🤛', '必须是函数'),
            ('📢筛选🤜🔘,🔤甲🔡🤛', '需要列表'), ('📢整数🤜🤛', '需要 1 或 2 个参数'),
            ('📢映射🤜🎲,🎁🎁🎀🎀🤛', '要是整数'),
        ]
        for source, fragment in cases:
            with self.subTest(source=source):
                rc, _, err = self.execute(source)
                self.assertEqual(rc, 1)
                self.assertIn(fragment, err)
                self.assertNotIn('解释器内部错误', err)
        for source in ('📢范围🤜1000000000🤛', '📢替换🤜🔤a🔡✖️1000,🔤a🔡,🔤b🔡✖️1000🤛'):
            self.assertIn('内存上限', self.execute(source, max_mem_mb=1)[2])
        self.assertIn('资源超限', self.execute('📢范围🤜2🚀200🤛', max_mem_mb=0)[2])
        self.assertIn('数字文字太长', self.execute('📢整数🤜🔤1🔡✖️3001🤛')[2])
        self.assertIn('整数太大', self.execute('📢整数🤜🔤f🔡✖️3000,16🤛')[2])
        self.assertIn('整数太大', self.execute('📢求和🤜🎁2🚀9999,2🚀9999🎀🤛')[2])
        rc, _, err = self.execute('🏭f🤜n🤛👉↩️映射🤜f,🎁n🎀🤛👈📢f🤜1🤛', max_depth=8)
        self.assertEqual(rc, 1)
        self.assertIn('超过了 8 层', err)

    def test_builtin_names_and_aliases_are_callable(self):
        interp = pymoji.Interpreter(max_mem_mb=0)
        for emoji, alias, fn, arities in pymoji._BUILTIN_SPECS:
            for name in (emoji, alias):
                with self.subTest(name=name):
                    tokens = pymoji.tokenize(name)
                    self.assertEqual(tokens[0].type, 'NAME')
                    self.assertEqual(len(tokens), 2)
                    self.assertIs(interp.globals.vars[tokens[0].value].fn, fn)

    def test_slice_range_and_text_against_python_reference(self):
        interp = pymoji.Interpreter(max_mem_mb=0)
        node = pymoji.Const(1, None)
        rng = random.Random(20261026)
        for trial in range(200):
            seq = list(range(rng.randrange(20)))
            start, stop = (rng.choice([None, rng.randrange(-30, 30)]) for _ in range(2))
            step = rng.choice([None, -4, -2, -1, 1, 2, 4])
            lo, hi = (rng.randrange(-20, 20) for _ in range(2))
            stride = rng.choice([-4, -1, 1, 3])
            text = ''.join(rng.choice('ab ()\"\'') for _ in range(rng.randrange(30)))
            old = rng.choice(['a', 'b', 'ab', ' '])
            new = rng.choice(['', 'x', 'yz'])
            count = rng.randrange(5)
            with self.subTest(trial=trial):
                self.assertEqual(interp.call(interp.globals.vars['切片'], [seq, start, stop, step], node),
                                 seq[slice(start, stop, step)])
                expected = list(range(lo, hi + (1 if stride > 0 else -1), stride))
                self.assertEqual(interp.call(interp.globals.vars['范围'], [lo, hi, stride], node), expected)
                self.assertEqual(interp.call(interp.globals.vars['分割'], [text, old], node), text.split(old))
                self.assertEqual(interp.call(interp.globals.vars['替换'], [text, old, new, count], node),
                                 text.replace(old, new, count))
                self.assertEqual(interp.call(interp.globals.vars['查找'], [text, old, lo], node),
                                 text.find(old, lo))

    def test_syntax_and_runtime_error_regressions(self):
        cases = [
            ('1abc⬅️2', '名字不能以数字开头'),
            ('１猫⬅️2', '名字不能以数字开头'),
            ('١变量⬅️2', '名字不能以数字开头'),
            ('📢1📢2', '🔚'),
            ('📢1🔚a=2', '想赋值请用'),
            ('🛑', '只能用在循环'),
            ('⏭️', '只能用在循环'),
            ('↩️1', '只能用在'),
            ('👈', '多了一个'),
            ('🤔✅👉📢1', '没有等到配对'),
            ('📢🤜1', '🤛'),
            ('📢🎁1', '🎀'),
            ('📢🔤甲', '🔡'),
            ('📢🔤甲🛡️🍎🔡', '🛡️ 后面需要'),
            ('📢🔤甲🔤乙🔡', '🛡️🔤'),
            ('📢🔡', '只能用在'),
            ('📢\x00', '控制字符'),
            ('📢\u200b1', '控制字符'),
            ('🏭f🤜a,a🤛👉👈', '重复'),
            ('🏭f🤜é,e\u0301🤛👉👈', '重复'),
            ('🔂i🛫1🛬3👉🏭f🤜🤛👉🛑👈👈', '只能用在循环'),
            ('📢1➗0', '不能除以 0'),
            ('📢0🚀➖1', '0 不能做负数次方'),
            ('📢🤜➖1🤛🚀0.5', '负数不能开分数次方'),
            ('📢🎁1🎀📍1', '超出范围'),
            ('📢🎁1🎀📍➖1', '这里需要一个值'),
            ('📢🎁1🎀📍🤜➖1🤛', '超出范围'),
            ('📢📤🎁🎀', '空列表'),
            ('📢📏1', '只能量列表、文字或字典'),
            ('a⬅️🔤甲🔡🔚a📍0⬅️1', '不能单独修改'),
            ('a⬅️1🔚a📥2', '只能往列表'),
            ('📢1🤜2🤛', '不是函数'),
            ('📢🎲🤜1,2,3🤛', '需要 1 或 2 个参数'),
            ('📢👑🤜🎁🎀🤛', '至少需要一个值'),
            ('📢🔃🤜1🤛', '只能给列表排序'),
            ('🔂i🛫1🛬3👣0👉👈', '步长不能是 0'),
            ('a⬅️2🔚🏭f🤜🤛👉📢a🔚a⬅️1👈f🤜🤛', '局部变量'),
            ('📢2🚀10001', '整数太大'),
        ]
        for source, fragment in cases:
            with self.subTest(source=source):
                rc, _, err = self.execute(source)
                self.assertEqual(rc, 1)
                self.assertIn(fragment, err)
                self.assertNotIn('解释器内部错误', err)
        self.assertEqual(self.execute('📢1🔚a=2')[1], '')  # 整体语法检查先于任何执行

    def test_physical_locations_and_call_trace(self):
        rc, _, err = self.execute('🏭f🤜x🤛👉\n↩️x➗0\n👈\n📢f🤜1🤛')
        self.assertEqual(rc, 1)
        self.assertIn('第 2 行', err)
        self.assertIn('第 4 行调用 🏭f', err)
        tokens = pymoji.tokenize('变 \n 量⬅️1🔚\n📢变量')
        self.assertEqual((tokens[0].line, tokens[0].col), (1, 1))
        self.assertEqual((tokens[-3].line, tokens[-3].col), (3, 1))

    def test_input_types_eof_and_unrestricted_data(self):
        self.assert_program('📢👂,👂,👂,👂,👂,👂', '12 -7 3.5 abc  🕳️\n', '12\n-7\n3.5\nabc\n\n')
        self.assert_program('📢👂', 'a b ()\"\'\n', 'a b ()\"\'\n')
        self.assert_program('📢👂', '甲\n', '甲\r\n')

    def test_no_input_line_length_or_output_truncation(self):
        data = '甲' * 1_000_001
        self.assert_program('📢👂', data + '\n', data + '\n')
        self.assert_program('📢🔤x🔡✖️1000001', 'x' * 1_000_001 + '\n')
        self.assert_program('📢🤜🔤x🔡✖️1000000🤛➕🔤y🔡', 'x' * 1_000_000 + 'y\n')
        self.assert_program('📢🔤🔡➕🎁🔤x🔡✖️1000001🎀', '🎁🔤' + 'x' * 1_000_001 + '🔡🎀\n')

    def test_no_source_or_io_line_count_limit(self):
        self.assert_program('\n' * 120_000 + '📢7', '7\n')
        self.assert_program('📢1🔚\n' * 20_000, '1\n' * 20_000)
        self.assert_program('🔂i🛫1🛬20000👉📢👂👈', '甲\n' * 20_000, '甲\n' * 20_000)

    def test_more_than_original_ten_million_steps(self):
        interp = pymoji.Interpreter(out=io.StringIO(), inp=io.StringIO(), max_mem_mb=0)
        program = pymoji.Parser(pymoji.tokenize('🔂i🛫1🛬10000001👉👈')).parse_program()
        interp.run(program)
        self.assertGreater(interp.steps, 10_000_000)
        self.assertEqual(interp.globals.vars['i'], 10_000_001)

    def test_remaining_resource_controls(self):
        self.assertIn('超过了 8 层', self.execute('🏭f🤜🤛👉↩️f🤜🤛👈f🤜🤛', max_depth=8)[2])
        self.assertIn('内存上限', self.execute('📢🔤x🔡✖️10000000', max_mem_mb=1)[2])
        rc, out, err = self.execute('📢🎲🤜6🤛,🎲🤜1,100🤛', seed=8)
        self.assertEqual((rc, err), (0, ''))
        self.assertEqual(self.execute('📢🎲🤜6🤛,🎲🤜1,100🤛', seed=8)[1], out)

    def test_seeded_fuzz_has_no_internal_errors(self):
        rng = random.Random(22026)
        pieces = ['📢', '1', '2', '0', '甲', '_x', '🍎', '⬅️', '➕', '➖', '✖️',
                  '➗', '🚀', '🔚', '🤜', '🤛', '🎁', '🎀', ',', '🔤', '🔡',
                  '🛡️', '💭', '👉', '👈', '🤔', '🤷', '✅', '❌', '📍', '📤', '🚫']
        for trial in range(1000):
            source = ''.join(rng.choice(pieces) for _ in range(rng.randrange(1, 35)))
            rc, _, err = self.execute(source, max_mem_mb=8)
            with self.subTest(trial=trial):
                self.assertIn(rc, (0, 1))
                self.assertNotIn('解释器内部错误', err)

    def test_rainwater_algorithms_against_python_reference(self):
        path = os.path.join(os.path.dirname(__file__), 'examples', '接雨水.pymoji')
        with open(path, encoding='utf-8') as f:
            source = f.read()
        program = pymoji.Parser(pymoji.tokenize(source)).parse_program()
        interp = pymoji.Interpreter(out=io.StringIO(), max_mem_mb=0)
        interp.run([node for node in program if type(node) is pymoji.FuncDef])
        rng = random.Random(2026)
        samples = [[], [0], [2, 1, 2], [4, 2, 0, 3, 2, 5]]
        samples += [[rng.randrange(21) for _ in range(rng.randrange(41))] for _ in range(300)]
        samples.append([rng.randrange(1001) for _ in range(20_000)])
        for heights in samples:
            left, peak = [], 0
            for h in heights:
                peak = max(peak, h)
                left.append(peak)
            right, expected = 0, 0
            for i in range(len(heights) - 1, -1, -1):
                right = max(right, heights[i])
                expected += min(left[i], right) - heights[i]
            for name in ('接雨水', '单调栈'):
                with self.subTest(size=len(heights), function=name):
                    actual = interp.call(interp.globals.vars[name], [heights], pymoji.Const(1, None))
                    self.assertEqual(actual, expected)

    def test_command_line_modes_and_exit_codes(self):
        cli = self.cli

        self.assertEqual(cli('--version').stdout.strip(), 'pymoji ' + pymoji.__version__)
        self.assertIn('pymoji v' + pymoji.__version__, cli('--help').stdout)
        cyclic = 'a⬅️🎁🎀🔚a📥a🔚b⬅️🎁🎀🔚b📥b🔚📢a=b,a<b'
        result = cli('-c', cyclic, '--max-depth', '100000', '--max-mem', '256')
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '✅ ❌\n', ''))
        self.assertEqual(cli('-c', '📢1').stdout, '1\n')
        self.assertEqual(cli('-c', '📢1➗0').returncode, 1)
        self.assertEqual(cli('/no/such/pymoji/file').returncode, 2)
        self.assertEqual(cli('-c', '📢1', '--max-steps', '3').returncode, 2)
        self.assertEqual(cli('-c', '📢1', '--width', '1').returncode, 2)
        self.assertEqual(cli('-c', '📢1', '--max-mem', '-1').returncode, 2)
        self.assertEqual(cli('-c', '📢1', '--output', 'x').returncode, 2)
        self.assertIn('NEWLINE', cli('-c', 'a⬅️1🔚📢a', '--tokens').stdout)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, '矩形.pymoji')
            result = cli('-c', '甲⬅️1🔚📢甲', '--format', '--width', '13', '--output', path)
            self.assertEqual((result.returncode, result.stderr), (0, ''))
            self.assertEqual(cli(path, '--check-rectangle').returncode, 0)
            self.assertEqual(cli(path).stdout, '1\n')
            self.assertEqual(cli('-c', '📢1\n ', '--check-rectangle').returncode, 1)

    def test_check_mode_never_executes_and_accepts_free_layout(self):
        sources = ['', '💭只有注释', '📢1\n ', '📢未知变量', '📢1➗0',
                   '📢👂', '🔁✅👉📢1👈', '\ufeff📢7']
        for source in sources:
            with self.subTest(source=source):
                result = self.cli('-c', source, '--check')
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, '自由排版.pymoji')
            with open(path, 'w', encoding='utf-8-sig') as f:
                f.write('📢1\n ')
            self.assertEqual(self.cli(path, '--check').returncode, 0)
            self.assertEqual(self.cli(path, '--check-rectangle').returncode, 1)

    def test_cli_help_and_argument_errors_use_utf8(self):
        env = dict(os.environ, PYTHONIOENCODING='ascii', PYTHONUTF8='0')
        result = self.cli('--help', env=env)
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        self.assertIn('pymoji v' + pymoji.__version__, result.stdout)
        self.assertIn('标准输入', result.stdout)
        result = self.cli('-c', '📢1', '--width', '无效', env=env)
        self.assertEqual((result.returncode, result.stdout), (2, ''))
        self.assertIn('无效', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_check_mode_reports_errors_and_rejects_conflicting_modes(self):
        for source, fragment in [('📢1🔚\n📢🤜2', '第 2 行'), ('📢(1)', '字符不合规')]:
            result = self.cli('-c', source, '--check')
            self.assertEqual((result.returncode, result.stdout), (1, ''))
            self.assertIn(fragment, result.stderr)
            self.assertNotIn('Traceback', result.stderr)
        result = self.cli('-c', '📢' + '🤜' * 2000 + '1' + '🤛' * 2000, '--check')
        self.assertEqual(result.returncode, 1)
        self.assertIn('资源超限', result.stderr)
        for mode in ('--tokens', '--format', '--check-rectangle'):
            self.assertEqual(self.cli('-c', '📢1', '--check', mode).returncode, 2)
        self.assertEqual(self.cli('/no/such/pymoji/file', '--check').returncode, 2)
        self.assertEqual(self.cli('-c', '📢1', '--check', '-o', 'x').returncode, 2)

    def test_stdin_source_execution_and_runtime_input(self):
        for source, expected in [('📢🔤你好🌏🔡', '你好🌏\n'),
                                 ('\ufeff总数⬅️2🔚\r\n📢总数➕3', '5\n'),
                                 ('', ''), ('📢👂', '🕳️\n')]:
            with self.subTest(source=source):
                result = self.cli('-', data=source)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, ''))
        result = self.cli('-c', '📢👂', data='42\n')
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '42\n', ''))
        self.assertEqual(self.cli('-', '-c', '📢1', data='📢2').returncode, 2)

    def test_stdin_source_tool_modes(self):
        result = self.cli('-', '--check', data='📢1➗0')
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))
        result = self.cli('-', '--tokens', data='📢1')
        self.assertEqual(result.returncode, 0)
        self.assertIn('PRINT', result.stdout)
        self.assertIn('EOF', result.stdout)
        result = self.cli('-', '--format', '--width', '13', data='甲⬅️1🔚📢甲')
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        self.assertEqual(pymoji.check_rectangle(result.stdout)[0], 13)
        self.assertEqual(self.cli('-', data=result.stdout).stdout, '1\n')
        self.assertEqual(self.cli('-', '--check-rectangle', data=result.stdout).returncode, 0)
        result = self.cli('-', '--check', data='📢1🔚\n📢🤜2')
        self.assertEqual((result.returncode, result.stdout), (1, ''))
        self.assertIn('第 2 行', result.stderr)

    def test_stdin_source_rejects_invalid_utf8(self):
        script = os.path.join(os.path.dirname(__file__), 'pymoji.py')
        for mode in ([], ['--check'], ['--tokens'], ['--format'], ['--check-rectangle']):
            with self.subTest(mode=mode):
                result = subprocess.run([sys.executable, script, '-', *mode], input=b'\xff',
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
                self.assertEqual((result.returncode, result.stdout), (2, b''))
                self.assertIn('标准输入 不是 UTF-8', result.stderr.decode('utf-8'))

    def test_stdin_source_text_stream_and_read_failures(self):
        with patch('sys.stdin', io.StringIO('📢1➗0')):
            self.assertEqual(pymoji.main(['-', '--check']), 0)
        for exception, expected, fragment in [(OSError('读取失败'), 2, '无法读取 标准输入'),
                                              (KeyboardInterrupt(), 130, '已中断')]:
            err = io.StringIO()
            with patch('sys.stdin', io.StringIO()) as inp, patch('sys.stderr', err):
                with patch.object(inp, 'read', side_effect=exception):
                    self.assertEqual(pymoji.main(['-', '--check']), expected)
            self.assertIn(fragment, err.getvalue())


if __name__ == '__main__':
    unittest.main(verbosity=2)
