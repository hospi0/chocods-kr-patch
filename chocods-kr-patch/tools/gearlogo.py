# -*- coding: utf-8 -*-
r"""파일 선택 화면 로고(UI/TM/base_16: 4bpp BG, 타일마다 16색 팔레트 14벌) + 도는 톱니(UI/TM/gear_16: OBJ 5프레임) 한글판.

타이틀(tl_ue)·파일 선택(base_16) 둘 다 톱니는 gear_16 스프라이트가 덮는다(화면 (32,56) — 파랑 조각 맞춤으로 실측).
스프라이트 안에는 「シドと」 와 부제 첫 글자 「チ」 조각·띠 가장자리까지 들어 있다.
  · base_16: 톱니 몸체 자리(5프레임 톱니 화소 합) 는 원본 판 그대로, 나머지는 한글 로고(v13)를 타일마다 가장 맞는 팔레트로 줄여 넣는다.
             원본에서 투명(0)이던 흰 바탕은 투명 그대로. 바뀌지 않은 타일은 원본 배치 그대로.
  · gear_16: 톱니 얼굴 글자 칸(GEAR_FACE) 은 v13 화소, 파랑·노랑 화소는 v13 화소, 그 밖(톱니 몸체)은 원본 — 각 OBJ 팔레트로 최근접.
"""
import struct
import ncer
import logoimg

GEAR_POS = (32, 56)
GEAR_FACE = (40, 70, 66, 89)             # 화면 좌표 x0,y0,x1,y1 — 「シドと」(탁점 포함) 가 있던 톱니 얼굴 → v13 화소
WHITE = (248, 248, 248)


def _near(pal16, c, allow0=False):
    best, bi = None, None
    for k in range(0 if allow0 else 1, 16):
        e = sum((a - b) ** 2 for a, b in zip(pal16[k], c))
        if best is None or e < best:
            best, bi = e, k
    return bi, best


GEARS = ((53, 79, 19.5), (81, 73, 15.5))   # 화면 좌표 톱니 원(중심 x, y, 바깥 반지름) — 색이 아니라 자리로 가른다


def _is_gear_at(X, Y, c):
    """톱니 원 안이면서 파랑이 아닌 화소 = 톱니 몸체(「チ」 주황 가장자리가 색만으로는 톱니로 잡혔다)"""
    inside = any((X - cx) ** 2 + (Y - cy) ** 2 <= r * r for cx, cy, r in GEARS)
    yellow = c[0] > 0xc0 and c[1] > 0x90 and c[2] < 0x70      # 「チ」 꼬리
    olive = c[0] - c[1] <= 16 and c[0] - c[2] >= 30 and c[0] < 190   # 옛 「チ」 획 가장자리(올리브) — 「초」 위 점 두 개(PoC-2d)
    return inside and not (c[2] > c[0] + 40) and not yellow and not olive


def gear_mask(ncer_b, ncgr_b, pal):
    """5프레임 톱니 몸체 화소(화면 좌표) 합"""
    cells = ncer.cells(ncer_b)
    o, sz = ncer.ncgr_data(ncgr_b)
    T = ncgr_b[o:o + sz]
    m = set()
    for objs in cells:
        for ob in objs:
            px = ncer.obj_pixels(T, ob)
            for y in range(ob['h']):
                for x in range(ob['w']):
                    v = px[y][x]
                    X, Y = GEAR_POS[0] + ob['x'] + x, GEAR_POS[1] + ob['y'] + y
                    if v and _is_gear_at(X, Y, pal[ob['pal'] * 16 + v]):
                        m.add((X, Y))
    return m


def patch_gear(ncer_b, ncgr_b, pal, logo):
    cells = ncer.cells(ncer_b)
    o, sz = ncer.ncgr_data(ncgr_b)
    tiles = bytearray(ncgr_b[o:o + sz])
    old = bytes(tiles)
    lp = logo.load()
    fx0, fy0, fx1, fy1 = GEAR_FACE
    done = set()
    for objs in cells:
        for ob in objs:
            key = (ob['tile'], ob['w'], ob['h'], ob['pal'])
            if key in done:
                continue
            done.add(key)
            px = ncer.obj_pixels(old, ob)
            p16 = pal[ob['pal'] * 16:ob['pal'] * 16 + 16]
            for y in range(ob['h']):
                for x in range(ob['w']):
                    v = px[y][x]
                    if not v:
                        continue
                    X, Y = GEAR_POS[0] + ob['x'] + x, GEAR_POS[1] + ob['y'] + y
                    c = pal[ob['pal'] * 16 + v]
                    if (fx0 <= X < fx1 and fy0 <= Y < fy1) or not _is_gear_at(X, Y, c):
                        px[y][x] = _near(p16, lp[X, Y])[0]
            ncer.put_obj(tiles, ob, px)
    return ncgr_b[:o] + bytes(tiles) + ncgr_b[o + sz:]


