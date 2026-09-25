# -*- coding: utf-8 -*-
r"""메뉴 그림 글자(타일 OBJ) 한글판 — 셀 판에서 «영역» 안의 옛 글자 화소만 지우고 새 글자를 그려 제자리에 되쓴다.

작업 = (파일, 셀, 영역 x0,y0,x1,y1(끝 제외), 글자, 글꼴, 채움 색, 테두리 색|None, 지울 색들, 바탕 색 규칙)
  바탕 규칙: 정수 = 그 색 / 'plate' = y ≥ 4 면 9 아니면 0 (되찾은 기억 머리 글자: 판 위쪽은 투명)
글자 타일은 같은 라벨의 변형 셀끼리만 나눠 쓴다(조사: docs §13) → 한 셀만 고치면 변형도 같이 바뀐다.
"""
import bdf
import hudlabel
import ncer

FD = 'C:/claude/utils/font/Galmuri-v2.40.3/'
ITEM = 'romdata/UI/ITEMMENU/ui_item.FBC.z'
DGN = 'romdata/UI/UPMDSTAT/ui_dgn_center.FBC.z'
CLOAK = 'romdata/UI/CNTR/ui_cloak.FBC.z'
KAIZO = 'romdata/UI/CSTMBOX/ui_kaizo.FBC.z'
B, F = 11, 15

JOBS = [
    (ITEM, 1, (14, 3, 52, 13), '정리', 'Galmuri7', B, None, {B}, 2),          # せいとん
    (ITEM, 21, (14, 3, 52, 13), '복수', 'Galmuri7', B, None, {B}, 2),         # ふくすう
    (ITEM, 18, (4, 1, 38, 9), '발밑', 'Galmuri7', B, F, {B, F}, 6),           # あしもと
    (ITEM, 19, (20, 4, 60, 12), '단축키', 'Galmuri7', B, F, {B, F, 2}, 0),    # ショートカット: 글자 OBJ(타일 71·75)만 — 밑 판(타일 80)은 네 번 반복 사용
    (DGN, 0, (0, 0, 16, 8), '직업', 'Galmuri7', 1, None, {1}, 0),             # ジョブ(Lv)
    (DGN, 2, (0, 0, 16, 8), '직업', 'Galmuri7', 1, None, {1}, 0),             # ジョブ(Lv UP) — x 16 부터는 「Lv」
    (DGN, 2, (52, 0, 68, 8), '남은', 'Galmuri7', 5, None, {5}, 0),            # あと
    (DGN, 3, (0, 0, 45, 9), '되찾은', 'Galmuri7', B, F, {B, F}, 'plate'),     # とりもどした
    (CLOAK, 0, (14, 3, 52, 13), '전부', 'Galmuri7', B, None, {B}, 2),        # ぜんぶ(셀 1 과 글자 타일 공유)
    (KAIZO, 1, (14, 3, 52, 13), '정리', 'Galmuri7', B, None, {B}, 2),        # せいとん(셀 2 공유)
    (KAIZO, 6, (14, 3, 52, 13), '설명', 'Galmuri7', B, None, {B}, 2),        # せつめい(셀 7 공유)
    (KAIZO, 3, (4, 3, 53, 13), '개조하기', 'Galmuri7', 7, None, {7}, 2),     # 改造する(보통)
    (KAIZO, 4, (4, 3, 53, 13), '개조하기', 'Galmuri7', 7, None, {7}, 14),    # 改造する(눌림, 셀 5 공유)
    (DGN, 3, (22, 10, 45, 21), '기억', 'Galmuri9', B, F, {B, F}, 'plate2'),  # 記憶 — 원본은 흰 글자+검은 테두리(검은 바탕 아님, 실기 지적)
]


def apply(path, ncer_b, ncgr_b):
    cells = ncer.cells(ncer_b)
    o, sz = ncer.ncgr_data(ncgr_b)
    tiles = bytearray(ncgr_b[o:o + sz])
    fonts = {}
    done = []
    for p, c, (rx0, ry0, rx1, ry1), text, fname, fill, edge, erase, bg in JOBS:
        if p != path:
            continue
        objs = cells[c]
        can, cov, x0, y0 = ncer.cell_canvas(objs, lambda ob: ncer.obj_pixels(bytes(tiles), ob))
        for y in range(ry0, ry1):
            for x in range(rx0, rx1):
                if can[y][x] in erase:
                    can[y][x] = bg if isinstance(bg, int) else (
                        (9 if y >= 4 else 0) if bg == 'plate' else (9 if y <= 17 else 0))   # plate2: 판은 17행까지
        if fname not in fonts:
            fonts[fname] = bdf.load(FD + fname + '.bdf')
        W, H = rx1 - rx0, ry1 - ry0
        ol = 1 if edge is not None else 0
        try:
            img = hudlabel.label(text, fonts[fname], W, H, 1, ol, 0, center=True)
        except AssertionError:                             # 7 px 글자 + 테두리 = 9 > 8 칸 → 위 테두리 한 줄은 잘라도 된다
            img = hudlabel.label(text, fonts[fname], W, H, 1, ol, 0, clip_top=True)
        for y in range(H):
            for x in range(W):
                v = img[y][x]
                if v == 1:
                    can[ry0 + y][rx0 + x] = fill
                elif v == 2 and edge is not None:
                    can[ry0 + y][rx0 + x] = edge
        # 화소마다 «맨 앞에 보이는 OBJ»(원본에서 그 자리에 0 아닌 화소를 가진 첫 OBJ, 없으면 덮는 첫 OBJ) 에만 쓴다
        #  — 아이콘이 글자 영역에 걸쳐도 아이콘 타일은 그대로, 글자 조각 OBJ 는 영역에 조금만 걸쳐도 고친다(실기 두 번 지적)
        orig = [ncer.obj_pixels(bytes(tiles), ob) for ob in objs]
        rep = {}
        for k, ob in enumerate(objs):
            if sum(1 for o2 in objs if o2['tile'] == ob['tile']) > 1:
                continue                                   # 셀 안 반복 바탕 타일
            rep[k] = [r[:] for r in orig[k]]
        for y in range(ry0, ry1):
            for x in range(rx0, rx1):
                cands = [k for k, ob in enumerate(objs)
                         if ob['x'] - x0 <= x < ob['x'] - x0 + ob['w'] and ob['y'] - y0 <= y < ob['y'] - y0 + ob['h']]
                if not cands:
                    continue
                vis = [k for k in cands if orig[k][y - (objs[k]['y'] - y0)][x - (objs[k]['x'] - x0)]]
                k = vis[0] if vis else cands[0]
                if k not in rep:                           # 맨 앞이 반복 바탕 타일이면 그보다 앞의 쓸 수 있는 OBJ 에(단축키 — 실기 지적)
                    front = [j for j in cands if j in rep and j < k]
                    k = front[0] if front else k
                if k in rep:
                    rep[k][y - (objs[k]['y'] - y0)][x - (objs[k]['x'] - x0)] = can[y][x]
        for k, px in rep.items():
            if px != orig[k]:
                ncer.put_obj(tiles, objs[k], px)
        done.append(text)
    return ncgr_b[:o] + bytes(tiles) + ncgr_b[o + sz:], done
