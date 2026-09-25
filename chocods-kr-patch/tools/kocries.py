# -*- coding: utf-8 -*-
r"""초코보 울음 채우기 — 이벤트 대사(EVTMSG*) 중 원문이 울음소리 한 줄뿐인 번호를 정해진 번역으로 work/ko/29_cries.tsv 에.

  python tools/kocries.py

이미 다른 번역 파일에 있는 번호는 건너뛴다(매번 29_cries.tsv 를 새로 쓴다).
"""
import glob
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kocheck

CRIES = {                                   # 초코보 울음(docs/02_용어표.md §4 — 초코보 キュウ = 쿠엣)
    'キュウ！{13}': '쿠엣!{13}',
    'キュウ？{13}': '쿠엣?{13}',
    'キュウ…{13}': '쿠엣…{13}',
    'キュキュキュ！{13}': '쿠엣쿠엣쿠엣!{13}',
    'キュルル？{13}': '쿠르르?{13}',
    'クピピ…{13}': '쿠피피…{13}',
    'キュピーー！！{13}': '쿠에에엑!!{13}',
}
OUT = os.path.join(kocheck.KO_DIR, '29_cries.tsv')


def main():
    src = kocheck.source()
    done = set()
    for p in glob.glob(os.path.join(kocheck.KO_DIR, '*.tsv')):
        if os.path.abspath(p) == os.path.abspath(OUT):
            continue
        for _, r in kocheck.load(p):
            done.add((r[0], r[1], int(r[2])))
    rows = defaultdict(list)
    for key, t in sorted(src.items()):
        if 'EVTMSG' in key[1] and t in CRIES and key not in done:
            rows[key[:2]].append((key[2], CRIES[t]))
    with open(OUT, 'w', encoding='utf-8') as fo:
        fo.write('# 초코보 울음 — tools/kocries.py 가 만듦(손으로 고치지 말 것)\n')
        for (f, inner), rs in sorted(rows.items()):
            fo.write('@\t%s\t%s\n' % (f, inner))
            for i, ko in rs:
                fo.write('%d\t%s\n' % (i, ko))
    print('울음 %d줄' % sum(len(v) for v in rows.values()))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
