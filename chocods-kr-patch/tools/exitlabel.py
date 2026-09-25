# -*- coding: utf-8 -*-
r"""필드 출구 표시(3D 필드 화면 가장자리의 「フィールドマップ ▷」 등) 한글판.

  FLD/OBJ/CICON.FBC   NCER + NCGR(4bpp 1D 타일, 매핑 0x200010 → 단위 128 B) — 필드 맵·던전·홀·스텔라 목장·상업구·광산구
  FLD/SWSPR/MFRAME.FBC NCER + NCBR(4bpp 선형, 단위 32 B)                     — 스텔라 목장·시간을 잊는 마을·시간을 새기는 마을

원본 꼴: 흰 글자(색 1) + 8방향 1 px 테두리(색 15), 그림자 없음, 글자 10 행.
라벨 글자 타일은 라벨마다 한 벌이고 깜빡임 3장·화살표 방향 변형이 같은 타일을 쓴다 → 라벨 글자 단위만 새로 배치
(원본 라벨 글자 단위 범위 안, 파일 크기 불변). 화살표 오브젝트는 그대로.
정렬: 화살표가 글자 오른쪽이면 글자 오른쪽 끝, 왼쪽이면 왼쪽 끝, 위·아래면 가운데를 원본 잉크 자리에 맞춘다.
마을 이름 둘은 1,280 B 안에 들게 갈무리11 콘덴스드를 전진폭 7·공백 2 로 붙여 쓴다(사용자 결정·미리보기 승인 2026-09-25).
"""
import bdf
import ncer
import titletext

CONDENSED = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11-Condensed.bdf'
WHITE, BLACK = 1, 15

# 경로 → (단위 B, 선형?, 라벨 글자 단위 범위[시작, 끝), {라벨: (한글, 글꼴, [셀…])})
FILES = {
    'romdata/FLD/OBJ/CICON.FBC.z': (128, False, (18, 37), {
        'field': ('필드 맵', 'g9', list(range(18, 30))),
        'dungeon': ('던전', 'g9', [30, 31, 32]),
        'hall': ('홀', 'g9', [33, 34, 35]),                  # 広間(사용자 결정)
        'stella': ('스텔라 목장', 'g9', [36, 37, 38]),
        'shop': ('상업구', 'g9', [39, 40, 41]),
        'mine': ('광산구', 'g9', [42, 43, 44]),
    }),
    'romdata/FLD/SWSPR/MFRAME.FBC.z': (32, True, (79, 119), {
        'stella': ('스텔라 목장', 'cond', [14, 15, 16]),
        'town1': ('시간을 잊는 마을', 'cond', [17, 18, 19]),
        'town2': ('시간을 새기는 마을', 'cond', [20, 21, 22]),
    }),
}


def text_mask(text, font, kind):
    """→ 글자 잉크 0/1 행 목록"""
    if kind == 'g9':
        line = titletext.render_line(font, [('W', text)])
        return [[1 if v else 0 for v in r] for r in line]
    G, asc = font
    rows = [[] for _ in range(11)]
    for ch in text:
        if ch == ' ':
            for r in rows:
                r += [0] * 2
            continue
        arr, _ = bdf.render(G, asc, ord(ch), 7, 11, 11)
        for y in range(11):
            rows[y] += arr[y]
    return rows


def outline(mask):
    """1 px 테두리 여백을 둔 색번호 판(흰 글자 + 검정 8방향 테두리)"""
    h, w = len(mask) + 2, len(mask[0]) + 2
    can = [[0] * w for _ in range(h)]
    for y, r in enumerate(mask):
        for x, v in enumerate(r):
            if v:
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        can[y + 1 + dy][x + 1 + dx] = BLACK
    for y, r in enumerate(mask):
        for x, v in enumerate(r):
            if v:
                can[y + 1][x + 1] = WHITE
    ys = [y for y, r in enumerate(can) if any(r)]
    xs = [x for r in can for x, v in enumerate(r) if v]
    return [r[min(xs):max(xs) + 1] for r in can[min(ys):max(ys) + 1]]


