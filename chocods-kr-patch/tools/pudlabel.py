# -*- coding: utf-8 -*-
r"""카드 게임(PUD) 스프라이트 글자 자동 한글화 — D2KP(.POBJ/.pobj) 또는 NARC 안 D2KP 의 NCER + NCGR(4/8bpp 1D 타일).

셀마다:
  1) 판 정하기 — 가장 흔한 색이 셀 화소의 35% 이상이고 그 색 테두리 상자가 셀의 70% 이상을 덮으면 «판 위 글자»,
     아니면 «글자만» 셀. 작업에 rect=(x0,y0,x1,y1) 를 주면 그 안만 글자 영역.
  2) 글자 화소 = 글자만: 0 아닌 모든 화소 / 판: 판 안쪽(판 상자 2 px 안) 에서 판 색이 아닌 화소.
  3) 색 역할 = 테두리: 글자 화소 중 «글자 아닌 이웃»에 가장 많이 닿는 색, 채움: 그 밖 색을 줄마다 최빈값(세로 명암 유지).
  4) 옛 글자 지움(판 → 판 색, 글자만 → 0) → 원래 글자 높이에 맞는 갈무리 글꼴로 그림(칸에 안 맞으면 글꼴을 낮추고, 그래도면 띄어쓰기 삭제).
  5) OBJ 가 덮는 칸에만 되쓴다. 같은 셀 안에서 반복 쓰는 타일·다른 셀과 나눠 쓰는 타일은 건드리지 않는다(assert).
"""
import struct
from collections import Counter
import bdf
import ncer
import titlegfx
import titletext

FD = 'C:/claude/utils/font/Galmuri-v2.40.3/'
FONTS = [('Galmuri14', titlegfx.HORIZ, 14), ('Galmuri11-Bold', titlegfx.NONE, 11), ('Galmuri11', titlegfx.NONE, 11),
         ('Galmuri9', titlegfx.HORIZ, 9),
         ('Galmuri9', titlegfx.NONE, 9), ('Galmuri7', titlegfx.NONE, 7)]
_fc = {}


def _font(name):
    if name not in _fc:
        _fc[name] = bdf.load(FD + name + '.bdf')
    return _fc[name]


def blocks(d):
    """D2KP 안 표준 블록 위치 {마법: (오프셋, 바이트)}"""
    out = {}
    for mg in (b'RLCN', b'RGCN', b'RCSN', b'RECN', b'RNAN'):
        i = d.find(mg)
        if i >= 0:
            sz = struct.unpack_from('<I', d, i + 8)[0]
            out[mg.decode()] = (i, d[i:i + sz])
    return out


