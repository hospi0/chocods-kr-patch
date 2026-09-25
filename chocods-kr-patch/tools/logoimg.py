# -*- coding: utf-8 -*-
r"""타이틀 로고 그림(TL/TL.FBC → tl_ue.fbc: TITLE_UE.NSCR 256×192 + NCGR 8bpp + NCLR) 을 한글 로고 PNG 로 교체.

  · 원본 색번호 판을 NSCR·NCGR 에서 복원 → 바뀌지 않은 화소는 원본 번호 그대로, 바뀐 화소만 팔레트 최근접 색(0번 제외).
  · 8×8 타일로 쪼개 같은 타일(좌우·상하 뒤집기 포함)은 하나로 → NCGR·NSCR 재작성.
  · 타일 수는 원본(384) 이하로 막는다(BG 문자 영역 크기 불변).
"""
import struct

TILE = 64


def _pal(nclr):
    j = nclr.index(b'TTLP')
    n = struct.unpack_from('<I', nclr, j + 0x10)[0] // 2
    return [((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3) for c in struct.unpack_from('<%dH' % n, nclr, j + 0x18)]


def _scr(nscr):
    i = nscr.index(b'NRCS')
    w, h = struct.unpack_from('<HH', nscr, i + 8)
    sz = struct.unpack_from('<I', nscr, i + 0x10)[0]
    return i, w, h, sz, list(struct.unpack_from('<%dH' % (sz // 2), nscr, i + 0x14))


def _chr(ncgr):
    i = ncgr.index(b'RAHC')
    sz = struct.unpack_from('<I', ncgr, i + 0x18)[0]
    return i, sz, ncgr[i + 0x20:i + 0x20 + sz]


def index_image(nscr, ncgr):
    """→ 색번호 판[y][x]"""
    _, w, h, _, m = _scr(nscr)
    _, _, data = _chr(ncgr)
    img = [[0] * w for _ in range(h)]
    for k, e in enumerate(m[:(w // 8) * (h // 8)]):
        t, hf, vf = e & 0x3ff, (e >> 10) & 1, (e >> 11) & 1
        tx, ty = k % (w // 8), k // (w // 8)
        for y in range(8):
            for x in range(8):
                v = data[t * TILE + (7 - y if vf else y) * 8 + (7 - x if hf else x)]
                img[ty * 8 + y][tx * 8 + x] = v
    return img


def replace(nscr, ncgr, nclr, png_rgb):
    """png_rgb: PIL RGB 256×192 → (새 NSCR, 새 NCGR, 타일 수)"""
    pal = _pal(nclr)
    orig = index_image(nscr, ncgr)
    H, W = len(orig), len(orig[0])
    px = png_rgb.load()
    cache = {}
    cand = list(range(1, 256))

    def near(c):
        if c not in cache:
            cache[c] = min(cand, key=lambda k: sum((a - b) ** 2 for a, b in zip(pal[k], c)))
        return cache[c]
    img = [[orig[y][x] if pal[orig[y][x]] == px[x, y] else near(px[x, y]) for x in range(W)] for y in range(H)]
    tiles = []
    index = {}
    m = []
    for ty in range(H // 8):
        for tx in range(W // 8):
            t = [img[ty * 8 + y][tx * 8 + x] for y in range(8) for x in range(8)]
            found = None
            for hf in (0, 1):
                for vf in (0, 1):
                    key = bytes(t[(7 - y if vf else y) * 8 + (7 - x if hf else x)] for y in range(8) for x in range(8))
                    if key in index:
                        found = (index[key], hf, vf)
                        break
                if found:
                    break
            if not found:
                key = bytes(t)
                index[key] = len(tiles)
                tiles.append(key)
                found = (index[key], 0, 0)
            n, hf, vf = found
            m.append(n | (hf << 10) | (vf << 11))
    i, sz, data = _chr(ncgr)
    assert len(tiles) * TILE <= sz, '로고 타일 %d 개 > 원본 %d 개' % (len(tiles), sz // TILE)
    new_data = b''.join(tiles) + bytes(sz - len(tiles) * TILE)
    ncgr2 = ncgr[:i + 0x20] + new_data + ncgr[i + 0x20 + sz:]
    si, w, h, ssz, om = _scr(nscr)
    m += om[len(m):]
    nscr2 = nscr[:si + 0x14] + struct.pack('<%dH' % len(m), *m) + nscr[si + 0x14 + ssz:]
    return nscr2, ncgr2, len(tiles)
