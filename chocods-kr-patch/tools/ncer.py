# -*- coding: utf-8 -*-
r"""NCER(셀) · NCGR(4bpp 1D 타일) · NCLR 읽기 — 셀을 그림으로 그리고, 그림을 셀 타일로 되돌려 쓴다."""
import struct

SH = {(0, 0): (8, 8), (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64), (1, 0): (16, 8), (1, 1): (32, 8),
      (1, 2): (32, 16), (1, 3): (64, 32), (2, 0): (8, 16), (2, 1): (8, 32), (2, 2): (16, 32), (2, 3): (32, 64)}


def cells(b):
    i = b.index(b'KBEC')
    n, ext, off, mode = struct.unpack_from('<HHII', b, i + 8)
    base = i + 8 + off
    cs = 16 if ext else 8
    ob = base + n * cs
    out = []
    for c in range(n):
        no, attr, oo = struct.unpack_from('<HHI', b, base + c * cs)
        objs = []
        for k in range(no):
            a0, a1, a2 = struct.unpack_from('<HHH', b, ob + oo + 6 * k)
            y = a0 & 0xff
            y = y - 256 if y > 127 else y
            x = a1 & 0x1ff
            x = x - 512 if x > 255 else x
            w, h = SH[(a0 >> 14, a1 >> 14)]
            objs.append(dict(x=x, y=y, w=w, h=h, tile=a2 & 0x3ff, pal=a2 >> 12, hf=(a1 >> 12) & 1, vf=(a1 >> 13) & 1, raw=(a0, a1, a2)))
        out.append(objs)
    return out


def ncgr_data(b):
    """→ (타일 데이터 시작 오프셋, 길이)"""
    i = b.index(b'RAHC')
    sz = struct.unpack_from('<I', b, i + 0x18)[0]
    return i + 0x20, sz


def nclr(b):
    i = b.index(b'TTLP')
    sz = struct.unpack_from('<I', b, i + 0x10)[0]
    n = sz // 2
    return [((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3) for c in struct.unpack_from('<%dH' % n, b, i + 0x18)]


def obj_pixels(tiles, o):
    """OBJ 하나 → 2차원 색번호(1D 매핑, 4bpp)"""
    w, h = o['w'], o['h']
    px = [[0] * w for _ in range(h)]
    for ty in range(h // 8):
        for tx in range(w // 8):
            t = o['tile'] + ty * (w // 8) + tx
            tb = tiles[t * 32:(t + 1) * 32]
            for y in range(8):
                for x in range(8):
                    px[ty * 8 + y][tx * 8 + x] = (tb[y * 4 + x // 2] >> (4 * (x & 1))) & 15
    return px


def put_obj(tiles, o, px):
    for ty in range(o['h'] // 8):
        for tx in range(o['w'] // 8):
            t = o['tile'] + ty * (o['w'] // 8) + tx
            for y in range(8):
                for x in range(0, 8, 2):
                    tiles[t * 32 + y * 4 + x // 2] = px[ty * 8 + y][tx * 8 + x] | (px[ty * 8 + y][tx * 8 + x + 1] << 4)


def obj_pixels_bitmap(data, o, unit=32):
    """NCBR(선형 비트맵) OBJ: 시작 = tile × unit 바이트, 폭 w 의 4bpp 줄들."""
    w, h = o['w'], o['h']
    st = o['tile'] * unit
    px = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            k = y * w + x
            b = data[st + k // 2] if st + k // 2 < len(data) else 0
            px[y][x] = (b >> (4 * (k & 1))) & 15
    return px


def put_obj_bitmap(data, o, px, unit=32):
    """NCBR OBJ 에 4bpp 선형 비트맵 쓰기"""
    w, h = o['w'], o['h']
    st = o['tile'] * unit
    for y in range(h):
        for x in range(0, w, 2):
            k = (y * w + x) // 2
            data[st + k] = px[y][x] | (px[y][x + 1] << 4)


def cell_canvas(objs, getpx):
    """셀의 OBJ 들을 한 판에 합친다 → (판[y][x] 색번호, 덮임[y][x] bool, x0, y0)"""
    x0 = min(o['x'] for o in objs); y0 = min(o['y'] for o in objs)
    W = max(o['x'] + o['w'] for o in objs) - x0; H = max(o['y'] + o['h'] for o in objs) - y0
    can = [[0] * W for _ in range(H)]
    cov = [[False] * W for _ in range(H)]
    for o in reversed(objs):
        px = getpx(o)
        for y in range(o['h']):
            for x in range(o['w']):
                cov[o['y'] - y0 + y][o['x'] - x0 + x] = True
                if px[y][x]:
                    can[o['y'] - y0 + y][o['x'] - x0 + x] = px[y][x]
    return can, cov, x0, y0