def pieces(W):
    """폭 W 를 32/16/8 조각으로(8 배수로 올림)"""
    out, left = [], (W + 7) // 8 * 8
    while left:
        w = 32 if left >= 32 else (16 if left >= 16 else 8)
        out.append(w)
        left -= w
    return out


def build(ncer_b, ngr_b, unit, linear, span, labels, fonts):
    cells = ncer.cells(ncer_b)
    o, sz = ncer.ncgr_data(ngr_b)
    data = bytearray(ngr_b[o:o + sz])
    lo, hi = span
    in_span = lambda ob: lo <= ob['tile'] < hi

    def px_of(ob):
        if linear:
            return ncer.obj_pixels_bitmap(data, ob, unit)
        d = dict(ob); d['tile'] = ob['tile'] * unit // 32
        return ncer.obj_pixels(data, d)

    def put(ob, px):
        if linear:
            ncer.put_obj_bitmap(data, ob, px, unit)
        else:
            d = dict(ob); d['tile'] = ob['tile'] * unit // 32
            ncer.put_obj(data, d, px)

    # 원본 잉크 자리(셀별): 글자 오브젝트들의 잉크 x 범위와 맨 위 y
    ink = {}
    for key, (text, fk, cs) in labels.items():
        for c in cs:
            xs, ys = [], []
            for ob in cells[c]:
                if not in_span(ob):
                    continue
                px = px_of(ob)
                for y in range(ob['h']):
                    for x in range(ob['w']):
                        if px[y][x]:
                            xs.append(ob['x'] + x); ys.append(ob['y'] + y)
            arrow = [ob for ob in cells[c] if not in_span(ob)]
            ax = arrow[0]['x'] + arrow[0]['w'] / 2 if arrow else 0
            ink[c] = (min(xs), max(xs), min(ys), ax)

    for u in range(lo, hi):                                   # 라벨 글자 단위 비우기
        data[u * unit:(u + 1) * unit] = bytes(unit)
    nxt = lo
    new = [list(objs) for objs in cells]
    for key, (text, fk, cs) in labels.items():
        img = outline(text_mask(text, fonts[fk], fk))
        W, H = len(img[0]), len(img)
        assert H <= 16, (key, H)
        ws = pieces(W)
        tiles = []
        for w in ws:
            need = (w * 16 // 2 + unit - 1) // unit
            tiles.append(nxt)
            nxt += need
        assert nxt <= hi, '%s: 단위 %d > %d' % (key, nxt, hi)
        Wp = sum(ws)
        # 조각에 그림 쓰기(판 = 폭 Wp × 16, 잉크는 판 왼쪽 위부터)
        can = [[0] * Wp for _ in range(16)]
        for y in range(H):
            for x in range(W):
                can[y][x] = img[y][x]
        sx = 0
        for w, t in zip(ws, tiles):
            put(dict(tile=t, w=w, h=16), [r[sx:sx + w] for r in can])
            sx += w
        for c in cs:
            x0, x1, y0, ax = ink[c]
            tmpl = next(ob for ob in cells[c] if in_span(ob))
            if ax > x1:                    # 화살표가 오른쪽 → 오른쪽 끝 맞춤
                left = x1 + 1 - W
            elif ax < x0:                  # 화살표가 왼쪽 → 왼쪽 끝 맞춤
                left = x0
            else:                          # 위·아래 → 가운데
                left = (x0 + x1 + 1 - W) // 2
            objs = [ob for ob in cells[c] if not in_span(ob)]
            sx = 0
            for w, t in zip(ws, tiles):
                objs.append(dict(x=left + sx, y=y0, w=w, h=16, tile=t, pal=tmpl['pal'], raw=tmpl['raw']))
                sx += w
            new[c] = objs
    return titletext.ncer_write(ncer_b, new), ngr_b[:o] + bytes(data) + ngr_b[o + sz:], nxt - lo, hi - lo


def fonts_for(dsr_bytes):
    return {'g9': titletext.Font(dsr_bytes), 'cond': bdf.load(CONDENSED)}
