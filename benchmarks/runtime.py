#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""可复现的运行时基准；解析、解释器初始化与 GC 不计入执行时间。"""
import argparse
import gc
from pathlib import Path
import statistics
import subprocess
import sys
import time
import types


ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ('loop-1000000', 's⬅️0🔚🔂i🛫1🛬1000000👉s⬆️1👈', 's', 1000000),
    ('fib-25', '🏭fib🤜n🤛👉🤔n≤1👉↩️n👈↩️fib🤜n➖1🤛➕fib🤜n➖2🤛👈x⬅️fib🤜25🤛', 'x', 75025),
]


def load(source, name):
    module = types.ModuleType(name)
    module.__file__ = str(ROOT / 'pymoji.py')
    exec(compile(source, module.__file__, 'exec'), module.__dict__)
    return module


def sample(module, program, result_name, expected):
    gc.collect()
    interp = module.Interpreter()
    start = time.perf_counter()
    interp.run(program)
    elapsed = time.perf_counter() - start
    if interp.globals.vars[result_name] != expected:
        raise AssertionError('基准结果不正确')
    return elapsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compare-ref', help='要比较的 Git ref，例如 main 或某个 commit SHA')
    parser.add_argument('--repeats', type=int, default=5, help='采样次数（默认 5，取中位数）')
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('--repeats 至少为 1')
    current = load((ROOT / 'pymoji.py').read_text(encoding='utf-8'), 'pymoji_current')
    modules = [('current', current)]
    if args.compare_ref:
        try:
            source = subprocess.check_output(['git', 'show', args.compare_ref + ':pymoji.py'],
                                             cwd=str(ROOT), encoding='utf-8', stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as error:
            parser.error(error.stderr.strip())
        modules.insert(0, ('baseline', load(source, 'pymoji_baseline')))
    print('Python', sys.version.split()[0], '| repeats:', args.repeats, '| default resource limits')
    print('case             ' + ''.join(f'{label:>14}' for label, _ in modules) + '    speedup')
    for name, source, result_name, expected in CASES:
        programs = [(module, module.Parser(module.tokenize(source)).parse_program())
                    for _, module in modules]
        samples = [[] for _ in modules]
        for module, program in programs:
            sample(module, program, result_name, expected)  # 预热
        for trial in range(args.repeats):
            # 交替运行顺序，减少固定先后顺序带来的偏差。
            order = range(len(modules)) if trial % 2 == 0 else reversed(range(len(modules)))
            for index in order:
                module, program = programs[index]
                samples[index].append(sample(module, program, result_name, expected))
        medians = [statistics.median(values) for values in samples]
        speedup = f'{medians[0] / medians[-1]:.2f}x' if len(modules) == 2 else '—'
        print(f'{name:17}' + ''.join(f'{value:>13.4f}s' for value in medians) + f'    {speedup}')


if __name__ == '__main__':
    main()
