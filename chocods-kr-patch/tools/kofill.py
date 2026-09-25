# -*- coding: utf-8 -*-
r"""같은 원문 채우기 — 번역 파일에 한 번 쓴 줄을, 같은 표(안쪽 경로) 안에서 원문이 똑같은 다른 번호에도 붙인다.

  python tools/kofill.py work/ko/05_item_txt0.tsv [--dry]

이미 어느 번역 파일(work/ko/*.tsv)에든 있는 번호는 건드리지 않는다. 붙인 줄은 파일 끝 「# kofill」 아래에 머리줄과 함께.
"""
import glob
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocheck


def main():
    path = sys.argv[1]
    src = kocheck.source()
    done = set()
    for p in glob.glob(os.path.join(kocheck.KO_DIR, '*.tsv')):
        for _, r in kocheck.load(p):
            done.add((r[0], r[1], int(r[2])))
    by_text = defaultdict(list)
    for key, t in src.items():
        by_text[(key[0], key[1], t)].append(key)
    add = defaultdict(list)
    for _, r in kocheck.load(path):
        f, inner, i, ko = r
        for key in by_text[(f, inner, src[(f, inner, int(i))])]:
            if key not in done:
                add[(f, inner)].append((key[2], ko))
                done.add(key)
    n = sum(len(v) for v in add.values())
    if '--dry' not in sys.argv and n:
        with open(path, 'a', encoding='utf-8') as fo:
            fo.write('# kofill — 원문이 같은 번호\n')
            for (f, inner), rows in add.items():
                fo.write('@\t%s\t%s\n' % (f, inner))
                for i, ko in sorted(rows):
                    fo.write('%d\t%s\n' % (i, ko))
    print('채움 %d줄' % n)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
