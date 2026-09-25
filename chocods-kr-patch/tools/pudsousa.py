# -*- coding: utf-8 -*-
r"""그림책 게임 조작 설명 머리글(mgentryphase/ja/sousa_*.PBG, 48장: 「あそびかた」) 한글판.

PBG 안 NCGR = 8bpp 64×80 타일 시트(8×10 타일), 머리글 = 위 16줄(타일 0‥15, 이 파일만 씀). 팔레트는 PBG 에 없다(공용).
파일마다 색번호가 달라 판 = 머리글에서 가장 흔한 색, 글자 = 두 번째로 흔한 색(어두운 글자)으로 잡고
판을 칠한 뒤 갈무리11 로 「놀이 방법」 을 한 색으로 그린다(원본 글자 높이 11 줄 · 3‥13 행).
"""
from collections import Counter
import bdf
import titlegfx
import ncer
import pudlabel

TEXT = '놀이 방법'
FONT = 'C:/claude/utils/font/Galmuri-v2.40.3/Galmuri11-Bold.bdf'   # 원본처럼 굵게


def patch(d):
    """d = 압축 푼 PBG(D2KP) 바이트 → 고친 바이트(크기 같음)"""
    B = pudlabel.blocks(d)
    gi, g = B['RGCN']
    o, sz = ncer.ncgr_data(g)
    data = bytearray(g[o:o + sz])
    px = lambda x, y: ((y // 8) * 8 + x // 8) * 64 + (y % 8) * 8 + x % 8
    cnt = Counter(data[px(x, y)] for y in range(16) for x in range(64))
    (plate, _), (ink, _) = cnt.most_common(2)
    for y in range(16):
        for x in range(64):
            data[px(x, y)] = plate
    m = titlegfx.bold_mask(TEXT, bdf.load(FONT), 1, titlegfx.NONE)
    mh, mw = len(m), len(m[0])
    ox, oy = (64 - mw) // 2, 3 + (11 - mh) // 2
    for y in range(mh):
        for x in range(mw):
            if m[y][x]:
                data[px(ox + x, oy + y)] = ink
    g2 = g[:o] + bytes(data) + g[o + sz:]
    return d[:gi] + g2 + d[gi + len(g):]
