# -*- coding: utf-8 -*-
r"""카드 이름 그림(PUD/card/ja/name_XXXX.NCGR, 147장) 한글판.

파일 번호 = 카드 id(card.bin 기록 [0]). 64×32 8bpp, 카드 팔레트 224‥239 = 검정→흰 회색 16단(147장 전부 확인).
위 줄 = 몬스터 이름(갈무리9, 왼쪽), 아래 줄 = 기술 이름(갈무리14 굵게 → 11 굵게 → 11 → 콘덴스드, 오른쪽 맞춤),
원본 후리가나는 없앤다. 28‥31 줄(아래 밝은 띠)은 원본 그대로.
"""
import bdf
import titlegfx
import ncer

FD = 'C:/claude/utils/font/Galmuri-v2.40.3/'
BLACK, WHITE = 224, 239
_f = {}


def font(n):
    if n not in _f:
        _f[n] = bdf.load(FD + n + '.bdf')
    return _f[n]


def render(g, name, skill):
    o, sz = ncer.ncgr_data(g)
    data = bytearray(g[o:o + sz])
    px = lambda x, y: ((y // 8) * 8 + x // 8) * 64 + (y % 8) * 8 + x % 8
    for y in range(28):
        for x in range(64):
            data[px(x, y)] = BLACK
    for t, fn in ((name, 'Galmuri9'), (name.replace(' ', ''), 'Galmuri9'), (name, 'Galmuri7'), (name.replace(' ', ''), 'Galmuri7')):
        m = titlegfx.bold_mask(t, font(fn), 1, titlegfx.NONE)   # 넘치면 띄어쓰기 삭제 → 갈무리7
        if len(m[0]) <= 62:
            break
    assert len(m[0]) <= 62, '이름 %r 폭 %d' % (name, len(m[0]))
    for y in range(len(m)):
        for x in range(len(m[0])):
            if m[y][x]:
                data[px(2 + x, 1 + y)] = WHITE
    done = False
    for t in (skill, skill.replace(' ', '')):
        for fn, dil in (('Galmuri14', titlegfx.HORIZ), ('Galmuri11-Bold', titlegfx.NONE), ('Galmuri11', titlegfx.NONE),
                        ('Galmuri11-Condensed', titlegfx.NONE), ('Galmuri9', titlegfx.NONE)):
            m = titlegfx.bold_mask(t, font(fn), 1, dil)
            if len(m[0]) <= 62 and len(m) <= 16:
                done = True
                break
        if done:
            break
    assert len(m[0]) <= 62, '기술 %r 폭 %d' % (skill, len(m[0]))
    mh, mw = len(m), len(m[0])
    ox, oy = 62 - mw, 27 - mh                              # 오른쪽·아래 맞춤(원본처럼)
    for y in range(mh):
        for x in range(mw):
            if m[y][x]:
                data[px(ox + x, oy + y)] = WHITE
    return g[:o] + bytes(data) + g[o + sz:]
