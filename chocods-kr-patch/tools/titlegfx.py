# -*- coding: utf-8 -*-
r"""타이틀 메뉴 그림(UI/TM/ui_title.FBC: NCER 59셀 + NCBR 4bpp 선형, 단위 32 B) 한글판.

바꾸는 셀
  22‥27  第一章‥第六章 배지 40×24 — 굵은 글자(2 px 획 + 1 px 테두리), 위아래 장식 줄(색 5, 6장은 4)은 원본 유지.
          → 셀마다 자기 비트맵만 쓴다: 원래 OBJ 배치 그대로 제자리에 다시 그림.
  28     ノーマル 32×16 — 채움 1 · 테두리 11(B)
  29     ハード 32×16 — 줄마다 다른 색 막대(2‥9) 위에 글자 10(A)
  35‥45  세이브 위치 이름 + 층 「F」(OBJ 단위 332, 그대로) — 1 px 게임 글꼴, 색 1, x=79 에 오른쪽 맞춤
  46     フィールド — x=87 에 오른쪽 맞춤
          → 이름끼리 「の守護者」·「の記憶」 조각을 나눠 쓰므로 배치를 새로 짜서, 남는 단위(다른 셀이 안 쓰는 곳)에 넣는다.
굵은 글자 = 갈무리 BDF 글리프를 오른쪽·아래로 1 px 부풀려 2 px 획을 만들고 8방향 테두리.
"""
from collections import Counter
import bdf
import ncer
import titletext

UNIT = 32
HORIZ = ((0, 0), (0, 1))
NONE = ((0, 0),)
FONT_DIR = 'C:/claude/utils/font/Galmuri-v2.40.3/'

CHAPTER = {22: '제1장', 23: '제2장', 24: '제3장', 25: '제4장', 26: '제5장', 27: '제6장'}
NAMES = {35: '불의 수호자', 36: '물의 수호자', 37: '빛의 수호자', 38: '어둠의 수호자', 39: '초코보의 추억',
         40: '고대 유적', 41: '게일의 기억', 42: '시드의 기억', 43: '프레이아의 기억', 44: '메아의 기억',
         45: '시로마의 기억', 46: '필드'}
NAME_RIGHT = {46: 88}
# 파일 선택 버튼(주황·회색 두 벌): 글자 OBJ = 셀의 (32,0) 32×16, 흰 글자(2) — 버튼 가운데 x 48
BUTTONS = {47: '예', 48: '예', 49: '아니요', 50: '아니요', 51: '노멀', 52: '노멀', 53: '하드', 54: '하드',
           55: '계속', 56: '계속', 57: '지우기', 58: '지우기'}
# 파일 탭: 아이콘 오른쪽 x 21‥77, y 2‥17 — 채움·테두리 색, 지울 색, 바탕 색
TABS = {30: ('세이브 모드', 10, 2, {10, 2}, 6), 31: ('중단 모드', 10, 2, {10, 2}, 6), 32: ('재개됨', 9, 1, {9, 1, 10}, 11)}                  # 기본 80(= 마지막 잉크 x 79 + 1)


def bold_mask(text, font, gap=0, dil=((0, 0), (0, 1), (1, 0), (1, 1))):
    """→ (fill 마스크[y][x] bool) 2 px 획. 글자 사이 gap px(테두리는 서로 겹친다) — gap 이 목록이면 글자 사이마다."""
    G, asc = font
    gaps = gap if isinstance(gap, (list, tuple)) else [gap] * len(text)
    glyphs = []
    for ch in text:
        if ch == ' ':                                    # 띄어쓰기 = 빈 4 px
            glyphs.append(None)
            continue
        g = G[ord(ch)]
        w, h, xo, yo, adv, rows = g
        cw = max(adv, xo + w) + 2
        arr, _ = bdf.render(G, asc, ord(ch), cw, asc + 3, asc)
        xs = [x for r in arr for x, v in enumerate(r) if v]
        x0, x1 = min(xs), max(xs)
        arr = [r[x0:x1 + 1] + [0] for r in arr] + [[0] * (x1 - x0 + 2)]
        big = [[0] * len(arr[0]) for _ in arr]
        for y, r in enumerate(arr):
            for x, v in enumerate(r):
                if v:
                    for dy, dx in dil:
                        big[y + dy][x + dx] = 1
        glyphs.append(big)
    H = len(next(g for g in glyphs if g))
    out = [[] for _ in range(H)]
    for k, gph in enumerate(glyphs):
        for y in range(H):
            out[y] += (gph[y] if gph else [0] * 4) + ([0] * gaps[k] if k + 1 < len(glyphs) else [])
    ys = [y for y, r in enumerate(out) if any(r)]
    return out[min(ys):max(ys) + 1]


