# -*- coding: utf-8 -*-
r"""장 제목 그림(EVT_DAT/evt_dat1200‥1205 · EVT_DAT1063 안 evt_title_0N: NCER + NCBR 4bpp 선형, 단위 32 B) 한글판.

원본: 회색 16단 팔레트(0 투명·1 검정 → 15 흰색), 셀 원점 = 가운데. 위 「第N章」(작게) + 아래 제목(붓글씨 느낌, 크게)
+ 제목 밑 가로 선(가운데 밝고 양끝으로 흐려짐) + 선 아래 후리가나. 한글판은 후리가나를 없애고,
나눔명조 ExtraBold 로 그려(섞임색 → 회색 단계) 셀 배치를 새로 짠다(선은 원본 선 한 줄을 새 폭에 맞춰 늘림).
"""
import os
from PIL import Image, ImageDraw, ImageFont
import ncer
import titletext

FONT = 'C:/claude/utils/font/nanum-myeongjo/NanumMyeongjoExtraBold.ttf'
TITLES = {1: ('제1장', '망각의 거리, 예언의 구세주'), 2: ('제2장', '검은 살의의 불꽃'), 3: ('제3장', '물에 비친 달'),
          4: ('제4장', '빛을 찾아서…'), 5: ('제5장', '천공의 어둠, 지상의 빛'), 6: ('제6장', '시간을 새기는 거리')}
UNIT = 32
HEAD_PX, TITLE_PX = 15, 23          # 원본 「第一章」 약 14 줄, 제목 약 24 줄


def _gray_index(v):
    return 0 if v < 12 else max(2, min(15, round(v / 255 * 15)))


