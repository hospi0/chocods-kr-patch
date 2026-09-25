# -*- coding: utf-8 -*-
r"""타이틀 안내문 그림(UI/TM/ui_text.FBC: NCER 19셀 + NCBR 4bpp 선형 비트맵, 1D 64K → 단위 64 B) 한글판.

원본은 게임 글꼴(dsr_fnt 10×10)로 미리 그린 1 px 글자. 색번호 2 흰 · 7 빨강 · 6 초록 · 9 노랑 · 8 하늘, 14 = 깃털 아이콘.
셀끼리 같은 낱말 그림을 나눠 쓰고(단위 공유), 스프라이트는 일본어 글자 폭만큼만 덮는다
→ 셀 배치를 통째로 새로 짠다: 줄마다 16 px 높이 OBJ 띠(32×16 조각 + 끝 16/8 폭), 같은 조각은 단위를 나눠 쓴다(중복 제거).
깃털 아이콘 등 글자 아닌 화소(색 2·6·7·8·9 아님)는 원본 OBJ 를 그대로 남긴다.
비트맵 총 크기는 원본(33,408 B) 이하로 막는다 — 뒤에 ui_title 이 VRAM 에 이어 붙는다(세이브스테이트 실측).
"""
import struct
import bdf
import ncer
import nftr

GALMURI9 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri9.bdf'
UNIT = 64
INK = {'W': 2, 'R': 7, 'G': 6, 'Y': 9, 'C': 8}
TEXT_COLORS = set(INK.values())
MAX_W = 240                                   # 원본 가장 넓은 셀 폭

# 셀 번호 → 줄 목록, 줄 = [(색, 글자), …]
MSG = {
    0: [[('W', '플레이할 데이터를 선택해 주세요')]],
    1: [[('G', '세이브 모드'), ('W', '입니다')],
        [('W', '지난번에 이어서 게임을 시작합니다')]],
    2: [[('W', '데이터를 지웁니다')]],
    3: [[('W', '데이터를 지우면 되돌릴 수 없습니다')],
        [('W', '정말로 지워도 괜찮습니까？')]],
    4: [[('W', '플레이 모드를 선택해 주세요')],
        [('R', '여기서 정한 뒤에는 바꿀 수 없습니다')]],
    5: [[('Y', '재개 데이터'), ('W', '입니다 '), ('R', '지난번에 세이브 없이')],
        [('R', '게임을 끝낸 데이터입니다')]],
    6: [[('W', '게임 재개 후 '), ('R', '그만둘 때는 다시 중단하거나')],
        [('R', '필드에서 세이브 후 전원을 꺼 주세요')]],
    7: [[('W', '데이터가 손상되었습니다')],
        [('W', '지워도 괜찮습니까？')]],
    8: [[('W', '데이터가 손상되어서')],
        [('W', '시작할 수 없었습니다')]],
    9: [[('W', '데이터를 로드・세이브하고 있습니다')],
        [('R', '전원을 끄거나 DS 카드를 뽑지 마세요')]],
    10: [[('R', '여기서 정한 뒤에는 바꿀 수 없습니다')],
         [('W', '정말로 시작해도 괜찮습니까？')]],
    11: [[('W', '데이터를 지우고 있습니다 '), ('R', '전원을 끄거나')],
         [('R', 'DS 카드를 뽑지 마세요')]],
    12: [[('W', '보통 모드입니다')],
         [('W', '쓰러져도 '), ('R', '장비'), ('W', '는 없어지지 않습니다')]],
    13: [[('W', '어려운 모드입니다 적이 조금 강해지고')],
         [('W', '쓰러지면 '), ('R', '모든 아이템'), ('W', '을 잃습니다')]],
    14: [[('W', '데이터를 지웠습니다')]],
    15: [[('W', '데이터를 확인하고 있습니다…')]],
    16: [[('C', '중단 모드'), ('W', '로 재개합니다')],
         [('R', '중단 데이터는 한 번만 재개할 수 있습니다')]],
    17: [[('R', '중단한 던전에서 쓰러진 것으로 처리됩니다')],
         [('R', '던전 입구에서 시작하겠습니까？')]],
    18: [[('W', '데이터를 로드하고 있습니다…')]],
}


