# -*- coding: utf-8 -*-
r"""카드 게임 번역 검사(ROM 필요 — 폭 계산에 PUD 글꼴) — work/pud_src.tsv ↔ work/ko_pud/*.tsv

  python tools/pudcheck.py [--todo]

검사: 번호가 원문에 있나 · 제어 표기({1B}X {03}{SFF}{01} {00} …) 개수 같음 · 쪽 수 같음 ·
쪽마다 줄 수 ≤ 원문 그 쪽 줄 수(쪽 넘김 없는 ptx 한 쪽은 원문 줄 수) · 줄 픽셀 폭 ≤ 그 파일 원문 최대 줄 폭 ·
부호 뒤 공백 없음 · 반각 ~ 금지(일본 글꼴 0x7E = 윗줄) · 가나·한자 남음.
jc 는 ja 번역을 그대로 쓰는 것이 기본(쪽 수가 같을 때) — 다르면 jc 줄을 따로 적어야 한다(--todo 에 나옴).
"""
import collections
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'pud_src.tsv')
KO = os.path.join(ROOT, 'work', 'ko_pud')
BS = chr(92) + 'n'
TOK = re.compile(r'\{1B\}(?:\{1B\}|[^{])|\{S?[0-9A-F]{2}\}')   # ESC+글자 · ESC ESC(색 끝) · {XX}
PAGE = re.compile(r'\{03\}\{SFF\}\{0[12]\}')
JP = re.compile(r'[ぁ-ヺー-ヿ一-鿿ｦ-ﾟ]')   # ・(30FB) 는 부호


def src():
    out = {}
    for ln in open(SRC, encoding='utf-8'):
        if ln.startswith('#'):
            continue
        p, kind, i, t = ln.rstrip('\n').split('\t')
        out[(p, int(i))] = (kind, t)
    return out


def ko():
    out = {}
    for path in sorted(glob.glob(os.path.join(KO, '*.tsv'))):
        for n, ln in enumerate(open(path, encoding='utf-8'), 1):
            if ln.startswith('#') or not ln.strip():
                continue
            q = ln.rstrip('\n').split('\t')
            out[(q[0], int(q[1]))] = (q[2], '%s:%d' % (os.path.basename(path), n))
    return out


def jc_to_ja(p):
    return p.replace('/jc/', '/ja/')


class Width:
    def __init__(self):
        import ndspy.rom, nftr
        from gfxsurvey import ORIG
        f = nftr.Nftr(ndspy.rom.NintendoDSRom.fromFile(ORIG).getFileByName('romdata/PUD/font/font.nftr'))
        self.f = f

    def __call__(self, line):
        t = 0
        for c in TOK.sub('', line):
            if '가' <= c <= '힣':
                t += 10
                continue
            i = self.f.lookup(ord(c))
            t += self.f.widths[i][2] if i is not None else 10
        return t


# 폭 한도 덮어쓰기 — secret(해금 목록)은 위 화면 목록 창이라 원문 최대(182)보다 넓다고 보고 200(⏳실기 확인)
BOX_MAX = {'romdata/PUD/mgentryphase/text/ja/secret': 200, 'romdata/PUD/mgentryphase/text/jc/secret': 200}


def box(p, kind):
    """폭 한도를 나눠 쓰는 단위 — ptx 는 같은 폴더(같은 화면 상자), 표는 파일"""
    return os.path.dirname(p) if kind == 'ptx' else p


def pages(t, kind):
    return PAGE.split(t) if kind == 'table' else [t]


def lines(pg):
    return [l for l in TOK.sub('', pg).split(BS)]


def main():
    S = src()
    K = ko()
    W = Width()
    maxw = collections.defaultdict(int)
    for (p, i), (kind, t) in S.items():
        for pg in pages(t, kind):
            for l in lines(pg):
                maxw[box(p, kind)] = max(maxw[box(p, kind)], W(l))
    for k2, v in BOX_MAX.items():
        maxw[k2] = max(maxw[k2], v)
    errs = []
    for (p, i), (k, loc) in K.items():
        if (p, i) not in S:
            errs.append('%s 원문에 없는 번호 %s %d' % (loc, p, i))
            continue
        kind, jp = S[(p, i)]
        e = []
        if collections.Counter(TOK.findall(jp)) != collections.Counter(TOK.findall(k)):
            e.append('제어 다름 원문%s 번역%s' % (dict(collections.Counter(TOK.findall(jp)) - collections.Counter(TOK.findall(k))),
                                                 dict(collections.Counter(TOK.findall(k)) - collections.Counter(TOK.findall(jp)))))
        jps, kps = pages(jp, kind), pages(k, kind)
        if len(jps) != len(kps):
            e.append('쪽 수 %d → %d' % (len(jps), len(kps)))
        for a, b in zip(jps, kps):
            if len(lines(b)) > max(len(lines(a)), 1):
                e.append('쪽 줄 수 %d > %d 「%s」' % (len(lines(b)), len(lines(a)), lines(b)[0][:12]))
            for l in lines(b):
                if W(l) > maxw[box(p, kind)]:
                    e.append('줄 폭 %d > %d 「%s」' % (W(l), maxw[box(p, kind)], l))
        if re.search('[가-힣]', k):
            for m in re.finditer(r'[,.!?:;] +', k):
                e.append('부호 뒤 공백 「%s」' % k[max(0, m.start() - 4):m.end() + 2])
        if '~' in k:
            e.append('반각 ~')
        kk = JP.findall(TOK.sub('', k))
        if kk:
            e.append('가나·한자 남음 %s' % ''.join(kk))
        errs += ['✗ %s [%s #%d] %s' % (loc, p.split('/')[-1], i, x) for x in e]
    for x in errs:
        print(x)
    # 남은 것
    todo = collections.Counter()
    for (p, i), (kind, t) in S.items():
        if not JP.search(t) or '/en/' in p:
            continue
        if (p, i) in K:
            continue
        if '/jc/' in p:
            ja = jc_to_ja(p)
            jn = sum(1 for (q, j) in S if q == ja)
            cn = sum(1 for (q, j) in S if q == p)
            if (ja, i) in K and jn == cn:
                continue
        todo['/'.join(p.split('/')[2:5])] += 1
    print('번역 %d줄 · 오류 %d · 남음 %d' % (len(K), len(errs), sum(todo.values())))
    if '--todo' in sys.argv:
        for k, v in sorted(todo.items()):
            print('  ', v, k)
    syl = set(c for k, _ in K.values() for c in k if '가' <= c <= '힣')
    print('카드 게임 글꼴에 필요한 한글 %d음절' % len(syl))


if __name__ == '__main__':
    main()