def outlined(mask):
    """마스크에 1 px 테두리 여백을 더한 역할 판: 0 없음 · 1 채움 · 2 테두리"""
    h, w = len(mask) + 2, len(mask[0]) + 2
    img = [[0] * w for _ in range(h)]
    for y, r in enumerate(mask):
        for x, v in enumerate(r):
            if v:
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if img[y + 1 + dy][x + 1 + dx] == 0:
                            img[y + 1 + dy][x + 1 + dx] = 2
    for y, r in enumerate(mask):
        for x, v in enumerate(r):
            if v:
                img[y + 1][x + 1] = 1
    return img


def _paste_centered(can, img, top, color):
    """color(역할, y) → 색번호. 가로 가운데."""
    W = len(can[0])
    x0 = (W - len(img[0])) // 2
    # 1 px 까지는 넘쳐도 된다(바깥 테두리 한 줄만 잘림 — 원본 배지도 x 0‥39 를 꽉 채운다)
    assert x0 >= -1 and len(img[0]) + x0 <= W + 1 and top + len(img) <= len(can),         '그림이 칸을 넘음 %dx%d > %dx%d' % (len(img[0]), len(img), W, len(can))
    for y, r in enumerate(img):
        for x, v in enumerate(r):
            if v and 0 <= x0 + x < W:
                if v == 1 and not 0 <= x0 + x < W:
                    raise AssertionError('글자 채움이 잘림')
                can[top + y][x0 + x] = color(v, top + y)


