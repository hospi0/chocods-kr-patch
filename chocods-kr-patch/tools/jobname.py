# -*- coding: utf-8 -*-
r"""직업 얼굴 그림(UI/JOBCFACE/jobico_*·jobico2_*) 안의 직업명 글자 한글판.

스테이터스 창 직업명은 텍스트 직업 표(PLY_JOBPARAM)가 아니라 이 그림을 쓴다(실기: 표를 「스핑」 으로 바꿔도 「すっぴん」,
세이브스테이트 RAM 에는 표가 이미 「스핑」 — 2026-09-24).
이름 칸 = 셀 0 의 팔레트 10 OBJ(32×16 [+16×16]). 원본 꼴: 게임 글꼴 글리프 색 11 + 오른쪽 아래 그림자 색 4, 칸 왼쪽 +4 px.
"""
import ncer
import titletext

JOBS = {'suppin': '스핑', 'knight': '나이트', 'dragon': '용기사', 'dark': '암흑기사', 'ninja': '닌자', 'thief': '시프',
        'schol': '학자', 'scholar': '학자', 'black': '흑마도사', 'white': '백마도사', 'dancer': '무희', 'red': '적마도사',
        'herox': '히어로X', 'cid': '시드'}
FILL, SHADOW = 11, 4


def patch(ncer_b, ncgr_b, font, text):
    cells = ncer.cells(ncer_b)
    objs = [ob for ob in cells[0] if ob['pal'] == 10]
    o, sz = ncer.ncgr_data(ncgr_b)
    tiles = bytearray(ncgr_b[o:o + sz])
    x0 = min(ob['x'] for ob in objs)
    y0 = min(ob['y'] for ob in objs)
    W = max(ob['x'] + ob['w'] for ob in objs) - x0
    line = titletext.render_line(font, [('W', text)])
    lw = len(line[0])
    lx = 4 if lw + 5 <= W else max(0, (W - lw - 1) // 2)
    assert lx + lw <= W, '직업명 %r 폭 %d > 칸 %d' % (text, lw, W)
    can = [[0] * W for _ in range(16)]
    ink = [(lx + x, 2 + y) for y in range(10) for x in range(lw) if line[y][x]]
    for (x, y) in ink:
        if x + 1 < W and y + 1 < 16:
            can[y + 1][x + 1] = SHADOW
    for (x, y) in ink:
        can[y][x] = FILL
    for ob in objs:
        px = [[can[ob['y'] - y0 + y][ob['x'] - x0 + x] for x in range(ob['w'])] for y in range(ob['h'])]
        ncer.put_obj(tiles, ob, px)
    return ncgr_b[:o] + bytes(tiles) + ncgr_b[o + sz:]
