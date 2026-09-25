# -*- coding: utf-8 -*-
r"""카드 게임 첫 메뉴 배너(pubtopmenu NARC 3, 셀 1‥6) 한글판 — 깨끗한 판을 새로 칠하고 글자를 얹는다(사용자 지정).

셀마다 글자 OBJ(다른 셀과 안 나눠 쓰는 것)만 되쓴다. 판 영역을 줄마다 «여섯 배너 공통 종이색»으로 칠해
옛 글자·잔무늬를 없애고, 갈무리 글꼴 + 1 px 테두리로 글자를 그린다.
"""
from collections import Counter
import bdf
import titlegfx
import pudlabel

FD = 'C:/claude/utils/font/Galmuri-v2.40.3/'
# 셀: (글자, 판 영역 x0,y0,x1,y1(셀 좌표), 채움색, 테두리색)
JOBS = {1: ('무선', (42, 8, 85, 31)), 2: ('트레이닝', (24, 8, 85, 31)), 3: ('카드 덱', (24, 8, 85, 31)),
        4: ('플레이어 정보', (24, 8, 85, 31)), 5: ('튜토리얼', (24, 8, 85, 31)), 6: ('끝내기', (24, 16, 90, 40))}
FILL = {6: 125}                                          # 끝내기 = 원본 おわり 파랑, 나머지 = 원본 노랑(222)
import json as _json, os as _os
BLANK = _json.load(open(_os.path.join(_os.path.dirname(__file__), 'pudbanner_blank.json')))
FONTS = ['Galmuri14', 'Galmuri11-Bold', 'Galmuri11', 'Galmuri11-Condensed', 'Galmuri9']   # 플레이어 정보 = 콘덴스드(크게 — 사용자)


def build(ncer_b, ncgr_b, pal):
    sp = pudlabel.Sprites(ncer_b, ncgr_b)
    own = sp.owners()
    txt = lambda v: sum(pal[v]) < 300 or (pal[v][0] > 200 and pal[v][2] < 150) or pal[v][2] > pal[v][0] + 60   # 글자(테두리·노랑·파랑)
    for c, (text, (rx0, ry0, rx1, ry1)) in JOBS.items():
        can, cov, x0, y0 = sp.canvas(c)
        if c != 6:                                       # 1‥5 = 사용자가 만든 빈 판(플레이어 정보 자리, tools/pudbanner_blank.json RGB)을 그대로 깐다
            idx = {}
            for v in range(len(pal)):
                idx.setdefault(tuple(pal[v]), v)
            for y in range(8, 32):
                for x in range(42 if c == 1 else 24, 88):   # 무선은 왼쪽 아이콘 자리 그대로
                    can[y][x] = idx[tuple(BLANK[y][x])]
            rx0 = 42 if c == 1 else 24
            rowc = None
        # 줄마다 판 색 = 그 줄에서 글자 아닌 화소의 최빈값(같은 모양 배너끼리 모아서)
        if c == 6:
            group = [k for k in JOBS if JOBS[k][1][1] == ry0] if c != 1 else [2, 3, 4, 5]
            rowc = {}
            for y in range(ry0, ry1):
                cnt = Counter()
                for k in group:
                    ck, _, _, _ = sp.canvas(k)
                    cnt.update(v for v in ck[y][rx0:rx1] if v and not txt(v) and pudlabel._lum(pal, v) >= 180)   # 밝은 종이색만(옛 글자 갈색이 섞이면 가운데에 띠가 생긴다)
                rowc[y] = cnt.most_common(1)[0][0] if cnt else rowc.get(y - 1)
            for y in range(ry1 - 1, ry0 - 1, -1):              # 밝은 색이 없는 줄은 아래 줄 색
                if rowc[y] is None:
                    rowc[y] = rowc.get(y + 1)
            for y in range(ry0, ry1):
                for x in range(rx0, rx1):
                    can[y][x] = rowc[y]
            if c != 6:                                       # 오른쪽 접힌 자리(x 85‥88)는 글자가 짧은 Wi-Fi 배너(셀 0)에서 깨끗한 것을 복사(무선 찌꺼기)
                c0, _, _, _ = sp.canvas(0)
                for y in range(ry0, ry1):
                    for x in range(85, 88):
                        can[y][x] = c0[y][x]
        fillc = FILL.get(c, 222)
        edge = Counter(v for r in sp.canvas(c)[0] for v in r if v and sum(pal[v]) < 250).most_common(1)[0][0]
        m = None
        for f in FONTS:
            mm = titlegfx.bold_mask(text, bdf.load(FD + f + '.bdf'), 1, titlegfx.HORIZ if f == 'Galmuri14' else titlegfx.NONE)   # 14 는 가로로 굵게(원본 굵은 글자)
            if len(mm[0]) + 2 <= rx1 - rx0 and len(mm) + 2 <= ry1 - ry0:
                m = mm
                break
        assert m, '셀 %d %r 안 들어감' % (c, text)
        mh, mw = len(m), len(m[0])
        ox = (rx0 + rx1) // 2 - mw // 2
        oy = (ry0 + ry1) // 2 - mh // 2 + (2 if c != 6 else 0)   # 1‥5 는 2 px 아래로(사용자)
        ink = [(ox + x, oy + y) for y in range(mh) for x in range(mw) if m[y][x]]
        for x, y in ink:
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    can[y + dy][x + dx] = edge
        for x, y in ink:
            can[y][x] = fillc
        for o in sp.cells[c]:
            if set().union(*[own[t] for t in sp.tiles_of(o)]) - {c}:
                continue                                 # 리본(여러 셀 공유)은 그대로
            px = [[can[o['y'] - y0 + y][o['x'] - x0 + x] for x in range(o['w'])] for y in range(o['h'])]
            sp.put_obj(o, px)
    return sp.result()