class Font:
    """게임 글꼴 그대로: 한글 = 갈무리9(빌더와 같은 배치), 나머지 = 원본 dsr_fnt 글리프"""

    def __init__(self, dsr_bytes):
        self.f = nftr.Nftr(dsr_bytes)
        self.G, self.asc = bdf.load(GALMURI9)

    def glyph(self, ch):
        """→ (10×10 0/1 배열, 왼쪽, 전진폭)"""
        o = ord(ch)
        if 0xAC00 <= o <= 0xD7A3:
            arr, _ = bdf.render(self.G, self.asc, o, 10, 10, 10)
            return arr, 0, 10
        i = self.f.lookup(o)
        if i is None:
            raise ValueError('글꼴에 없는 글자 %r' % ch)
        bm = self.f.glyphs[i]
        bits = ''.join(format(b, '08b') for b in bm)
        arr = [[int(bits[y * 10 + x]) for x in range(10)] for y in range(10)]
        left, gw, adv = self.f.widths[i]
        return arr, left, adv

    def width(self, text):
        return sum(self.glyph(c)[2] for c in text)


def render_line(font, segs):
    """→ 10행 색번호 배열(폭 = 전진폭 합)"""
    W = sum(font.width(t) for _, t in segs)
    img = [[0] * W for _ in range(10)]
    x = 0
    for col, text in segs:
        for ch in text:
            arr, left, adv = font.glyph(ch)
            for y in range(10):
                for gx in range(10):
                    if arr[y][gx] and 0 <= x + left + gx < W:
                        img[y][x + left + gx] = INK[col]
            x += adv
    return img


def _shapes(width):
    """줄 폭 → 16 높이 OBJ 조각 [(x, w)] (32 단위, 끝은 16/8)"""
    out = []
    x = 0
    while x < width:
        rest = width - x
        w = 32 if rest > 24 else (16 if rest > 8 else 8)    # 17‥24 px 는 16+8 이 32 보다 작다
        out.append((x, w))
        x += w
    return out


SHAPE_BITS = {(8, 8): (0, 0), (16, 16): (0, 1), (32, 32): (0, 2), (64, 64): (0, 3), (16, 8): (1, 0), (32, 8): (1, 1), (32, 16): (1, 2),
              (64, 32): (1, 3), (8, 16): (2, 0), (8, 32): (2, 1), (16, 32): (2, 2), (32, 64): (2, 3)}


