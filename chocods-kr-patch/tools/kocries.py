# -*- coding: utf-8 -*-
r"""초코보 울음·이름 채우기 — 이벤트 대사(EVTMSG*) 중 원문이 울음소리 한 줄뿐인 번호를 정해진 번역으로,
이름 칸(번호 100 미만)은 다른 장에서 이미 옮긴 같은 원문의 번역으로 work/ko/29_cries.tsv 에.

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
    names = {}                              # 이름 칸 원문 → 번역(다른 장에서)
    for p in glob.glob(os.path.join(kocheck.KO_DIR, '*.tsv')):
        if os.path.abspath(p) == os.path.abspath(OUT):
            continue
        for _, r in kocheck.load(p):
            key = (r[0], r[1], int(r[2]))
            done.add(key)
            if 'EVTMSG' in r[1] and key[2] < 100:
                names[src[key]] = r[3]
    rows = defaultdict(list)
    for key, t in sorted(src.items()):
        if 'EVTMSG' not in key[1] or key in done:
            continue
        if t in CRIES:
            rows[key[:2]].append((key[2], CRIES[t]))
        elif key[2] < 100 and t in names:
            rows[key[:2]].append((key[2], names[t]))
    with open(OUT, 'w', encoding='utf-8') as fo:
        fo.write('# 초코보 울음·이름 칸 — tools/kocries.py 가 만듦(손으로 고치지 말 것)\n')
        for (f, inner), rs in sorted(rows.items()):
            fo.write('@\t%s\t%s\n' % (f, inner))
            for i, ko in rs:
                fo.write('%d\t%s\n' % (i, ko))
    print('울음·이름 %d줄' % sum(len(v) for v in rows.values()))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
