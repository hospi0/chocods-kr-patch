# -*- coding: utf-8 -*-
r"""카드 게임 첫 메뉴 로고(pubtopmenu NARC 4, 셀 0: ポップアップ / デュエル) 한글판.

바탕 = 사용자가 그림판으로 그린 빈 배너(tools/pudlogo_sketch.json, 2배 비교 그림에서 읽은 RGB) 그대로.
손대는 것은 «배너 안쪽 갈색 선» 위·아래 두 줄뿐: 삐뚤삐뚤한 선을 2차 곡선으로 맞춰 같은 굵기로 다시 긋고,
선 바깥쪽은 그림의 노란색, 안쪽은 그림의 크림색 한 색으로 메운다(그라데이션 없음). 날개·테는 건드리지 않는다.
글자 = 매끈한 윤곽 글꼴(도트 2배 확대 아님)을 흰 테두리 + 갈색 바깥 테두리로 그려 팔레트 가까운 색으로 옮긴다.
가운데 64×64 OBJ 4개(x 40‥167, 다른 셀과 안 나눠 씀)에만 되쓴다.
"""
import json
import os
from collections import Counter
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import pudlabel

SKETCH = json.load(open(os.path.join(os.path.dirname(__file__), 'pudlogo_sketch.json')))
FONT = 'C:/claude/utils/font/logo/BlackHanSans.ttf'
LINES = [('팝업', (88, 184, 40)), ('듀얼', (240, 152, 72))]   # 글자, 채움색(원본 초록·주황 한 색)
WHITE, DARK = (248, 248, 248), (112, 72, 32)
X0, X1 = 40, 168


def kind(c):
    r, g, b = c
    if (r, g, b) == (40, 40, 60):
        return '.'
    if r + g + b < 330:
        return 'D'
    if r >= 215 and g >= 195 and b >= 150 and r - b <= 80:
        return 'c'
    if r >= 200 and g >= 160 and b < 140:
        return 'Y'
    return 'm'


