# -*- coding: utf-8 -*-
r"""위 화면 HUD 그림 글자(ui_common 셀) 한글 그리기.

  label(text, font, W, H, gap, outline, shadow) → 색 역할 2차원 배열: 0 투명 · 1 글자 · 2 테두리
  bdf 글리프를 이어 붙이고(자간 gap) 8방향 테두리 + (선택) 오른쪽 아래 그림자 → W×H 가운데 정렬.
"""
import bdf


def text_bits(text, font, gap):
    G, asc = font
    cols = []
    H = 0
    glyphs = []
    for ch in text:
        w, h, xo, yo, adv, rows = G[ord(ch)]
        arr, adv = bdf.render(G, asc, ord(ch), adv + 2, asc + 4, asc)
        glyphs.append(arr)
    # 글자마다 잉크 좌우 끝으로 잘라 자간 gap 으로 붙인다
    ch_h = len(glyphs[0])
    out = [[] for _ in range(ch_h)]
    for k, arr in enumerate(glyphs):
        xs = [x for row in arr for x, v in enumerate(row) if v]
        if not xs:                                     # 띄어쓰기: 빈 3 px
            for y in range(ch_h):
                out[y] += [0] * 3
            continue
        x0, x1 = min(xs), max(xs)
        for y in range(ch_h):
            out[y] += arr[y][x0:x1 + 1] + ([0] * gap if k + 1 < len(glyphs) else [])
    ys = [y for y, row in enumerate(out) if any(row)]
    return out[min(ys):max(ys) + 1]


def label(text, font, W, H, gap=1, outline=1, shadow=0, clip_top=False, dy=0, center=False, clip_bottom=False):
    """clip_top: 글자+아래 테두리만 칸 높이에 맞추고 위 테두리는 잘려도 된다(おなか 24×8 칸)."""
    b = text_bits(text, font, gap)
    h, w = len(b), len(b[0])
    ow, oh = w + 2 * outline + shadow, h + 2 * outline + shadow
    assert ow <= W, '%r 폭 %d 인데 칸은 %d' % (text, ow, W)
    assert (oh - outline if (clip_top or clip_bottom) else oh) <= H, '%r 높이 %d 인데 칸은 %d' % (text, oh, H)
    if clip_bottom:                                # 위에 붙임(아래 테두리 잘림 — 상태 팝업, 사용자 지정)
        ox, oy = (W - ow) // 2 + outline, outline
    elif clip_top:                                 # 아래에 붙임(위 테두리 잘림)
        ox, oy = (W - ow) // 2 + outline, H - outline - shadow - h
    elif center:                                   # 메뉴 라벨(labelgfx): 영역 가운데
        ox, oy = (W - ow) // 2 + outline, (H - oh) // 2 + outline
    else:                                          # 원본 「チョコボ」 처럼 왼쪽 위에 붙임
        ox, oy = outline, outline + dy
    img = [[0] * W for _ in range(H)]
    ink = {(ox + x, oy + y) for y in range(h) for x in range(w) if b[y][x]}
    for (x, y) in ink:
        for ddx in range(-outline, outline + 1 + shadow):
            for ddy in range(-outline, outline + 1 + shadow):
                if 0 <= x + ddx < W and 0 <= y + ddy < H:
                    img[y + ddy][x + ddx] = 2
    for (x, y) in ink:
        img[y][x] = 1
    return img


FONT_DIR = 'C:/claude/utils/font/Galmuri-v2.40.3/'
# (셀 번호, 글자 OBJ 개수(앞에서부터), 글자, 글꼴, 자간, 테두리, 그림자, 위 잘림, 글자 색번호, 테두리 색번호, 아래로 px) — 색번호는 원본 그림에서 읽음
HUD = [
    (27, 2, '초코보', 'Galmuri9', 1, 1, 1, False, 10, 2, 2),       # 위 화면 이름(주황, 팔레트 10) 40×16 — 11 Bold 는 «너무 굵고 거대» (사용자)
    (3, 2, '만복도', 'Galmuri7', 0, 1, 0, True, 1, 3, 0),            # 순무 아래 おなか(흰 글자, 팔레트 8) 24×8
]


def patch_ui_common(ncgr, ncer_b):
    """ui_common.NCGR 의 글자 OBJ 타일(다른 셀과 안 나눠 씀)을 한글로 다시 그린다."""
    import ncer
    cells = ncer.cells(ncer_b)
    o, sz = ncer.ncgr_data(ncgr)
    tiles = bytearray(ncgr[o:o + sz])
    fonts = {}
    for c, nobj, text, fname, gap, ol, sh, clip, ink, edge, dy in HUD:
        objs = cells[c][:nobj]
        x0 = min(ob['x'] for ob in objs)
        y0 = min(ob['y'] for ob in objs)
        W = max(ob['x'] + ob['w'] for ob in objs) - x0
        H = max(ob['y'] + ob['h'] for ob in objs) - y0
        if fname not in fonts:
            fonts[fname] = bdf.load(FONT_DIR + fname + '.bdf')
        img = label(text, fonts[fname], W, H, gap, ol, sh, clip, dy)
        role = {0: 0, 1: ink, 2: edge}
        for ob in objs:
            px = [[role[img[ob['y'] - y0 + y][ob['x'] - x0 + x]] for x in range(ob['w'])] for y in range(ob['h'])]
            ncer.put_obj(tiles, ob, px)
    return ncgr[:o] + bytes(tiles) + ncgr[o + sz:]