class Sprites:
    def __init__(self, ncer_b, ncgr_b):
        self.cells = ncer.cells(ncer_b)
        i = ncgr_b.index(b'RAHC')
        self.bpp = 8 if struct.unpack_from('<I', ncgr_b, i + 12)[0] == 4 else 4
        mp = struct.unpack_from('<I', ncgr_b, i + 16)[0]
        self.unit = {0x10: 32, 0x0: 32, 0x100010: 64, 0x200010: 128, 0x300010: 256}.get(mp, 32)
        self.o, self.sz = ncer.ncgr_data(ncgr_b)
        self.ncgr = ncgr_b
        self.data = bytearray(ncgr_b[self.o:self.o + self.sz])
        self.tsz = 64 if self.bpp == 8 else 32

    def tiles_of(self, ob):
        first = ob['tile'] * self.unit // self.tsz
        return list(range(first, first + ob['w'] * ob['h'] // 64))

    def obj_px(self, ob):
        ts = self.tiles_of(ob)
        px = [[0] * ob['w'] for _ in range(ob['h'])]
        k = 0
        for ty in range(ob['h'] // 8):
            for tx in range(ob['w'] // 8):
                t = ts[k]; k += 1
                for y in range(8):
                    for x in range(8):
                        if self.bpp == 8:
                            v = self.data[t * 64 + y * 8 + x]
                        else:
                            v = (self.data[t * 32 + y * 4 + x // 2] >> (4 * (x & 1))) & 15
                        px[ty * 8 + y][tx * 8 + x] = v
        return px

    def put_obj(self, ob, px):
        ts = self.tiles_of(ob)
        k = 0
        for ty in range(ob['h'] // 8):
            for tx in range(ob['w'] // 8):
                t = ts[k]; k += 1
                for y in range(8):
                    for x in range(8):
                        v = px[ty * 8 + y][tx * 8 + x]
                        if self.bpp == 8:
                            self.data[t * 64 + y * 8 + x] = v
                        else:
                            o = t * 32 + y * 4 + x // 2
                            self.data[o] = (self.data[o] & (0xF0 if x & 1 == 0 else 0x0F)) | (v << (4 * (x & 1)))

    def canvas(self, c):
        objs = self.cells[c]
        x0 = min(o['x'] for o in objs); y0 = min(o['y'] for o in objs)
        W = max(o['x'] + o['w'] for o in objs) - x0; H = max(o['y'] + o['h'] for o in objs) - y0
        can = [[0] * W for _ in range(H)]
        cov = [[False] * W for _ in range(H)]
        for o in reversed(objs):
            px = self.obj_px(o)
            for y in range(o['h']):
                for x in range(o['w']):
                    cov[o['y'] - y0 + y][o['x'] - x0 + x] = True
                    if px[y][x]:
                        can[o['y'] - y0 + y][o['x'] - x0 + x] = px[y][x]
        return can, cov, x0, y0

    def owners(self):
        own = {}
        for c, objs in enumerate(self.cells):
            for o in objs:
                for t in self.tiles_of(o):
                    own.setdefault(t, set()).add(c)
        return own

    def result(self):
        return self.ncgr[:self.o] + bytes(self.data) + self.ncgr[self.o + self.sz:]


def _lum(pal, v):
    if not pal or v >= len(pal):
        return v
    r, g, b = pal[v]
    return 0.3 * r + 0.59 * g + 0.11 * b


def analyze(can, rect=None, pal=None, pk=lambda v: v, dark_plate=False):
    H, W = len(can), len(can[0])
    nz = [(x, y) for y in range(H) for x in range(W) if can[y][x]]
    cnt = Counter(can[y][x] for x, y in nz)
    plate = None
    ax0 = min(x for x, _ in nz); ax1 = max(x for x, _ in nz); ay0 = min(y for _, y in nz); ay1 = max(y for _, y in nz)
    for pc, pn in cnt.most_common(3):
        if _lum(pal, pk(pc)) < 60 and not dark_plate:    # 어두운 색은 판이 아니다(테두리·그림자) — 'plate' 지정 셀(せんせき)만 예외
            continue
        pts = [(x, y) for x, y in nz if can[y][x] == pc]
        bx0 = min(x for x, _ in pts); bx1 = max(x for x, _ in pts)
        by0 = min(y for _, y in pts); by1 = max(y for _, y in pts)
        if pn >= 0.30 * len(nz) and (bx1 - bx0 + 1) >= 0.6 * (ax1 - ax0 + 1) and (by1 - by0 + 1) >= 0.6 * (ay1 - ay0 + 1):
            plate = (pc, (bx0 + 2, by0 + 2, bx1 - 1, by1 - 1))
        break
    if rect:
        area = rect
    elif plate:
        area = plate[1]
    else:
        area = (0, 0, W, H)
    x0, y0, x1, y1 = area
    pc = plate[0] if plate else None
    text = [(x, y) for y in range(max(0, y0), min(H, y1)) for x in range(max(0, x0), min(W, x1))
            if can[y][x] and can[y][x] != pc]
    return plate, area, text


def roles(can, text, pc, pal=None, pk=lambda v: v):
    """테두리 = 글자 화소 중 가장 어두운 쪽의 최빈 색, 채움 = 그보다 밝은 색을 줄마다 최빈값."""
    cnt = Counter(can[y][x] for x, y in text)
    lums = sorted(cnt, key=lambda v: _lum(pal, pk(v)))
    dark = [v for v in lums if _lum(pal, pk(v)) <= _lum(pal, pk(lums[0])) + 40]
    edge = max(dark, key=lambda v: cnt[v]) if dark else None
    rows = {}
    for (x, y) in text:
        v = can[y][x]
        if v not in dark:
            rows.setdefault(y, Counter())[v] += 1
    fill_rows = {y: max(c, key=lambda v: c[v] * (_lum(pal, pk(v)) / 255.0) ** 2) for y, c in rows.items()}   # 밝은 색 가중(흰 글자 안 갈색 줄 방지)
    if not fill_rows:                                    # 한 색 글자(테두리 없음)
        fill_rows = {y: edge for y in {y for _, y in text}}
        edge = None
    return edge, fill_rows


def relabel(sp, c, text, rect=None, font=None, align='center', erase_to=None, pal=None, fill=None, ring=False, edge_c=None):
    """fill: None = 원본 줄별 색 / 'white' = 흰색 한 색 / 'grad' = 원본 채움 색을 평균 높이순으로 세로 그라데이션(위→아래)"""
    can, cov, x0, y0 = sp.canvas(c)
    H, W = len(can), len(can[0])
    pk = (lambda v: v) if sp.bpp == 8 else (lambda v, p=sp.cells[c][0]['pal']: p * 16 + v)
    can_orig = [r[:] for r in can]
    plate, area, tpx = analyze(can, rect, pal, pk, dark_plate=(erase_to == 'plate'))
    if erase_to == 'plate2':                             # 판 색 자동: 가장 흔한 색 + 바깥 테두리 색(화살표 버튼 — 화살표 쪽 테두리 지워짐 방지)
        nz_ = [(x, y) for y in range(H) for x in range(W) if can[y][x]]
        outer_ = Counter(can[y][x] for x, y in nz_ if any(not (0 <= x + dx < W and 0 <= y + dy < H) or can[y + dy][x + dx] == 0
                                                          for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))))
        erase_to = sorted({Counter(can[y][x] for x, y in nz_).most_common(1)[0][0]} | {v for v, n in outer_.items() if n >= 5})   # 바깥에 닿는 색 전부(테두리 + 그림자 — 튜토리얼 뒤로 그림자 깨짐)
    plate_list = erase_to if isinstance(erase_to, list) else None   # 판 색 목록(파란 화살표 버튼 두 색 등): 지운 자리는 같은 줄 가장 가까운 판 색으로
    if plate_list:
        plate = None
        # 테두리 색은 «바깥(투명)과 이어진 것»만 판으로 본다 — 글자 테두리가 같은 색 번호일 때(편집 버튼 찌꺼기)
        touch = {can[y][x] for y in range(H) for x in range(W) if can[y][x] in plate_list and
                 any(not (0 <= x + dx < W and 0 <= y + dy < H) or can[y + dy][x + dx] == 0 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
        inner_c = set(plate_list) if rect and len(plate_list) > 2 else (set(plate_list) - touch or {Counter(can[y][x] for y in range(H) for x in range(W) if can[y][x]).most_common(1)[0][0]})
        mainc = None                                     # 판 안쪽 색 = 바깥에 안 닿는 판 색(저장하고 뒤로: 테두리 진파랑·안쪽 밝은 파랑)
        seen_b = set()
        stack = [(x, y) for y in range(H) for x in range(W) if can[y][x] in plate_list and can[y][x] not in inner_c and
                 any(not (0 <= x + dx < W and 0 <= y + dy < H) or can[y + dy][x + dx] == 0 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
        while stack:
            x, y = stack.pop()
            if (x, y) in seen_b:
                continue
            seen_b.add((x, y))
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < W and 0 <= yy < H and (xx, yy) not in seen_b and can[yy][xx] == can[y][x]:
                    stack.append((xx, yy))
        is_plate = lambda x, y: can_orig[y][x] in inner_c or (x, y) in seen_b
        tpx = [(x, y) for x, y in tpx if not is_plate(x, y)]
        erase_to = None
    no_edge = erase_to == 'plate'                        # 어두운 판 위 글자(せんせき): 테두리 없이 채움만
    if no_edge:
        erase_to = None
    outline_only = erase_to == 'outline'                 # 받침 없이 글자 둘레 1 px 만 받침색 테두리(승·패 — 사용자 지정)
    if outline_only:
        plate = None
        area = rect if rect else (0, 0, W, H)            # 판으로 잡힌 안쪽만이 아니라 셀 전체를 지운다(판 가장자리 찌꺼기)
        ax0_, ay0_, ax1_, ay1_ = area
        tpx = [(x, y) for y in range(max(0, ay0_), min(H, ay1_)) for x in range(max(0, ax0_), min(W, ax1_)) if can[y][x]]
        erase_to = 0
    if erase_to == 'edge':                               # 받침 덩어리 셀엔 판이 없다(밝은 글자 색을 판으로 오인하지 않게)
        plate = None
        cov = [[cov[y][x] and can[y][x] != 0 for x in range(W)] for y in range(H)]   # 받침 모양 밖(투명)엔 그리지 않는다(번짐 — 실기 지적)
        ax0_, ay0_, ax1_, ay1_ = area
        tpx = [(x, y) for y in range(max(0, ay0_), min(H, ay1_)) for x in range(max(0, ax0_), min(W, ax1_)) if can[y][x]]
    assert tpx, '셀 %d 글자 화소 없음' % c
    pc = plate[0] if plate else None
    edge, fill_rows = roles(can, tpx, pc, pal, pk)
    if isinstance(edge_c, list):                         # [테두리색, 바깥 테두리색] 직접 지정(팝업 듀얼 로고: 흰 테두리 + 갈색 바깥)
        edge = edge_c[0]
    if outline_only and edge_c == 'common':            # 테두리색 = 셀에서 가장 흔한 색(잠시 기다려 주세요: 주황 판색 — 사용자 지정)
        edge = Counter(can[y][x] for x, y in tpx).most_common(1)[0][0]
    if no_edge:
        edge = None
    tx0 = min(x for x, _ in tpx); tx1 = max(x for x, _ in tpx) + 1
    ty0 = min(y for _, y in tpx); ty1 = max(y for _, y in tpx) + 1
    oh = ty1 - ty0
    dark_n = sum(1 for x, y in tpx if edge is not None and can[y][x] == edge)
    thick = 2 if edge is not None and dark_n >= 2 * (len(tpx) - dark_n) else 1   # 원본 테두리가 두꺼우면 2 px
    if outline_only:
        thick = 1
    if erase_to == 'edge':                               # 어두운 받침 덩어리 위 글자(勝·敗 등): 받침 모양을 살린다
        bg = edge
    else:
        bg = erase_to if erase_to is not None else (pc if pc is not None else 0)
    for (x, y) in tpx:
        can[y][x] = bg
    if plate_list:
        tset = set(tpx)                                  # 배치는 글자 영역 기준, 지우기는 셀 전체의 판 아닌 화소(가장자리 찌꺼기 — 재도전)
        for (x, y) in tpx + [(x, y) for y in range(H) for x in range(W)
                             if not rect and can[y][x] and not is_plate(x, y) and (x, y) not in tset]:
            fillable = lambda xx, yy: is_plate(xx, yy) and (xx, yy) not in seen_b   # 바깥 테두리색으로 메우지 않는다(편집 버튼 가로 줄 찌꺼기)
            rowc = Counter(can_orig[y][xx] for xx in range(W) if fillable(xx, y))
            if rect and rowc and len(plate_list) > 2:    # 영역 지정 + 종이색 여러 개(배너 종이): 그 줄의 가장 흔한 종이색 — 가까운 화소를 따르면 세로 줄무늬가 생긴다
                can[y][x] = rowc.most_common(1)[0][0]
                continue
            near = [(abs(xx - x), can_orig[y][xx]) for xx in range(W) if fillable(xx, y)]
            near += [(abs(yy - y) + 100, can_orig[yy][x]) for yy in range(H) if fillable(x, yy)]
            can[y][x] = min(near)[1] if near else 0
    if plate:                                            # 판 안쪽 경계(1 px)에 걸친 옛 글자 조각도 지운다
        bx0, by0, bx1, by1 = plate[1]
        erased = set(tpx)
        for _ in range(2):
            more = [(x, y) for y in range(by0 - 2, by1 + 1) for x in range(bx0 - 2, bx1 + 1)   # 판 색 테두리 상자 안(판 테두리 밖은 안 건드림)
                    if 0 <= x < W and 0 <= y < H and can[y][x] not in (0, pc)
                    and any((x + dx, y + dy) in erased for dx in (-1, 0, 1) for dy in (-1, 0, 1))]
            for (x, y) in more:
                can[y][x] = bg
                erased.add((x, y))
    ax0, ay0, ax1, ay1 = area
    avail_w = min(W, ax1) - max(0, ax0) - 2
    avail_h = min(H, ay1) - max(0, ay0)
    has_edge = edge is not None
    if bg == edge:
        thick = 1
    cands = [f for f in FONTS if f[2] + (2 if has_edge else 0) <= max(oh, 7) + 2] if not font else [f for f in FONTS if f[0] == font.rstrip('!') and (not font.endswith('!') or f[1] is titlegfx.NONE)]   # 'Galmuri9!' = 굵히지 않은 판
    if not cands:
        cands = [(font, titlegfx.NONE, 11)] if font else [FONTS[-1]]   # 목록 밖 글꼴(콘덴스드 등)은 지정했을 때만
    mask = None
    for t in ([text] + ([text.replace(' ', '')] if ' ' in text else [])):
        for fname, dil, fh in cands:
            m = titlegfx.bold_mask(t, _font(fname), 1, dil)
            if len(m[0]) + (2 if has_edge else 0) <= avail_w and len(m) + (2 if has_edge else 0) <= avail_h + 2:
                mask = m
                break
        if mask:
            break
    assert mask, '셀 %d %r 가 %d px 에 안 들어감' % (c, text, avail_w)
    mh, mw = len(mask), len(mask[0])
    e = (thick if mw + 2 * thick <= avail_w + 2 and mh + 2 * thick <= avail_h + 2 else 1) if has_edge else 0
    cx = (tx0 + tx1) // 2 if align == 'center' else None
    rmargin = int(align.split(':')[1]) if align.startswith('right:') else 0
    ox = cx - mw // 2 if align == 'center' else ((tx1 - mw - e - rmargin) if align.startswith('right') else (tx0 + e))
    ox = max(max(0, ax0) + e, min(ox, min(W, ax1) - mw - e))
    oy = (ty0 + ty1) // 2 - mh // 2
    oy = max(e, min(oy, H - mh - e))
    ink = [(ox + x, oy + y) for y in range(mh) for x in range(mw) if mask[y][x]]
    if erase_to == 'edge':                               # 받침 안쪽(가장자리 1 px 남김)에 통째로 들어가는 가장 큰 글꼴·가운데 자리
        blk = {(x, y) for y in range(H) for x in range(W) if cov[y][x]}
        inner = {(x, y) for (x, y) in blk if all((x + dx, y + dy) in blk for dx in (-1, 0, 1) for dy in (-1, 0, 1))}
        bx = (min(x for x, _ in blk) + max(x for x, _ in blk) + 1) / 2
        by = (min(y for _, y in blk) + max(y for _, y in blk) + 1) / 2
        best = None
        for t in ([text] + ([text.replace(' ', '')] if ' ' in text else [])):
            for fname, dil, fh in (cands + [f for f in FONTS if f not in cands and f[2] <= 11 and f[1] is titlegfx.NONE and 'Bold' not in f[0]] if font else FONTS):   # 지정 글꼴이 안 들어가면 더 작은 글꼴로
                m = titlegfx.bold_mask(t, _font(fname), 1, dil)
                h_, w_ = len(m), len(m[0])
                opts = []
                for oy_ in range(H - h_ + 1):
                    for ox_ in range(W - w_ + 1):
                        pts = [(ox_ + x, oy_ + y) for y in range(h_) for x in range(w_) if m[y][x]]
                        if all(p in inner for p in pts):
                            opts.append((abs(ox_ + w_ / 2 - bx) + abs(oy_ + h_ / 2 - by), pts))
                if opts:
                    best = min(opts)[1]
                    break
            if best:
                break
        assert best, '셀 %d %r 가 받침 안에 안 들어감' % (c, text)
        ink = best
        oy = min(y for _, y in ink); mh = max(y for _, y in ink) - oy + 1
        e = 0
    src_rows = sorted(fill_rows)

    if fill == 'hgrad':                                  # 가로 그라데이션: 원본 밝은 채움색을 평균 x 순으로(뺄 카드를 골라 줘: 청록→녹→노랑→연빨강)
        xs = {}
        for (x, y) in tpx:
            v = can_orig[y][x]
            if v not in (edge, pc) and _lum(pal, pk(v)) >= 170:   # 어두운 그림자색은 빼야 세로 줄무늬가 안 생긴다
                xs.setdefault(v, []).append(x)
        horder = sorted((v for v in xs if len(xs[v]) >= 8), key=lambda v: sum(xs[v]) / len(xs[v]))
        ix0 = min(x for x, _ in ink); ix1 = max(x for x, _ in ink) + 1
        hfill = lambda x: horder[min(len(horder) - 1, (x - ix0) * len(horder) // max(1, ix1 - ix0))]
        fill = None
        fill_hg = True
    else:
        fill_hg = False
    if fill == 'flat':                                   # 그라데이션 없이 원본 채움 중 가장 흔한 색 한 가지(무선 플레이·그림책 게임 — 사용자 지정)
        fc = Counter(v for r in fill_rows.values() for v in [r])
        inner_px = [(x, y) for x, y in tpx if all(0 <= x + dx < W and 0 <= y + dy < H and can_orig[y + dy][x + dx] != 0
                                                  for dx in (-1, 0, 1) for dy in (-1, 0, 1))]   # 바깥 테두리(투명에 닿는 화소)는 빼고
        fcnt = Counter(can_orig[y][x] for x, y in inner_px if can_orig[y][x] not in (edge, pc) and max(pal[pk(can_orig[y][x])]) - min(pal[pk(can_orig[y][x])]) >= 40)
        outer = Counter(can_orig[y][x] for x, y in tpx if any(not (0 <= x + dx < W and 0 <= y + dy < H) or can_orig[y + dy][x + dx] == 0
                                                          for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))))
        if outer and ring:                               # 바깥 테두리 색(두 겹 테두리)은 채움 후보에서 뺀다
            fcnt.pop(outer.most_common(1)[0][0], None)
        if not fcnt:
            fcnt = Counter(can_orig[y][x] for x, y in tpx if can_orig[y][x] not in (edge, pc))
        bright = [v for v, n in fcnt.most_common() if _lum(pal, pk(v)) >= 150]   # 밝은 주 채움색(가장자리 섞임색 말고)
        flat = bright[0] if bright else fcnt.most_common(1)[0][0]
        fill_at = lambda y: flat
    elif fill == 'white':                                  # 그라데이션 없이 흰색(사용자 지정: 뒤로·통산 성적·패스워드)
        span = range(len(pal)) if sp.bpp == 8 else range(16)
        wi = max((v for v in span if v and max(pal[pk(v)]) - min(pal[pk(v)]) < 24), key=lambda v: _lum(pal, pk(v)))
        fill_at = lambda y: wi
    elif fill in ('grad', 'gradb', 'grad3') or isinstance(fill, list) or str(fill).startswith('lum'):                                 # 원본 채움 색들을 평균 높이순으로 늘어놓고 새 글자 높이에 펼친다(중단·저장 중)
        ys = {}
        order = []
        for (x, y) in tpx:
            v = can_orig[y][x]
            if v != edge and v != pc and (edge is None or _lum(pal, pk(v)) > _lum(pal, pk(edge)) + 60):
                ys.setdefault(v, []).append(y)
        order = sorted((v for v in ys if len(ys[v]) >= 3 and max(pal[pk(v)]) - min(pal[pk(v)]) >= 40),
                       key=lambda v: sum(ys[v]) / len(ys[v]))
        if fill == 'grad3':                              # 3단: 글자 줄 위·가운데·아래 1/3 에서 가장 흔한 밝은 색(줄무늬 없는 세로 그라데이션 — 카드 덱)
            ty_ = sorted({y for _, y in tpx})
            thirds = [ty_[:len(ty_) // 3], ty_[len(ty_) // 3:2 * len(ty_) // 3], ty_[2 * len(ty_) // 3:]]
            order = []
            oc = Counter(can_orig[y][x] for x, y in tpx if any(not (0 <= x + dx < W and 0 <= y + dy < H) or can_orig[y + dy][x + dx] == 0
                                                               for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))))
            ringc = oc.most_common(1)[0][0] if oc else None   # 바깥 테두리색은 채움 후보에서 뺀다
            for part in thirds:
                cc = Counter(can_orig[y][x] for x, y in tpx if y in part and can_orig[y][x] not in (edge, pc) and _lum(pal, pk(can_orig[y][x])) >= 120
                             and max(pal[pk(can_orig[y][x])]) - min(pal[pk(can_orig[y][x])]) >= 40)
                cc.pop(ringc, None)
                if cc:
                    order.append(cc.most_common(1)[0][0])
        if fill == 'gradb':                              # 밝은 주 채움색만(가장자리 섞임색 제외) — 무선: 위 진한 주황 → 아래 연노랑
            order = sorted((v for v in ys if len(ys[v]) >= 8 and _lum(pal, pk(v)) >= 150), key=lambda v: sum(ys[v]) / len(ys[v]))
        if isinstance(fill, list) or str(fill).startswith('lum'):   # 색 목록을 직접(다른 셀 그라데이션 빌리기) / 'lum' = 밝은 색 위→어두운 색 아래
            if str(fill).startswith('lum'):
                order = sorted({can_orig[y][x] for x, y in tpx if can_orig[y][x] not in (edge, pc)
                                and max(pal[pk(can_orig[y][x])]) - min(pal[pk(can_orig[y][x])]) >= 40
                                and sum(1 for xx, yy in tpx if can_orig[yy][xx] == can_orig[y][x]) >= 3},
                               key=lambda v: _lum(pal, pk(v)) * (1 if str(fill).startswith('lumr') else -1))   # 'lumr' = 위 어두운 색 → 아래 밝은 색
                cn = Counter(can_orig[y][x] for x, y in tpx if can_orig[y][x] in order)
                dom = 'rgb'.index(fill.split(':')[1]) if ':' in fill else max(range(3), key=lambda i: pal[pk(cn.most_common(1)[0][0])][i])   # 'lum:g' = 초록 계열만
                order = [v for v in order if max(range(3), key=lambda i: pal[pk(v)][i]) == dom]
            else:
                order = fill
        # 흰 반짝임(무채색)은 빼고 색만 늘어놓는다
        fill_at = lambda y: order[min(len(order) - 1, max(0, (y - oy) * len(order) // max(1, mh)))]
    else:
      def fill_at(y):
          if not src_rows:
              return edge
          r = ty0 + (y - oy) * max(1, oh) // max(1, mh)
          best = min(src_rows, key=lambda s: abs(s - r))
          return fill_rows[best]
    if ring and has_edge:                                # 바깥 테두리 한 겹 더(원본 글자 모양 따라 두 겹 — 플레이어 정보)
        ro = edge_c[1] if isinstance(edge_c, list) else Counter(can_orig[y][x] for x, y in tpx
                     if any(0 <= x + dx < W and 0 <= y + dy < H and can_orig[y + dy][x + dx] == 0
                            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))).most_common(1)[0][0]
        for (x, y) in ink:
            for dy in range(-e - 1, e + 2):
                for dx in range(-e - 1, e + 2):
                    if abs(dx) == e + 1 and abs(dy) == e + 1:
                        continue
                    if 0 <= x + dx < W and 0 <= y + dy < H and cov[y + dy][x + dx]:
                        can[y + dy][x + dx] = ro
    if has_edge:
        for (x, y) in ink:
            for dy in range(-e, e + 1):
                for dx in range(-e, e + 1):
                    if e == 2 and abs(dx) == 2 and abs(dy) == 2:     # 모서리는 둥글게
                        continue
                    if 0 <= x + dx < W and 0 <= y + dy < H and cov[y + dy][x + dx]:
                        can[y + dy][x + dx] = edge
    for (x, y) in ink:
        if 0 <= x < W and 0 <= y < H and cov[y][x]:
            can[y][x] = hfill(x) if fill_hg else fill_at(y)
    objs = sp.cells[c]
    own = sp.owners()
    orig = [sp.obj_px(o) for o in objs]
    seen = Counter(t for o in objs for t in sp.tiles_of(o))
    rep = {k: [r[:] for r in orig[k]] for k, o in enumerate(objs) if not any(seen[t] > 1 for t in sp.tiles_of(o))}
    shared = {k for k, o in enumerate(objs) if set().union(*[own[t] for t in sp.tiles_of(o)]) - {c}}
    for y in range(H):                                   # 화소마다 맨 앞에 보이는 OBJ 에만(labelgfx 와 같은 규칙)
        for x in range(W):
            cands = [k for k, o in enumerate(objs)
                     if o['x'] - x0 <= x < o['x'] - x0 + o['w'] and o['y'] - y0 <= y < o['y'] - y0 + o['h']]
            if not cands:
                continue
            vis = [k for k in cands if orig[k][y - (objs[k]['y'] - y0)][x - (objs[k]['x'] - x0)]]
            k = vis[0] if vis else cands[0]
            if k not in rep:
                front = [j for j in cands if j in rep and j < k]
                k = front[0] if front else k
            if k in shared and not orig[k][y - (objs[k]['y'] - y0)][x - (objs[k]['x'] - x0)]:
                mine = [j for j in cands if j in rep and j not in shared]
                if mine:                                 # 여러 셀이 같이 쓰는 OBJ 의 빈 화소엔 쓰지 않는다(그림책 옆 찌꺼기 — 사용자 지적)
                    k = mine[0]
            if k in rep:
                rep[k][y - (objs[k]['y'] - y0)][x - (objs[k]['x'] - x0)] = can[y][x]
    for k, px in rep.items():
        if px == orig[k]:
            continue
        others = set().union(*[own[t] for t in sp.tiles_of(objs[k])]) - {c}
        key = lambda o: (o['tile'], o['w'], o['h'], o['raw'][1] & 0x3000 if 'raw' in o else 0)
        ts = set(sp.tiles_of(objs[k]))
        bad = [oc for oc in others for o in sp.cells[oc] if ts & set(sp.tiles_of(o)) and key(o) != key(objs[k])]
        assert not bad, '셀 %d 타일을 셀 %s 도 (다른 꼴로) 씀' % (c, sorted(set(bad)))   # 같은 OBJ 를 그대로 쓰는 셀(ワイヤレスプレイ 등)은 함께 바뀐다
        sp.put_obj(objs[k], px)


def ramp(sp, c, pal):
    """셀 c 의 글자 채움 색을 평균 높이순(위→아래)으로 — 다른 셀에 같은 그라데이션을 입힐 때"""
    can, cov, x0, y0 = sp.canvas(c)
    pk = (lambda v: v) if sp.bpp == 8 else (lambda v, p=sp.cells[c][0]['pal']: p * 16 + v)
    plate, area, tpx = analyze(can, None, pal, pk)
    edge, _ = roles(can, tpx, plate[0] if plate else None, pal, pk)
    ys = {}
    for (x, y) in tpx:
        v = can[y][x]
        if v != edge and _lum(pal, pk(v)) > _lum(pal, pk(edge)) + 60 and max(pal[pk(v)]) - min(pal[pk(v)]) >= 40:
            ys.setdefault(v, []).append(y)
    return sorted((v for v in ys if len(ys[v]) >= 3), key=lambda v: sum(ys[v]) / len(ys[v]))


def rewrap(sp, c, text, font='Galmuri9', fill='grad', pal=None, pad=2):
    """글자 모양을 따라 두른 판(せんせき: 어두운 판 + 흰 바깥 테두리)을 새 글자에 맞춰 통째로 다시 그린다.
    판 = 새 글자를 pad px 부풀린 모양(모서리 둥글게), 바깥 테두리 = 그 둘레 1 px. 원본 판 모양(옛 글자 요철)은 남기지 않는다(사용자 지적)."""
    can, cov, x0, y0 = sp.canvas(c)
    H, W = len(can), len(can[0])
    pk = (lambda v: v) if sp.bpp == 8 else (lambda v, p=sp.cells[c][0]['pal']: p * 16 + v)
    nz = [(x, y) for y in range(H) for x in range(W) if can[y][x]]
    cnt = Counter(can[y][x] for x, y in nz)
    ringc = Counter(can[y][x] for x, y in nz if any(not (0 <= x + dx < W and 0 <= y + dy < H) or can[y + dy][x + dx] == 0
                                                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))).most_common(1)[0][0]
    platec = max((v for v in cnt if v != ringc), key=lambda v: cnt[v])
    ys = {}
    for x, y in nz:
        v = can[y][x]
        if v not in (ringc, platec) and max(pal[pk(v)]) - min(pal[pk(v)]) >= 40:
            ys.setdefault(v, []).append(y)
    order = sorted((v for v in ys if len(ys[v]) >= 3), key=lambda v: sum(ys[v]) / len(ys[v]))
    cands = [f for f in FONTS if f[0] == font.rstrip('!') and (not font.endswith('!') or f[1] is titlegfx.NONE)]
    m = None
    for fname, dil, fh in cands:
        ls = [titlegfx.bold_mask(t, _font(fname), 1, dil) for t in text.split(chr(10))]   # 여러 줄: 가운데 맞춰 1 px 간격으로 쌓는다
        mw_ = max(len(l[0]) for l in ls)
        mm = []
        for k, l in enumerate(ls):
            if k:
                mm.append([0] * mw_)
            lp = (mw_ - len(l[0])) // 2
            mm += [[0] * lp + r + [0] * (mw_ - lp - len(r)) for r in l]
        if len(mm[0]) + 2 * (pad + 1) <= W and len(mm) + 2 * (pad + 1) <= H:
            m = mm
            break
    assert m, '셀 %d %r 가 안 들어감' % (c, text)
    mh, mw = len(m), len(m[0])
    bx0 = min(x for x, _ in nz); bx1 = max(x for x, _ in nz) + 1
    by0 = min(y for _, y in nz); by1 = max(y for _, y in nz) + 1
    ox = (bx0 + bx1) // 2 - mw // 2
    oy = (by0 + by1) // 2 - mh // 2
    ink = {(ox + x, oy + y) for y in range(mh) for x in range(mw) if m[y][x]}
    plate = {(x + dx, y + dy) for x, y in ink for dx in range(-pad, pad + 1) for dy in range(-pad, pad + 1)
             if abs(dx) + abs(dy) <= pad + 1}
    ring = {(x + dx, y + dy) for x, y in plate for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - plate
    new = [[0] * W for _ in range(H)]
    for x, y in ring | plate | ink:
        assert 0 <= x < W and 0 <= y < H and cov[y][x], '셀 %d 새 판이 OBJ 밖(%d,%d)' % (c, x, y)
    for x, y in ring:
        new[y][x] = ringc
    for x, y in plate:
        new[y][x] = platec
    for x, y in ink:
        new[y][x] = order[min(len(order) - 1, (y - oy) * len(order) // mh)] if fill == 'grad' else fill
    objs = sp.cells[c]
    own = sp.owners()
    seen = Counter(t for o in objs for t in sp.tiles_of(o))
    for o in objs:
        assert not any(seen[t] > 1 for t in sp.tiles_of(o)), '셀 %d 안에서 반복 타일' % c
        assert not (set().union(*[own[t] for t in sp.tiles_of(o)]) - {c}), '셀 %d 타일을 다른 셀도 씀' % c
    for o in reversed(objs):                             # 셀 전체를 새로 쓰므로 OBJ 마다 자기 칸을 통째로
        px = [[new[o['y'] - y0 + y][o['x'] - x0 + x] for x in range(o['w'])] for y in range(o['h'])]
        sp.put_obj(o, px)



def relayout(ncer_b, ncgr_b, spec, pal):
    """여러 셀이 조각을 나눠 쓰는 글자 셀(PUB_stUI: 「成功!」「フェイズ」 등)을 새로 배치한다.
    spec = {셀: {'text': '어택 |성공!\n…', 'font', 'edge'(px), 'align'}}.  '|' = 조각 경계(같은 조각은 셀끼리 타일을 나눠 쓴다 —
    원본처럼; 경계는 띄어쓰기 뒤에 둔다: 테두리가 옆 글자 위로 겹치지 않게), '\n' = 줄.
    대상 셀들만 쓰던 타일을 빈 칸으로 모아 조각마다 OBJ(32/16/8 × 16/8)를 채운다. 채움 = 원본 밝은 주색 한 색, 테두리 = 원본 가장 흔한 어두운 색."""
    sp = Sprites(ncer_b, ncgr_b)
    orig = Sprites(ncer_b, ncgr_b)
    own = sp.owners()
    targets = set(spec)
    free = sorted(t for t, cs in own.items() if cs <= targets)
    per_unit = sp.unit // sp.tsz
    for t in free:
        sp.data[t * sp.tsz:(t + 1) * sp.tsz] = bytes(sp.tsz)
    freeset = set(free)

    def alloc(n):
        for t in sorted(freeset):
            if t % per_unit == 0 and all((t + k) in freeset for k in range(n)):
                for k in range(n):
                    freeset.discard(t + k)
                return t // per_unit
        raise AssertionError('타일 빈 칸 부족(%d 타일 필요, 남은 %d)' % (n, len(freeset)))

    cache = {}                                           # (조각, 높이, 색, 글꼴, 테두리) → (OBJ 목록(상대 좌표), 잉크 폭)

    def piece(text, bh, fillc, edge, e, font, p):
        key = (text, bh, fillc, edge, e, font, p)
        if key in cache:
            return cache[key]
        cand = [f for f in FONTS if f[0] == font.rstrip('!') and (not font.endswith('!') or f[1] is titlegfx.NONE)]
        m = None
        for fname, dil, fh in cand + [f for f in FONTS if f not in cand and f[2] < cand[0][2]]:
            mm = titlegfx.bold_mask(text, _font(fname), 1, dil)
            if len(mm) + 2 * e <= bh + 2:
                m = mm
                break
        assert m, '%r 줄 높이 %d 에 안 들어감' % (text, bh)
        mh, mw = len(m), len(m[0])
        W = (mw + 2 * e + 7) // 8 * 8
        H = (mh + 2 * e + 7) // 8 * 8
        img = [[0] * W for _ in range(H)]
        pad = (H - mh - 2 * e) // 2                      # 조각 칸(8 배수) 안 세로 가운데(선공·후공이 위로 붙어 보임 — 사용자)
        ink = [(e + x, e + pad + y) for y in range(mh) for x in range(mw) if m[y][x]]
        if e:
            for x, y in ink:
                for dy in range(-e, e + 1):
                    for dx in range(-e, e + 1):
                        if e == 2 and abs(dx) == 2 and abs(dy) == 2:
                            continue
                        if 0 <= x + dx < W and 0 <= y + dy < H:
                            img[y + dy][x + dx] = edge
        for x, y in ink:
            img[y][x] = fillc
        objs = []
        for sy in range(0, H, 16):
            h = 16 if H - sy >= 16 else 8
            sx = 0
            while sx < W:
                w = 32 if W - sx >= 32 else (16 if W - sx >= 16 else 8)
                px = [r[sx:sx + w] for r in img[sy:sy + h]]
                if any(any(r) for r in px):
                    tile = alloc(w * h // 64)
                    sp.put_obj(dict(tile=tile, w=w, h=h), px)
                    objs.append(dict(dx=sx, dy=sy, w=w, h=h, tile=tile))
                sx += w
        cache[key] = (objs, mw, mh, pad)
        return cache[key]

    new_cells = [[dict(o, x=o['x'] & 0x1ff, y=o['y'] & 0xff) for o in objs] for objs in sp.cells]
    for c in sorted(spec):
        s = spec[c]
        objs = sp.cells[c]
        can, cov, x0, y0 = orig.canvas(c)
        H0, W0 = len(can), len(can[0])
        p = objs[0]['pal']
        pk = (lambda v: v) if sp.bpp == 8 else (lambda v, p=p: p * 16 + v)
        cnt = Counter(v for r in can for v in r if v)
        darks = [v for v in cnt if _lum(pal, pk(v)) < 60]
        edge = max(darks, key=lambda v: cnt[v]) if darks else None
        brights = [v for v in cnt if _lum(pal, pk(v)) >= 150]
        fillc = s.get('fill') or (max(brights, key=lambda v: cnt[v]) if brights else max(cnt, key=lambda v: cnt[v]))
        e = s.get('edge', 2 if edge is not None else 0)
        font = s.get('font', 'Galmuri11')
        lines = s['text'].split('\n')
        rows = [y for y in range(H0) if any(can[y])]
        bands = []
        for y in rows:
            if bands and y == bands[-1][1] + 1:
                bands[-1][1] = y
            else:
                bands.append([y, y])
        if len(lines) == 1:
            bands = [[rows[0], rows[-1]]]
        assert len(bands) == len(lines), '셀 %d 줄 수 %d ≠ 원본 %d' % (c, len(lines), len(bands))
        tmpl = objs[0]
        raw = (tmpl['raw'][0], tmpl['raw'][1] & ~0x3000, tmpl['raw'][2])
        no = []
        for ln, (b0, b1) in zip(lines, bands):
            bh = b1 - b0 + 1
            parts = [piece(t, bh, fillc, edge, e, font, p) for t in ln.split('|')]
            total = sum(p_[1] for p_ in parts) + (len(parts) - 1) + 2 * e
            mh = max(p_[2] for p_ in parts)
            pad = parts[0][3]
            lx = (x0 + W0 // 2 - total // 2) if s.get('align', 'center') == 'center' else x0
            ly = y0 + (b0 + b1 + 1) // 2 - (mh + 2 * e) // 2
            ly = (max(y0, min(ly, y0 + H0 - mh - 2 * e)) if H0 >= mh + 2 * e else ly) - pad
            cx = lx
            for pobjs, mw, _, _ in parts:
                for o in pobjs:
                    no.append(dict(x=(cx + o['dx']) & 0x1ff, y=(ly + o['dy']) & 0xff, w=o['w'], h=o['h'], tile=o['tile'], pal=p, raw=raw))
                cx += mw + 1
        new_cells[c] = no
    return titletext.ncer_write(ncer_b, new_cells), sp.result()


def glyph_cell(sp, c, text, pal, font='Galmuri7', fill=None):
    """글자 한 자짜리 좁은 셀(대전 화면 ミ·ス: 8×16 / 8×8)에 원본 칸 크기 그대로 한 글자.
    채움 = 원본 밝은 주색(또는 fill='white'), 테두리 = 원본 가장 어두운 색 1 px — 칸 밖으로 나가는 테두리는 잘린다."""
    can, cov, x0, y0 = sp.canvas(c)
    H, W = len(can), len(can[0])
    pk = (lambda v: v) if sp.bpp == 8 else (lambda v, p=sp.cells[c][0]['pal']: p * 16 + v)
    cnt = Counter(v for r in can for v in r if v)
    edge = min(cnt, key=lambda v: _lum(pal, pk(v))) if len(cnt) > 1 else None   # 한 색 글자(이름 칸)는 테두리 없음
    if fill == 'white':
        fc = max(cnt, key=lambda v: _lum(pal, pk(v)))
    else:
        fc = max((v for v in cnt if v != edge or len(cnt) == 1), key=lambda v: cnt[v] * (1 + (max(pal[pk(v)]) - min(pal[pk(v)])) / 64))
    ys = [y for y in range(H) if any(can[y])]
    m = titlegfx.bold_mask(text, _font(font), 1, titlegfx.NONE)
    mh, mw = len(m), len(m[0])
    ox = (W - mw) // 2
    oy = (min(ys) + max(ys) + 1) // 2 - mh // 2
    oy = max(0, min(oy, H - mh))
    new = [[0] * W for _ in range(H)]
    ink = [(ox + x, oy + y) for y in range(mh) for x in range(mw) if m[y][x]]
    for x, y in (ink if edge is not None else []):                   # 8 줄짜리 이름 칸은 테두리 없이(테두리가 글자를 덮어 뭉개짐)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if 0 <= x + dx < W and 0 <= y + dy < H:
                    new[y + dy][x + dx] = edge
    for x, y in ink:
        new[y][x] = fc
    for o in sp.cells[c]:
        sp.put_obj(o, [[new[o['y'] - y0 + y][o['x'] - x0 + x] for x in range(o['w'])] for y in range(o['h'])])


def rewrap_seg(sp, c, text, pal, seg=None, font='Galmuri11', fill='hgrad', pad=2, gap=1):
    """셀의 가로 구간 seg=(x0,x1) 만 비우고 새 글자 모양대로 어두운 판 + 바깥 테두리를 다시 두른다(그림책 부제·제목).
    판색 = 구간의 가장 흔한 어두운 색, 테두리 = 투명에 닿는 가장 흔한 색, 채움 = 원본 밝은 글자색을 평균 x 순(가로 그라데이션) 또는 'white'.
    '\n' = 줄바꿈(가운데 맞춰 gap px 간격)."""
    can, cov, x0, y0 = sp.canvas(c)
    H, W = len(can), len(can[0])
    sx0, sx1 = seg or (0, W)
    pk = (lambda v: v) if sp.bpp == 8 else (lambda v, p=sp.cells[c][0]['pal']: p * 16 + v)
    pts = [(x, y) for y in range(H) for x in range(sx0, sx1) if can[y][x]]
    cnt = Counter(can[y][x] for x, y in pts)
    ringc = Counter(can[y][x] for x, y in pts if any(not (0 <= x + dx < W and 0 <= y + dy < H) or can[y + dy][x + dx] == 0
                                                     for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))).most_common(1)[0][0]
    platec = max((v for v in cnt if v != ringc and _lum(pal, pk(v)) < 90), key=lambda v: cnt[v])
    xs = {}
    for x, y in pts:
        v = can[y][x]
        if v not in (ringc, platec) and _lum(pal, pk(v)) >= 150 and max(pal[pk(v)]) - min(pal[pk(v)]) >= 30:
            xs.setdefault(v, []).append(x)
    horder = sorted((v for v in xs if len(xs[v]) >= 4), key=lambda v: sum(xs[v]) / len(xs[v]))
    if fill == 'white':
        horder = [max(cnt, key=lambda v: _lum(pal, pk(v)))]
    def build_mask(t, f):
        ls = [titlegfx.bold_mask(u, _font(f), 1, titlegfx.NONE) for u in t.split(chr(10))]
        w = max(len(l[0]) for l in ls)
        mm = []
        for k, l in enumerate(ls):
            if k:
                mm += [[0] * w for _ in range(gap)]
            lp = (w - len(l[0])) // 2
            mm += [[0] * lp + r + [0] * (w - lp - len(r)) for r in l]
        return mm
    m = None
    # 안 들어가면: 지정 글꼴 → 콘덴스드 → 갈무리9 → (띄어쓰기 삭제) 순, 판 여백도 2 → 1 px
    for t in [text] + ([text.replace(' ', '')] if ' ' in text else []):
        for f in [font] + [g for g in ('Galmuri11-Condensed', 'Galmuri9') if g != font]:
            for pd in (pad, 1):
                mm = build_mask(t, f)
                if len(mm[0]) + 2 * (pd + 1) <= sx1 - sx0 and len(mm) + 2 * (pd + 1) <= H:
                    m, pad = mm, pd
                    break
            if m:
                break
        if m:
            break
    assert m, '셀 %d %r 가 구간 %d×%d 에 안 들어감' % (c, text, sx1 - sx0, H)
    mh, mw = len(m), len(m[0])
    ox = (sx0 + sx1) // 2 - mw // 2
    oy = H // 2 - mh // 2
    ink = {(ox + x, oy + y) for y in range(mh) for x in range(mw) if m[y][x]}
    plate = {(x + dx, y + dy) for x, y in ink for dx in range(-pad, pad + 1) for dy in range(-pad, pad + 1) if abs(dx) + abs(dy) <= pad + 1}
    for y in {y for _, y in plate}:                       # 낱말 사이 빈틈(8 px 이하)은 메워 한 줄 판으로(원본처럼 이어진 판)
        row = sorted(x for x, yy in plate if yy == y)
        for xa, xb in zip(row, row[1:]):
            if 1 < xb - xa <= 9:
                plate |= {(x, y) for x in range(xa, xb)}
    for x in {x for x, _ in plate}:                       # 세로로도 메운다(판 안에 테두리색 줄이 끼는 것 — 까만 초코보)
        col = [y for xx, y in plate if xx == x]
        plate |= {(x, y) for y in range(min(col), max(col) + 1)}
    ring = {(x + dx, y + dy) for x, y in plate for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - plate
    for y in range(H):
        for x in range(sx0, sx1):
            can[y][x] = 0
    for x, y in ring:
        if sx0 <= x < sx1:
            can[y][x] = ringc
    for x, y in plate:
        can[y][x] = platec
    ix0 = min(x for x, _ in ink); ix1 = max(x for x, _ in ink) + 1
    for x, y in ink:
        can[y][x] = horder[min(len(horder) - 1, (x - ix0) * len(horder) // max(1, ix1 - ix0))]
    objs = sp.cells[c]
    own = sp.owners()
    for o in objs:
        if not (o['x'] - x0 < sx1 and o['x'] - x0 + o['w'] > sx0):
            continue
        assert not (set().union(*[own[t] for t in sp.tiles_of(o)]) - {c}), '셀 %d 타일을 다른 셀도 씀' % c
        sp.put_obj(o, [[can[o['y'] - y0 + y][o['x'] - x0 + x] for x in range(o['w'])] for y in range(o['h'])])


def ttf_cell(sp, c, text, pal, font='C:/claude/utils/font/logo/BlackHanSans.ttf', order='lumr', margin=1):
    """칸을 꽉 채우는 큰 제목(볼그 배틀 등): 윤곽 글꼴을 칸 높이에 맞춰 크게(섞임색 없이) 그린다.
    바깥 테두리 = 원본에서 투명에 닿는 색, 안쪽 테두리 = 원본 가장 어두운 색, 채움 = 원본 밝은 색을 밝기순 세로 그라데이션
    ('lumr' = 위 어두운 색 → 아래 밝은 색, 'lum' = 반대)."""
    from PIL import Image, ImageDraw, ImageFont
    can, cov, x0, y0 = sp.canvas(c)
    H, W = len(can), len(can[0])
    pk = (lambda v: v) if sp.bpp == 8 else (lambda v, p=sp.cells[c][0]['pal']: p * 16 + v)
    pts = [(x, y) for y in range(H) for x in range(W) if can[y][x]]
    cnt = Counter(can[y][x] for x, y in pts)
    ringc = Counter(can[y][x] for x, y in pts if any(not (0 <= x + dx < W and 0 <= y + dy < H) or can[y + dy][x + dx] == 0
                                                     for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))).most_common(1)[0][0]
    edge = min((v for v in cnt if v != ringc), key=lambda v: _lum(pal, pk(v)))
    ramp = sorted((v for v in cnt if v not in (ringc, edge) and cnt[v] >= 6 and _lum(pal, pk(v)) >= 90
                   and max(pal[pk(v)]) - min(pal[pk(v)]) >= 40), key=lambda v: _lum(pal, pk(v)))
    if order == 'lum':
        ramp = ramp[::-1]
    size = H
    while True:
        f = ImageFont.truetype(font, size)
        im = Image.new('L', (W * 2, H * 2))
        dr = ImageDraw.Draw(im)
        dr.fontmode = '1'
        bb = dr.textbbox((0, 0), text, font=f, stroke_width=3)
        if bb[3] - bb[1] <= H - 2 * margin and bb[2] - bb[0] <= W - 2 * margin:
            break
        size -= 1
    ox, oy = (W - (bb[2] - bb[0])) // 2 - bb[0], (H - (bb[3] - bb[1])) // 2 - bb[1]
    layers = []
    for sw in (3, 2, 0):
        im = Image.new('L', (W, H))
        dr = ImageDraw.Draw(im)
        dr.fontmode = '1'
        dr.text((ox, oy), text, font=f, fill=255, stroke_width=sw, stroke_fill=255)
        layers.append(im.load())
    ys = [y for y in range(H) for x in range(W) if layers[2][x, y]]
    t0, t1 = min(ys), max(ys) + 1
    new = [[0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if layers[2][x, y]:
                new[y][x] = ramp[min(len(ramp) - 1, (y - t0) * len(ramp) // (t1 - t0))]
            elif layers[1][x, y]:
                new[y][x] = edge
            elif layers[0][x, y]:
                new[y][x] = ringc
    own = sp.owners()
    for o in sp.cells[c]:
        assert not (set().union(*[own[t] for t in sp.tiles_of(o)]) - {c}), '셀 %d 타일을 다른 셀도 씀' % c
        sp.put_obj(o, [[new[o['y'] - y0 + y][o['x'] - x0 + x] for x in range(o['w'])] for y in range(o['h'])])
