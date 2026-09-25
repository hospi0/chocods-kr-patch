# -*- coding: utf-8 -*-
r"""필드 지역 이름(UI/AREANAME/area_*.FBC: NCER 1셀 + NCGR 4bpp 1D 타일, 팔레트 9) 한글판.

원본: 굵은 한자(흰 15 → 회색 12 세로 명암) + 검은 테두리(7), 오른쪽 맞춤, 아래 줄에 후리가나.
한글: 후리가나 없이 이름만 한 줄 — 원래 OBJ 배치(폭) 안에서 가장 큰 글자 크기로, 세로 가운데.
글꼴: 갈무리 비트맵(14 가로 굵게 / 11 Bold / 11 중 칸에 맞는 것) + 8방향 테두리 — TTF 는 작게 줄이면 뭉개짐.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import ncer

FONT = 'C:/claude/utils/font/logo/BlackHanSans.ttf'
NAMES = {'church': '교회', 'clock': '시계탑 광장', 'downtown': '상업구', 'mine': '광산구',
         'stella': '스텔라 목장', 'suburb': '거주구', 'templeD': '어둠의 신전'}
OUTLINE = 7
RAMP = [15, 15, 14, 14, 13, 13, 12, 12]          # 위 → 아래 명암


def text_mask(text, W, H):
    """비트맵 글꼴로(TTF 는 작게 줄이면 획이 뭉개짐 — 실측): 갈무리14 가로 굵게 → 11 Bold → 11 순으로 칸에 맞는 것."""
    import bdf, titlegfx
    FD = 'C:/claude/utils/font/Galmuri-v2.40.3/'
    tries = [(text, f, d) for f, d in (('Galmuri14', titlegfx.HORIZ), ('Galmuri11-Bold', titlegfx.NONE), ('Galmuri11', titlegfx.NONE))]
    if ' ' in text:                                      # 그래도 넘치면 띄어쓰기를 뺀다(던전 이름과 같은 방침)
        tries += [(text.replace(' ', ''), f, d) for f, d in (('Galmuri11-Bold', titlegfx.NONE), ('Galmuri11', titlegfx.NONE))]
    for t, fname, dil in tries:
        m = titlegfx.bold_mask(t, bdf.load(FD + fname + '.bdf'), 1, dil)
        if len(m[0]) + 2 <= W and len(m) + 2 <= H:
            img = Image.new('L', (len(m[0]), len(m)), 0)
            for y, r in enumerate(m):
                for x, v in enumerate(r):
                    if v:
                        img.putpixel((x, y), 255)
            return img
    raise AssertionError('%r 이 %d×%d 에 안 들어감' % (text, W, H))


def build(ncer_b, ncgr_b, text):
    cells = ncer.cells(ncer_b)
    objs = cells[0]
    o, sz = ncer.ncgr_data(ncgr_b)
    tiles = bytearray(ncgr_b[o:o + sz])
    x0 = min(ob['x'] for ob in objs); y0 = min(ob['y'] for ob in objs)
    W = max(ob['x'] + ob['w'] for ob in objs) - x0
    H = max(ob['y'] + ob['h'] for ob in objs) - y0
    m = text_mask(text, W - 2, H - 4)
    mw, mh = m.size
    ox = W - 2 - mw                          # 오른쪽 맞춤(원본처럼 끝 2 px 여백)
    oy = (H - mh) // 2
    can = [[0] * W for _ in range(H)]
    ink = [(ox + x, oy + y) for y in range(mh) for x in range(mw) if m.getpixel((x, y))]
    for (x, y) in ink:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if 0 <= x + dx < W and 0 <= y + dy < H:
                    can[y + dy][x + dx] = OUTLINE
    for (x, y) in ink:
        can[y][x] = RAMP[min(len(RAMP) - 1, (y - oy) * len(RAMP) // max(1, mh))]
    for ob in objs:
        px = [[can[ob['y'] - y0 + y][ob['x'] - x0 + x] for x in range(ob['w'])] for y in range(ob['h'])]
        ncer.put_obj(tiles, ob, px)
    return ncgr_b[:o] + bytes(tiles) + ncgr_b[o + sz:]
