# -*- coding: utf-8 -*-
r"""바탕 UI 낱말(UI/BASEUI/bg_base_<지역>.NCGR 의 BG 타일) 한글판.

글자는 화면 배치(NSCR)가 가리키는 타일에 그려져 있고, 지역마다 NCGR 이 따로라 타일 번호가 다르다
→ (NSCR, 지역) 마다 화면 영역(타일 칸)을 판으로 펼쳐 옛 글자를 지우고 새로 그린 뒤 그 타일에 되쓴다.
되쓰는 타일은 그 NCGR 을 쓰는 모든 NSCR 에서 이 영역에만 나와야 한다(assert — 다른 곳 무늬를 깨지 않게).

작업 = (NSCR 경로 틀 {v}=지역, 지역들, 영역 타일칸 tx0,ty0,tx1,ty1, [줄: (글자, x, y, 채움, 테두리|None)], 지울 색, 바탕 규칙)
"""
import struct
import bdf
import hudlabel

FD = 'C:/claude/utils/font/Galmuri-v2.40.3/'
VARIANTS = ['cid', 'dark', 'field', 'fire', 'light', 'memory', 'water']

JOBS = [
    ('romdata/UI/CSTMBOX/bg_kaizo2_{v}.FBC.z', ['cid'], (11, 7, 17, 9),
     [('사용 재료', None, 3, 15, None)], {15}, lambda x, y: 2),                              # つかうそざい
    ('romdata/UI/STATMENU/bg_stat_{v}.FBC.z', ['cid'], (0, 14, 7, 17),          # 다른 지역판은 이 자리가 빈 판
     [('찾은', 5, 1, 15, 11), ('그렌의 메모', 4, 11, 15, 11)], {15, 11},
     lambda x, y: None if x >= 49 else (10 if 5 <= y <= 17 and x >= 4 else 13)),   # x ≥ 49 = 오른쪽 아이콘(지우지 않음)                                    # みつけた / グレンのメモ
]


def _scr(nscr):
    i = nscr.index(b'NRCS')
    return list(struct.unpack_from('<1024H', nscr, i + 0x14))


def _px(data, t, x, y):
    b = data[t * 32 + y * 4 + x // 2]
    return (b >> (4 * (x & 1))) & 15


def patch(ncgr, nscrs, job_scr, region, lines, erase, bg):
    """ncgr: 그 지역 NCGR, nscrs: 그 NCGR 을 쓰는 모든 NSCR 바이트(겹침 검사), job_scr: 글자가 있는 NSCR"""
    i = ncgr.index(b'RAHC')
    sz = struct.unpack_from('<I', ncgr, i + 0x18)[0]
    data = bytearray(ncgr[i + 0x20:i + 0x20 + sz])
    m = _scr(job_scr)
    tx0, ty0, tx1, ty1 = region
    W, H = (tx1 - tx0) * 8, (ty1 - ty0) * 8
    cells = {}
    for ty in range(ty0, ty1):
        for tx in range(tx0, tx1):
            e = m[ty * 32 + tx]
            cells[(tx, ty)] = e
    used = {e & 0x3ff for e in cells.values()}
    for s in nscrs:                                             # 이 타일들이 영역 밖에서 쓰이면 안 된다
        mm = _scr(s)
        for k, e in enumerate(mm):
            tx, ty = k % 32, k // 32
            if (e & 0x3ff) in used and not (s is job_scr and (tx, ty) in cells):
                raise AssertionError('타일 0x%x 가 영역 밖(%d,%d)에서도 쓰임' % (e & 0x3ff, tx, ty))
    can = [[0] * W for _ in range(H)]
    for (tx, ty), e in cells.items():
        t, hf, vf = e & 0x3ff, (e >> 10) & 1, (e >> 11) & 1
        for y in range(8):
            for x in range(8):
                can[(ty - ty0) * 8 + y][(tx - tx0) * 8 + x] = _px(data, t, 7 - x if hf else x, 7 - y if vf else y)
    for y in range(H):
        for x in range(W):
            if can[y][x] in erase:
                v = bg(x, y)
                if v is not None:
                    can[y][x] = v
    font = bdf.load(FD + 'Galmuri7.bdf')
    for text, lx, ly, fill, edge in lines:
        b = hudlabel.text_bits(text, font, 1)
        h, w = len(b), len(b[0])
        if lx is None:
            lx = (W - w) // 2
        ink = [(lx + x, ly + y) for y in range(h) for x in range(w) if b[y][x]]
        assert all(0 <= x < W and 0 <= y < H for x, y in ink), '%r 가 영역 밖' % text
        if edge is not None:
            for (x, y) in ink:
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if 0 <= x + dx < W and 0 <= y + dy < H:
                            can[y + dy][x + dx] = edge
        for (x, y) in ink:
            can[y][x] = fill
    for (tx, ty), e in cells.items():
        t, hf, vf = e & 0x3ff, (e >> 10) & 1, (e >> 11) & 1
        for y in range(8):
            for x in range(8):
                v = can[(ty - ty0) * 8 + (7 - y if vf else y)][(tx - tx0) * 8 + (7 - x if hf else x)]
                o = t * 32 + y * 4 + x // 2
                data[o] = (data[o] & (0xF0 if x & 1 == 0 else 0x0F)) | (v << (4 * (x & 1)))
    return ncgr[:i + 0x20] + bytes(data) + ncgr[i + 0x20 + sz:]
