# -*- coding: utf-8 -*-
r"""이름·합언어 입력 자판 바탕(UI/KBD/kbdres kbd_jp.NCGR, 256×104 를 타일 순서대로 담은 그림) 라벨 한글판.

  かな → 한1 · カナ → 한2(한글 자판 1·2쪽) · ゛ ゜ 小字 → 지움(한글엔 쓸모없는 키) · きりかえ → 전환
영역(픽셀)·색은 원본에서 잰 값(2026-09-25): 키 바탕 4 · 키 글자 6 · きりかえ 띠 5(검정) 위 글자 7(흰색).
"""
import struct

import bdf
import hudlabel

FD = 'C:/claude/utils/font/Galmuri-v2.40.3/'
W, H = 256, 104
# (영역 x0, y0, x1, y1 — 끝 포함, 새 글자(None = 지우기), 글자 색, 바탕 색)
LABELS = [
    ((5, 5, 23, 19), '한1', 6, 4),        # かな
    ((5, 21, 23, 35), '한2', 6, 4),       # カナ
    ((3, 39, 26, 55), None, 6, 4),        # ゛
    ((3, 57, 26, 73), None, 6, 4),        # ゜
    ((3, 75, 26, 91), None, 6, 4),        # 小字
    ((227, 65, 254, 72), '전환', 7, 5),   # きりかえ
]

KIRIKAE = [LABELS[-1]]   # 기호·그림 문자 쪽(kbd_mark)도 같은 자리에 きりかえ(실기 2026-09-25: 전환 뒤 일본어로 돌아감)


def build(ncgr, labels=None):
    """labels=None → 전부(kbd_jp). 기호·그림 문자 쪽 바탕 kbd_mark 는 「きりかえ」만(KIRIKAE)."""
    labels = LABELS if labels is None else labels
    i = ncgr.index(b'RAHC')
    sz = struct.unpack_from('<I', ncgr, i + 0x18)[0]
    data = bytearray(ncgr[i + 0x20:i + 0x20 + sz])
    img = [[0] * W for _ in range(H)]
    for t in range(sz // 32):
        tx, ty = t % 32, t // 32
        for y in range(8):
            for x in range(8):
                img[ty * 8 + y][tx * 8 + x] = (data[t * 32 + y * 4 + x // 2] >> (4 * (x & 1))) & 15
    font = bdf.load(FD + 'Galmuri7.bdf')
    for (x0, y0, x1, y1), text, fg, bg in labels:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if img[y][x] == fg:
                    img[y][x] = bg
        if text:
            b = hudlabel.text_bits(text, font, 1)
            h, w = len(b), len(b[0])
            ox = x0 + (x1 - x0 + 1 - w) // 2
            oy = y0 + (y1 - y0 + 1 - h) // 2
            assert ox >= x0 and oy >= y0 and ox + w <= x1 + 1 and oy + h <= y1 + 1, '%s 가 영역 밖' % text
            for y in range(h):
                for x in range(w):
                    if b[y][x]:
                        img[oy + y][ox + x] = fg
    for t in range(sz // 32):
        tx, ty = t % 32, t // 32
        for y in range(8):
            for x in range(0, 8, 2):
                data[t * 32 + y * 4 + x // 2] = img[ty * 8 + y][tx * 8 + x] | (img[ty * 8 + y][tx * 8 + x + 1] << 4)
    return ncgr[:i + 0x20] + bytes(data) + ncgr[i + 0x20 + sz:]