def build(ncer_b, ncbr_b, dsr_bytes):
    cells = ncer.cells(ncer_b)
    o, sz = ncer.ncgr_data(ncbr_b)
    data = bytearray(ncbr_b[o:o + sz])
    old = bytes(data)
    g14 = bdf.load(FONT_DIR + 'Galmuri14.bdf')           # 장 배지: 가로만 2 px 획(한글은 세로까지 부풀리면 뭉개진다)
    g11b = bdf.load(FONT_DIR + 'Galmuri11-Bold.bdf')     # 노멀·하드: 굵은 글꼴 그대로
    getpx = lambda ob: ncer.obj_pixels_bitmap(old, ob, UNIT)

    def write_back(c, can, x0, y0):
        for ob in cells[c]:
            px = [[can[ob['y'] - y0 + y][ob['x'] - x0 + x] for x in range(ob['w'])] for y in range(ob['h'])]
            ncer.put_obj_bitmap(data, ob, px, UNIT)

    # ── 장 배지
    for c, text in CHAPTER.items():
        can, cov, x0, y0 = ncer.cell_canvas(cells[c], getpx)
        frame = 4 if c == 27 else 5
        edge = 2 if c == 27 else 1
        rows_fill = {}                                     # 6장: 줄마다 채움 색이 다르다 → 원본 줄 색 그대로
        for y, r in enumerate(can):
            cnt = Counter(v for v in r if v not in (0, edge, frame))
            if cnt:
                rows_fill[y] = cnt.most_common(1)[0][0]
        for r in can:                                      # 장식(frame 색)만 남기고 지움
            for x, v in enumerate(r):
                if v != frame:
                    r[x] = 0
        mask = bold_mask(text, g14, 0, HORIZ)              # 자간 0: 테두리끼리 겹침(40 px 안)
        if c == 22:                                        # 「1」 만 좁다 → 제·장을 양옆으로 벌려 다른 장 폭에 맞춤(사용자 요청)
            want = min(len(bold_mask(t, g14, 0, HORIZ)[0]) for k, t in CHAPTER.items() if k != 22)
            extra = max(0, want - len(mask[0]))
            mask = bold_mask(text, g14, [extra // 2, extra - extra // 2, 0], HORIZ)
        img = outlined(mask)
        top = 4 + (17 - len(img)) // 2
        _paste_centered(can, img, top, lambda v, y: edge if v == 2 else (rows_fill.get(y, 10) if c == 27 else 3))
        write_back(c, can, x0, y0)

    # ── 노멀(28) · 하드(29)
    can, cov, x0, y0 = ncer.cell_canvas(cells[28], getpx)
    can = [[0] * len(can[0]) for _ in can]
    img = outlined(bold_mask('노멀', g11b, 1, NONE))
    _paste_centered(can, img, (len(can) - len(img)) // 2, lambda v, y: 11 if v == 2 else 1)
    write_back(28, can, x0, y0)
    can, cov, x0, y0 = ncer.cell_canvas(cells[29], getpx)
    for y, r in enumerate(can):                            # 글자(A) 를 그 줄 막대 색으로 지움
        bar = Counter(v for v in r if v and v != 10).most_common(1)
        for x, v in enumerate(r):
            if v == 10:
                r[x] = bar[0][0] if bar else 0
    m = bold_mask('하드', g11b, 1, NONE)
    _paste_centered(can, [[1 if v else 0 for v in r] for r in m], (len(can) - len(m)) // 2, lambda v, y: 10)
    write_back(29, can, x0, y0)

    # ── 파일 선택 버튼 · 탭(자기 전용 비트맵 — 제자리)
    font = titletext.Font(dsr_bytes)
    g9f = bdf.load(FONT_DIR + 'Galmuri9.bdf')
    import hudlabel
    for c, text in BUTTONS.items():
        can, cov, x0, y0 = ncer.cell_canvas(cells[c], getpx)
        tob = [ob for ob in cells[c] if ob['x'] == 32][0]
        bg = Counter(v for r in can[3:12] for v in r[33:63] if v and v != 2).most_common(1)[0][0]
        for y in range(16):
            for x in range(32, 64):
                if can[y][x] == 2:
                    can[y][x] = bg
        line = titletext.render_line(font, [('W', text)])
        lw = len(line[0])
        assert lw <= 32, '버튼 %r 폭 %d' % (text, lw)
        lx = 48 - lw // 2
        for y in range(10):
            for x in range(lw):
                if line[y][x]:
                    can[2 + y][lx + x] = 2
        px = [[can[tob['y'] - y0 + y][tob['x'] - x0 + x] for x in range(tob['w'])] for y in range(tob['h'])]
        ncer.put_obj_bitmap(data, tob, px, UNIT)
    for c, (text, fill, edge, erase, bg) in TABS.items():
        can, cov, x0, y0 = ncer.cell_canvas(cells[c], getpx)
        for y in range(2, 18):
            for x in range(21, 78):
                if can[y][x] in erase:
                    can[y][x] = bg
        img = hudlabel.label(text, g9f, 57, 16, 1, 1, 0, center=True)
        for y in range(16):
            for x in range(57):
                if img[y][x]:
                    can[2 + y][21 + x] = fill if img[y][x] == 1 else edge
        write_back(c, can, x0, y0)

    # ── 세이브 위치 이름: 배치 새로 짜기
    font = titletext.Font(dsr_bytes)
    keep = set()
    for c, objs in enumerate(cells):
        for ob in objs:
            n = ob['w'] * ob['h'] // 2 // UNIT
            if c not in NAMES or ob['tile'] == 332:
                keep |= set(range(ob['tile'], ob['tile'] + n))
    free = [u for u in range(sz // UNIT) if u not in keep]
    for u in free:
        data[u * UNIT:(u + 1) * UNIT] = bytes(UNIT)
    dedupe = {}

    def alloc(px):
        key = bytes(v for r in px for v in r)
        if key in dedupe:
            return dedupe[key]
        n = len(px) * len(px[0]) // 2 // UNIT
        for i in range(len(free) - n + 1):             # 연속 빈 단위 찾기
            if free[i + n - 1] - free[i] == n - 1:
                u = free[i]
                del free[i:i + n]
                ob = dict(tile=u, w=len(px[0]), h=len(px))
                ncer.put_obj_bitmap(data, ob, px, UNIT)
                dedupe[key] = u
                return u
        raise AssertionError('ui_title 빈 단위 모자람(%d 단위 필요)' % n)

    for c, name in NAMES.items():
        objs = cells[c]
        fobj = [ob for ob in objs if ob['tile'] == 332]
        tmpl = objs[-1]
        line = titletext.render_line(font, [('W', name)])
        line = [[1 if v else 0 for v in r] for r in line]
        lw = len(line[0])
        right = NAME_RIGHT.get(c, 80)
        left = right - lw
        assert left >= 0, '이름 %r 폭 %d > %d' % (name, lw, right)
        band = [[0] * lw for _ in range(16)]
        for y in range(10):
            band[y] = line[y]
        new = []
        x = right
        while x > left:                                    # 오른쪽 끝에서부터 잘라 같은 꼬리(「의 수호자」·「의 기억」)를 나눠 쓴다
            rest = x - left
            w = 32 if rest > 24 else (16 if rest > 8 else 8)    # 17‥24 px 는 16+8 이 32 보다 작다
            sx = x - w - left
            px = [[band[y][sx + i] if 0 <= sx + i < lw else 0 for i in range(w)] for y in range(16)]
            new.append(dict(x=x - w, y=tmpl['y'], w=w, h=16, tile=alloc(px), pal=tmpl['pal'], raw=tmpl['raw']))
            x -= w
        cells[c] = fobj + new
    out_ncbr = ncbr_b[:o] + bytes(data) + ncbr_b[o + sz:]
    return titletext.ncer_write(ncer_b, cells), out_ncbr, len(free)
