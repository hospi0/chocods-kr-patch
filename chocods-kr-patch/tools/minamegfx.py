# -*- coding: utf-8 -*-
r"""필드 지도 지명(FLD/SWSPR/MINAME00·01.FBC: NCER + NCBR 4bpp 선형) 한글판.

원본 꼴: 게임 글꼴 글리프(흰 1) + 8방향 테두리(검정 15) + 오른쪽 아래 그림자(2), 셀 원점 = 가운데.
이름 셀만 배치를 새로 짜고(글자 폭에 맞춰 32/16/8 OBJ, 가운데), 테 조각 셀은 원본 단위를 그대로 옮긴다. 총 크기 ≤ 원본.
MINAME00 단위 32 B(매핑 0x10), MINAME01 단위 64 B(0x100010).
"""
import ncer
import titletext

FILES = {
    'romdata/FLD/SWSPR/MINAME00.FBC.z': (32, {0: '스텔라의 집', 1: '목장 입구', 2: '외양간', 3: '사일로', 4: '시냇가',
                                               5: '여신의 샘', 6: '기관차'}),
    'romdata/FLD/SWSPR/MINAME01.FBC.z': (64, {0: '어물전・약방・꽃집', 1: '보관소', 2: '해변 공원', 3: '다들러의 가게',
                                               4: '교회', 5: '시계탑 광장', 6: '광산구 광장', 7: '천공 공원',
                                               8: '아무리의 집', 9: '시장의 집', 10: '레비아 곶', 11: '어둠의 신전',
                                               12: '던전으로'}),
}
WHITE, BLACK, SHADOW = 1, 15, 2


def render(font, text):
    line = titletext.render_line(font, [('W', text)])
    lw = len(line[0])
    W = (lw + 3 + 7) // 8 * 8
    can = [[0] * W for _ in range(16)]
    ink = [(1 + x, 1 + y) for y in range(10) for x in range(lw) if line[y][x]]
    for (x, y) in ink:                                   # 그림자 먼저(테두리 한 칸 바깥)
        for dy in (0, 1, 2):
            for dx in (0, 1, 2):
                if (dx == 2 or dy == 2) and x + dx < W and y + dy < 16:
                    can[y + dy][x + dx] = SHADOW
    for (x, y) in ink:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if 0 <= x + dx < W and 0 <= y + dy < 16:
                    can[y + dy][x + dx] = BLACK
    for (x, y) in ink:
        can[y][x] = WHITE
    return can, W


def build(ncer_b, ncbr_b, unit, names, font):
    cells = ncer.cells(ncer_b)
    o, sz = ncer.ncgr_data(ncbr_b)
    old = ncbr_b[o:o + sz]
    data = bytearray()

    def put(px):
        u = len(data) // unit
        w, h = len(px[0]), len(px)
        buf = bytearray(w * h // 2)
        ncer.put_obj_bitmap(buf, dict(tile=0, w=w, h=h), px, unit)
        buf += bytes(-len(buf) % unit)
        data.extend(buf)
        return u
    new = []
    cache = {}
    for c, objs in enumerate(cells):
        if c not in names:
            no = []
            for ob in objs:
                key = (ob['tile'], ob['w'], ob['h'])
                if key not in cache:
                    cache[key] = put(ncer.obj_pixels_bitmap(old, ob, unit))
                d = dict(ob); d['tile'] = cache[key]
                no.append(d)
            new.append(no)
            continue
        can, W = render(font, names[c])
        tmpl = objs[0]
        x0 = -(W // 2)
        no = []
        sx = 0
        while sx < W:
            w = 32 if W - sx >= 32 else (16 if W - sx >= 16 else 8)
            px = [r[sx:sx + w] for r in can]
            no.append(dict(x=x0 + sx, y=tmpl['y'], w=w, h=16, tile=put(px), pal=tmpl['pal'], raw=tmpl['raw']))
            sx += w
        new.append(no)
    assert len(data) <= sz, '지명 비트맵 %d B > 원본 %d B' % (len(data), sz)
    data += bytes(sz - len(data))
    return titletext.ncer_write(ncer_b, new), ncbr_b[:o] + bytes(data) + ncbr_b[o + sz:]