def build(ncer_b, ncbr_b, dsr_bytes):
    font = Font(dsr_bytes)
    cells = ncer.cells(ncer_b)
    o, sz = ncer.ncgr_data(ncbr_b)
    old = ncbr_b[o:o + sz]
    units = bytearray()                       # 새 비트맵
    dedupe = {}

    def alloc(px):
        key = bytes(v for r in px for v in r)
        if key in dedupe:
            return dedupe[key]
        u = len(units) // UNIT
        w, h = len(px[0]), len(px)
        buf = bytearray(w * h // 2)
        for y in range(h):
            for x in range(0, w, 2):
                buf[(y * w + x) // 2] = px[y][x] | (px[y][x + 1] << 4)
        buf += bytes(-len(buf) % UNIT)
        units.extend(buf)
        dedupe[key] = u
        return u

    new_cells = []
    report = []
    for c, objs in enumerate(cells):
        can, cov, x0, y0 = ncer.cell_canvas(objs, lambda ob: ncer.obj_pixels_bitmap(old, ob, UNIT))
        H = len(can)
        bands = []
        for y in range(H):
            if any(v in TEXT_COLORS for v in can[y]):
                if bands and y - bands[-1][1] <= 2:
                    bands[-1][1] = y
                else:
                    bands.append([y, y])
        lines = MSG[c]
        assert len(lines) == len(bands), '셀 %d 줄 수 %d ≠ 원본 %d' % (c, len(lines), len(bands))
        tmpl = objs[0]
        oams = []
        for (a, b), segs in zip(bands, lines):
            img = render_line(font, segs)
            lw = len(img[0])
            assert lw <= MAX_W, '셀 %d 줄 폭 %d > %d: %r' % (c, lw, MAX_W, segs)
            top = y0 + b - 9 - 3                 # 원본 글리프 밑줄(b)을 맞춤: 10행 글리프는 1‥9행 → 띠 위 여백 3
            band = [[0] * lw for _ in range(16)]
            for y in range(10):
                band[3 + y] = img[y][:]
            for sx, w in _shapes(lw):
                px = [[band[y][sx + x] if sx + x < lw else 0 for x in range(w)] for y in range(16)]
                if not any(any(r) for r in px):
                    continue
                oams.append(dict(x=x0 + sx, y=top, w=w, h=16, tile=alloc(px), pal=tmpl['pal']))
            report.append((c, lw, ''.join(t for _, t in segs)))
        # 글자 아닌 화소(깃털 아이콘 등)는 그 화소를 감싸는 가장 작은 OBJ(16×16 등) 로 옮겨 남긴다
        icon = [(x, y, can[y][x]) for y in range(H) for x in range(len(can[0])) if can[y][x] and can[y][x] not in TEXT_COLORS]
        if icon:
            ix0 = min(x for x, _, _ in icon); iy0 = min(y for _, y, _ in icon)
            ix1 = max(x for x, _, _ in icon); iy1 = max(y for _, y, _ in icon)
            w = 8 if ix1 - ix0 < 8 else (16 if ix1 - ix0 < 16 else 32)
            h = 8 if iy1 - iy0 < 8 else 16
            px = [[0] * w for _ in range(h)]
            for x, y, v in icon:
                px[y - iy0][x - ix0] = v
            oams.append(dict(x=x0 + ix0, y=y0 + iy0, w=w, h=h, tile=alloc(px), pal=objs[0]['pal']))
        new_cells.append(oams)
    assert len(units) <= sz, '비트맵 %d B > 원본 %d B (VRAM 뒤에 ui_title)' % (len(units), sz)
    units += bytes(sz - len(units))           # 원본 크기 유지
    new_ncbr = ncbr_b[:o] + bytes(units) + ncbr_b[o + sz:]
    return ncer_write(ncer_b, new_cells), new_ncbr, report


def ncer_write(b, new_cells):
    """KBEC 셀 표·OAM 을 새로 쓰고 LBAL·TXEU 는 그대로 뒤에 붙인다(셀 수 불변)."""
    i = b.index(b'KBEC')
    blk_size = struct.unpack_from('<I', b, i + 4)[0]
    n, ext, off, mode = struct.unpack_from('<HHII', b, i + 8)
    assert ext == 0 and n == len(new_cells)
    base = i + 8 + off
    head = bytearray(b[i:base])                          # 블록 머리(+8) + 머리 필드
    table = bytearray()
    oam = bytearray()
    for c, objs in enumerate(new_cells):
        attr = struct.unpack_from('<H', b, base + 8 * c + 2)[0]      # 원본 셀 속성값 유지
        table += struct.pack('<HHI', len(objs), attr, len(oam))
        for o in objs:
            sh, sz = SHAPE_BITS[(o['w'], o['h'])]
            r0, r1, r2 = o.get('raw', (0, 0, 0))            # 원본 OAM 이면 나머지 비트(우선순위·뒤집기·모드) 유지
            a0 = (r0 & 0x3f00) | (o['y'] & 0xff) | (sh << 14)
            a1 = (r1 & 0x3e00) | (o['x'] & 0x1ff) | (sz << 14)
            a2 = (r2 & 0x0c00) | (o['tile'] & 0x3ff) | (o['pal'] << 12)
            oam += struct.pack('<HHH', a0, a1, a2)
    body = head + table + oam
    body += bytes(-len(body) % 4)
    struct.pack_into('<I', body, 4, len(body))
    rest = b[i + blk_size:]
    out = bytearray(b[:i]) + body + rest
    struct.pack_into('<I', out, 8, len(out))            # 파일 크기
    return bytes(out)
