# -*- coding: utf-8 -*-
r"""상태 변화 팝업(UI/DMGCNTR/num_counter.FBC: NCER 38셀 + NCBR 4bpp 선형, 단위 32 B) 한글판.

원본 꼴: 높이 8 px, 글자 채움 9 + 1 px 테두리 1, 셀 원점(x 0)을 가운데로 OBJ 가 좌우에 놓인다(-16‥16 등).
한글 = 갈무리7(7 px) + 테두리, 아래 테두리 한 줄은 잘림(칸 8 px, 사용자 지정). 원래 칸이 좁은 이름(배리어 등)이 있어
셀 배치를 새로 짠다: 숫자·EXP·JP·MISS(셀 0‥11, 13) 는 원본 단위를 그대로 옮기고, 글자 셀은 새 비트맵 — 총 크기는 원본 이하.
"""
import bdf
import hudlabel
import ncer
import titletext

UNIT = 32
FILL, EDGE = 9, 1
FONT = 'C:/claude/utils/font/Galmuri-v2.40.3/Galmuri7.bdf'
NAMES = {12: '길', 14: '프로테스', 15: '셸', 16: '배리어', 17: '마배리어', 18: '독', 19: '암흑', 20: '혼란', 21: '침묵',
         22: '슬리플', 23: '돈무브', 24: '슬로', 25: '헤이스트', 26: '버서크', 27: '브레이브', 28: '맹약', 29: '스턴',
         30: '리레이즈', 31: '은신', 32: '모으기', 33: '약UP', 34: '책UP', 35: '파워브레', 36: '아머브레', 37: '연속마'}


def build(ncer_b, ncbr_b):
    cells = ncer.cells(ncer_b)
    o, sz = ncer.ncgr_data(ncbr_b)
    old = ncbr_b[o:o + sz]
    font = bdf.load(FONT)
    data = bytearray()

    def put(px):
        u = len(data) // UNIT
        w, h = len(px[0]), len(px)
        buf = bytearray(w * h // 2)
        ncer.put_obj_bitmap(buf, dict(tile=0, w=w, h=h), px, UNIT)
        data.extend(buf)
        return u

    new = []
    for c, objs in enumerate(cells):
        if c not in NAMES:                                    # 원본 그대로 옮김
            no = []
            for ob in objs:
                px = ncer.obj_pixels_bitmap(old, ob, UNIT)
                d = dict(ob)
                d['tile'] = put(px)
                no.append(d)
            new.append(no)
            continue
        text = NAMES[c]
        tw = len(hudlabel.text_bits(text, font, 1)[0]) + 2
        W = (tw + 7) // 8 * 8
        img = hudlabel.label(text, font, W, 8, 1, 1, 0, clip_bottom=True)   # 아래 테두리 한 줄 잘림(위를 자르면 글자 윗줄이 잘려 보임 — 실기)
        px_all = [[{0: 0, 1: FILL, 2: EDGE}[v] for v in r] for r in img]
        tmpl = objs[0]
        x = -W // 2 // 8 * 8 if W > 8 else 0
        no = []
        sx = 0
        while sx < W:
            w = 32 if W - sx >= 32 else (16 if W - sx >= 16 else 8)
            px = [r[sx:sx + w] for r in px_all]
            no.append(dict(x=x + sx, y=tmpl['y'], w=w, h=8, tile=put(px), pal=tmpl['pal'], raw=tmpl['raw']))
            sx += w
        new.append(no)
    assert len(data) <= sz, '팝업 비트맵 %d B > 원본 %d B' % (len(data), sz)
    data += bytes(sz - len(data))
    return titletext.ncer_write(ncer_b, new), ncbr_b[:o] + bytes(data) + ncbr_b[o + sz:]