def build(ncer_b, ncgr_b, pal):
    sp = pudlabel.Sprites(ncer_b, ncgr_b)
    can, cov, x0, y0 = sp.canvas(0)
    H, W = len(can), len(can[0])
    cache = {}

    def pidx(rgb):
        rgb = tuple(rgb)
        if rgb not in cache:
            cache[rgb] = 0 if rgb == (40, 40, 60) else min(range(1, len(pal)), key=lambda v: sum((a - b) ** 2 for a, b in zip(pal[v], rgb)))
        return cache[rgb]
    img = [[tuple(SKETCH[y][x]) for x in range(W)] for y in range(H)]
    K = [[kind(c) for c in row] for row in img]
    cream = Counter(img[y][x] for y in range(50, 85) for x in range(70, 140) if K[y][x] == 'c').most_common(1)[0][0]

    def fix_line(ylo, yhi, outside_up):
        """(ylo‥yhi) 안의 짙은 선: 한쪽이 노랑, 다른 쪽이 크림인 열에서 선 가운데를 2차식으로 맞춰 다시 긋는다"""
        runs = {}
        for x in range(X0, X1):                          # 크림에 바로 붙은 짙은 줄만(바깥 테두리 짙은 줄과 섞지 않게)
            if outside_up:
                cs = [y for y in range(ylo, yhi) if K[y][x] == 'c' and K[y - 1][x] == 'D']
                if not cs:
                    continue
                b = cs[0] - 1
                a = b
                while K[a - 1][x] == 'D':
                    a -= 1
                if K[a - 1][x] in 'Ym':
                    runs[x] = (a, b)
            else:
                cs = [y for y in range(ylo, yhi) if K[y][x] == 'c' and K[y + 1][x] == 'D']
                if not cs:
                    continue
                a = cs[-1] + 1
                b = a
                while K[b + 1][x] == 'D':
                    b += 1
                if K[b + 1][x] in 'Ym':
                    runs[x] = (a, b)
        xs = sorted(runs)
        p = np.polyfit(xs, [(runs[x][0] + runs[x][1]) / 2 for x in xs], 4)   # 양 끝이 둥글게 내려가므로 4차
        th = int(round(np.median([runs[x][1] - runs[x][0] + 1 for x in xs])))
        dark = Counter(img[y][x] for x in xs for y in range(runs[x][0], runs[x][1] + 1)).most_common(1)[0][0]
        yel0 = Counter(img[runs[x][0] - 1][x] if outside_up else img[runs[x][1] + 1][x] for x in xs).most_common(1)[0][0]
        for x in range(xs[0], xs[-1] + 1):               # 선이 있는 구간 전체(조건에 안 맞던 열도 같은 곡선으로)
            s = int(round(np.polyval(p, x) - (th - 1) / 2))
            a, b = runs.get(x, (s - 3, s + th + 2))
            yel = (img[a - 1][x] if outside_up else img[b + 1][x]) if x in runs else yel0
            for y in range(min(a, s), max(b, s + th - 1) + 1):
                if K[y][x] not in 'DYcm':
                    continue
                if s <= y < s + th:
                    img[y][x] = dark
                elif (y < s) == outside_up:
                    img[y][x] = yel                      # 선 바깥 = 그 열의 노란색(그림 색)
                else:
                    img[y][x] = cream                    # 선 안쪽 = 크림 한 색
        return p, th
    pt, tht = fix_line(38, 60, True)
    pb, thb = fix_line(78, 96, False)
    # 금색 띠 안 얼룩(중간 갈색 점) → 그 줄의 노란색 — 가운데 구간만, 띠 = 바깥 짙은 테두리와 안쪽 선 사이
    for x in range(44, 166):                           # 오른쪽 끝 두 줄 사이 회갈색 줄도(사용자 지적)
        for lo, hi in ((34, int(np.polyval(pt, x) - tht / 2)), (int(np.polyval(pb, x) + thb / 2) + 1, 97)):
            ys = [y for y in range(lo, hi) if kind(img[y][x]) == 'Y']
            if not ys:
                continue
            yel = Counter(img[y][x] for y in ys).most_common(1)[0][0]
            for y in range(min(ys), max(ys) + 1):
                if kind(img[y][x]) == 'm':
                    img[y][x] = yel
    # 노란 띠 안 세로 회갈색 줄(오른쪽 위 두 줄 사이 — 사용자 지적): 좌우가 노랑인 중간색 화소 → 노랑
    for y in range(30, 100):
        for x in range(X0 + 1, X1 - 1):
            if kind(img[y][x]) == 'm' and kind(img[y][x - 1]) == 'Y' and kind(img[y][x + 1]) == 'Y':
                img[y][x] = img[y][x - 1]
    # 안쪽(두 선 사이)은 크림 한 색만 — 그림에 남은 회색 점·줄 지움(듀 왼쪽 아래 — 사용자 지적)
    for x in range(70, 146):                           # 양 끝 옆선(그림)은 건드리지 않게 가운데만
        t_, b_ = np.polyval(pt, x) + tht / 2, np.polyval(pb, x) - thb / 2
        for y in range(int(t_) + 1, int(b_)):
            if kind(img[y][x]) in 'mD' and kind(img[int((t_ + b_) / 2)][x]) == 'c':
                img[y][x] = cream
    # 글자: 윤곽 글꼴을 크게 그려(가장자리 섞임색 포함) 팔레트로 옮김 — 두 줄을 배너 안쪽에 나눠 넣는다
    top_in = max(np.polyval(pt, 106) + tht / 2, 0)
    bot_in = np.polyval(pb, 106) - thb / 2
    band = (bot_in - top_in) / 2
    base = Image.new('RGB', (W, H))
    base.putdata([c for row in img for c in row])
    dr = ImageDraw.Draw(base)
    dr.fontmode = '1'                                    # 가장자리 섞임색 없이(섞임색이 팔레트 회색으로 바뀌어 줄처럼 보였다)
    size = int(band * 1.15)                          # 더 크게(사용자) — 두 줄 테두리가 조금 겹쳐도 된다
    for k, (text, col) in enumerate(LINES):
        while True:
            f = ImageFont.truetype(FONT, size)
            bb = dr.textbbox((0, 0), text, font=f, stroke_width=3)
            if bb[3] - bb[1] <= band + 3 and bb[2] - bb[0] <= 104:
                break
            size -= 1
        cy = top_in + band * (k + 0.5)
        ox = 106 - (bb[0] + bb[2]) / 2
        oy = cy - (bb[1] + bb[3]) / 2
        dr.text((ox, oy), text, font=f, fill=DARK, stroke_width=3, stroke_fill=DARK)
        dr.text((ox, oy), text, font=f, fill=WHITE, stroke_width=2, stroke_fill=WHITE)
        dr.text((ox, oy), text, font=f, fill=col)
    px = list(base.getdata())
    for y in range(H):
        for x in range(X0, X1):
            can[y][x] = pidx(px[y * W + x])
    for o in sp.cells[0]:
        if o['w'] != 64:                                 # 가운데 64×64 네 개만(날개·테는 다른 OBJ)
            continue
        sp.put_obj(o, [[can[o['y'] - y0 + y][o['x'] - x0 + x] for x in range(o['w'])] for y in range(o['h'])])
    return sp.result()