def build(ncer_b, ncbr_b, heading, title):
    cells = ncer.cells(ncer_b)
    objs = cells[0]
    o, sz = ncer.ncgr_data(ncbr_b)
    old = ncbr_b[o:o + sz]
    can, cov, x0, y0 = ncer.cell_canvas(objs, lambda ob: ncer.obj_pixels_bitmap(old, ob, UNIT))
    H0, W0 = len(can), len(can[0])
    # 원본 가로 선: 제목 아래에서 가장 넓게 퍼진 줄
    def run(r):                                              # 가장 긴 연속 잉크(후리가나 줄이 아니라 가로 선을 고르려고)
        best = cur = 0
        for v in r:
            cur = cur + 1 if v > 1 else 0                # 1 = 검정 바탕(불투명)
            best = max(best, cur)
        return best
    line_y = max(range(H0 // 2, H0), key=lambda y: run(can[y]))
    line = can[line_y]
    lx0 = min(x for x, v in enumerate(line) if v > 1)
    lx1 = max(x for x, v in enumerate(line) if v > 1) + 1
    # 새 그림 크기: 제목 폭 + 여백, 높이는 원본과 같게(후리가나 자리는 비움)
    fh = ImageFont.truetype(FONT, HEAD_PX)
    ft = ImageFont.truetype(FONT, TITLE_PX)
    tmp = ImageDraw.Draw(Image.new('L', (1, 1)))
    tb = tmp.textbbox((0, 0), title, font=ft)
    size = TITLE_PX
    while tb[2] - tb[0] > 224:                               # 긴 제목(1장)은 한 칸씩 줄여 256 안에
        size -= 1
        ft = ImageFont.truetype(FONT, size)
        tb = tmp.textbbox((0, 0), title, font=ft)
    hb = tmp.textbbox((0, 0), heading, font=fh)
    tw = tb[2] - tb[0]
    W = min(256, (max(tw + 24, lx1 - lx0, hb[2] - hb[0]) + 7) // 8 * 8)
    H = (H0 + 7) // 8 * 8
    im = Image.new('L', (W, H))
    dr = ImageDraw.Draw(im)
    head_top = [y for y in range(H0) if any(v > 1 for v in can[y])][0]
    dr.text((W // 2 - (hb[2] - hb[0]) // 2 - hb[0], head_top - hb[1]), heading, font=fh, fill=255)
    ty_bottom = line_y - 2                                    # 제목 글자 아래 끝 = 선 바로 위
    dr.text((W // 2 - tw // 2 - tb[0], ty_bottom - tb[3]), title, font=ft, fill=255)
    px = im.load()
    new = [[_gray_index(px[x, y]) for x in range(W)] for y in range(H)]
    # 선: 원본 선 한 줄을 새 폭(제목 폭 + 좌우 20)에 맞춰 늘림 — 가운데 밝고 양끝 흐림
    nl0, nl1 = max(0, W // 2 - tw // 2 - 20), min(W, W // 2 + tw // 2 + 20)
    # 원본 선 줄에는 한자 획이 선을 뚫고 지나간 밝은 점이 섞여 있다 → 가로 중앙값(±6)으로 걸러 매끈한 명암만 쓴다(찌꺼기 — 사용자 지적)
    prof = {}
    for dy in (-1, 0):
        row = can[line_y + dy]
        prof[dy] = [sorted(row[max(lx0, sx - 6):min(lx1, sx + 7)])[len(row[max(lx0, sx - 6):min(lx1, sx + 7)]) // 2]
                    for sx in range(W0)]
    for x in range(nl0, nl1):
        sx = lx0 + (x - nl0) * (lx1 - lx0) // max(1, nl1 - nl0)
        for dy in (-1, 0):                                 # 선은 두 줄(위 흐림·아래 밝음)
            v = prof[dy][sx]
            if v > 1:
                new[line_y + dy][x] = v
    # 셀 새로 짜기: 64×32 · 32×32 · 32×16 · 16×16 · 8×8 조각, 빈 조각은 뺌
    tmpl = objs[0]
    data = bytearray()
    no = []
    ox = -(W // 2)
    for sy in range(0, H, 32 if H - 0 >= 32 else 16):
        pass
    y = 0
    while y < H:
        h = 16 if H - y >= 16 else 8                             # 16 줄 띠로 잘라 빈 조각을 많이 뺀다(용량)
        x = 0
        while x < W:
            w = 32 if W - x >= 32 else (16 if W - x >= 16 else 8)
            blk = [r[x:x + w] for r in new[y:y + h]]
            if any(any(r) for r in blk):
                u = len(data) // UNIT
                buf = bytearray(w * h // 2)
                ncer.put_obj_bitmap(buf, dict(tile=0, w=w, h=h), blk, UNIT)
                data += buf
                no.append(dict(x=(ox + x) & 0x1ff, y=(y0 + y) & 0xff, w=w, h=h, tile=u, pal=tmpl['pal'], raw=tmpl['raw']))
            x += w
        y += h
    assert len(data) <= sz * 2, '장 제목 비트맵 %d B > 원본 %d B 의 2배' % (len(data), sz)   # 조금 커지는 건 허용(FBC 가 크기를 적음)
    data += bytes(max(0, sz - len(data)))
    import struct
    nb = bytearray(ncbr_b[:o] + bytes(data) + ncbr_b[o + sz:])
    i = nb.index(b'RAHC')
    struct.pack_into('<I', nb, i + 0x18, len(data))                   # 자료 크기
    struct.pack_into('<I', nb, i + 4, 0x20 + len(data))               # 블록 크기
    struct.pack_into('<I', nb, 8, len(nb))                            # 파일 크기
    return titletext.ncer_write(ncer_b, [no] + cells[1:]), bytes(nb), (W, H, new)


FILES = {1: ['evt_dat1200'], 2: ['evt_dat1201'], 3: ['evt_dat1202'], 4: ['evt_dat1203'], 5: ['evt_dat1204', 'EVT_DAT1063'],
         6: ['evt_dat1205']}


def patch_rom(rom, ids, replace_nested):
    import fbc
    import lz11
    n = 0
    for k, names in FILES.items():
        for nm in names:
            path = 'romdata/EVT_DAT/%s.FBC.z' % nm
            fid = ids[path]
            d = bytes(lz11.decompress(bytes(rom.files[fid])))
            ents = dict(fbc.walk(d))
            base = '@fbc/evt_title_%02d.FBC/evt_title_%02d' % (k, k)
            nce, ncb, _ = build(ents[base + '.NCER'], ents[base + '.NCBR'], *TITLES[k])
            repl = {base + '.NCER': nce, base + '.NCBR': ncb}
            nd = replace_nested(d, repl)
            assert not repl, '못 찾은 경로 %s' % list(repl)
            rom.files[fid] = bytes(lz11.compress(nd))
            n += 1
    return n
