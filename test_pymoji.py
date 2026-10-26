#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pymoji 1.1 语义回归、任意排版、边界与命令行验证。只依赖 Python 标准库。"""
import io
import os
import random
import subprocess
import sys
import tempfile
import unittest

import pymoji


class PymojiTests(unittest.TestCase):
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
            ('📢📏1', '只能量列表或文字'),
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
        script = os.path.join(os.path.dirname(__file__), 'pymoji.py')

        def cli(*args):
            return subprocess.run([sys.executable, script, *args], encoding='utf-8',
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)

        self.assertEqual(cli('--version').stdout.strip(), 'pymoji 1.1')
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