def _flip(tb, hf, vf):
    px = [(tb[j // 2] >> (4 * (j & 1))) & 15 for j in range(64)]
    out = bytearray(32)
    for y in range(8):
        for x in range(8):
            v = px[(7 - y if vf else y) * 8 + (7 - x if hf else x)]
            out[(y * 8 + x) // 2] |= v << (4 * (x & 1))
    return bytes(out)


def patch_base(nscr, ncgr, pal, logo, gmask, orig_logo):
    """orig_logo: 원본 tl_ue 렌더(RGB) — v13 과 같은 블록은 base_16 원본 그대로."""
    si, w, h, ssz, m = logoimg._scr(nscr)
    i = ncgr.index(b'RAHC')
    csz = struct.unpack_from('<I', ncgr, i + 0x18)[0]
    data = bytearray(ncgr[i + 0x20:i + 0x20 + csz])
    lp = logo.load()
    olp = orig_logo.load()
    used_pals = sorted({e >> 12 for e in m})

    def orig_px(e, x, y):
        t, hf, vf = e & 0x3ff, (e >> 10) & 1, (e >> 11) & 1
        xx, yy = (7 - x if hf else x), (7 - y if vf else y)
        b = data[t * 32 + yy * 4 + xx // 2]
        return (b >> (4 * (xx & 1))) & 15

    out_m = list(m)
    changed = 0
    for ty in range(192 // 8):
        for tx in range(w // 8):
            k = ty * (w // 8) + tx
            e = m[k]
            op = e >> 12
            ocol = [[pal[op * 16 + orig_px(e, x, y)] if orig_px(e, x, y) else None for x in range(8)] for y in range(8)]
            want = []
            for y in range(8):
                row = []
                for x in range(8):
                    X, Y = tx * 8 + x, ty * 8 + y
                    if (X, Y) in gmask:
                        row.append(('keep', ocol[y][x]))
                    else:
                        c = lp[X, Y]
                        row.append(('t', None) if (c == WHITE and ocol[y][x] is None) else ('c', c))
                want.append(row)
            if all(lp[tx * 8 + x, ty * 8 + y] == olp[tx * 8 + x, ty * 8 + y] or (tx * 8 + x, ty * 8 + y) in gmask
                   for y in range(8) for x in range(8)):
                continue                                             # 한글 로고가 원본 로고와 같은 블록 → base_16 원본 그대로
            best = None
            for p in used_pals:
                p16 = pal[p * 16:p * 16 + 16]
                err = 0
                idx = []
                for y, row in enumerate(want):
                    for x, (kind, c) in enumerate(row):
                        if kind == 't' or (kind == 'keep' and c is None):
                            idx.append(0)
                            continue
                        n, e2 = _near(p16, c)
                        idx.append(n)
                        err += e2
                if best is None or err < best[0]:
                    best = (err, p, idx)
            _, p, idx = best
            tb = bytearray(32)
            for j in range(64):
                y, x = divmod(j, 8)
                tb[y * 4 + x // 2] |= idx[j] << (4 * (x & 1))
            tb = bytes(tb)
            t = ('new', tb)
            out_m[k] = (tb, p)
            changed += 1
    # 전체 다시 배정: 안 바뀐 칸은 원본 타일(뒤집기 유지), 바뀐 칸은 새 타일 — 같은 내용은 하나로
    tiles_old = [bytes(data[k * 32:(k + 1) * 32]) for k in range(csz // 32)]
    order = [bytes(32)]
    index = {bytes(32): 0}
    final = []
    for e in out_m:
        if isinstance(e, tuple):
            tb, p = e
            flags = 0
        else:
            tb, p, flags = tiles_old[e & 0x3ff], e >> 12, e & 0x0c00
        hit = None
        for hf in (0, 1):                                    # 뒤집어 같은 타일이면 하나로(2 칸 모자람 해결)
            for vf in (0, 1):
                fb = _flip(tb, hf, vf)
                if fb in index:
                    hit = (index[fb], hf, vf)
                    break
            if hit:
                break
        if hit is None:
            index[tb] = len(order)
            order.append(tb)
            hit = (index[tb], 0, 0)
        n, hf, vf = hit
        f2 = flags ^ (hf << 10) ^ (vf << 11)
        final.append(n | f2 | (p << 12))
    limit = csz // 32
    merged = []
    while len(order) > limit:                                # 넘치면 가장 비슷한 새 타일끼리 합친다(화소 차이 최소)
        def px(tb):
            return [(tb[j // 2] >> (4 * (j & 1))) & 15 for j in range(64)]
        P = [px(t) for t in order]
        best = None
        for a in range(len(order) - 1, 0, -1):
            for b in range(1, len(order)):
                if a == b:
                    continue
                d = sum(1 for u, v in zip(P[a], P[b]) if u != v)
                if best is None or d < best[0]:
                    best = (d, a, b)
            if best and best[0] <= 1:
                break
        d, a, b = best
        merged.append(d)
        final = [((b if (e & 0x3ff) == a else (e & 0x3ff) - (1 if (e & 0x3ff) > a else 0)) | (e & 0xfc00)) for e in final]
        del order[a]
    assert len(order) <= limit, 'base_16 타일 %d > %d' % (len(order), limit)
    if merged:
        print('    base_16 타일 합침: 차이 화소', merged)
    new_data = b''.join(order) + bytes(csz - len(order) * 32)
    ncgr2 = ncgr[:i + 0x20] + new_data + ncgr[i + 0x20 + csz:]
    nscr2 = nscr[:si + 0x14] + struct.pack('<%dH' % len(final), *final) + nscr[si + 0x14 + ssz:]
    free = [None] * (csz // 32 - len(order))
    return nscr2, ncgr2, changed, len(free)


def overlay_gear(img, ncer_b, ncgr_b, pal, frame=0):
    """톱니 스프라이트 한 프레임을 화면 (32,56) 에 겹친 그림(타이틀 로고 원본용)"""
    out = img.copy()
    cells = ncer.cells(ncer_b)
    o, sz = ncer.ncgr_data(ncgr_b)
    T = ncgr_b[o:o + sz]
    for ob in reversed(cells[frame]):
        px = ncer.obj_pixels(T, ob)
        for y in range(ob['h']):
            for x in range(ob['w']):
                v = px[y][x]
                if v:
                    out.putpixel((GEAR_POS[0] + ob['x'] + x, GEAR_POS[1] + ob['y'] + y), pal[ob['pal'] * 16 + v])
    return out
