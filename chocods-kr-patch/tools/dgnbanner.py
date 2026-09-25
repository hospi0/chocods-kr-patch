# -*- coding: utf-8 -*-
r"""던전 입장 이름 그림(UI/DGNFLOOR/DGN_00‥32.FBC: NCER 1셀 + NCBR 4bpp 선형 비트맵 단위 32 B, 32×16 OBJ 가로 줄) 한글판.

원본 꼴(DGN_00 실측): 게임 글꼴 글리프(색 1 흰색) + 8방향 1 px 테두리 + 아래 1 px 그림자(색 15 검정),
  글자 시작 x 5, 글리프 1‥9행 → 판 2‥10행. 밑줄 = 14행 색 1 (x 2 ‥ 글자 끝 + 11) + 15행 색 15.
글자 폭이 원본 판보다 넓으면 그 파일만 32 px 단위로 판을 늘린다(NCBR·NCER 머리 크기 함께 갱신).
"""
import struct
import ncer
import titletext

NAMES = ['사막의 탑', '수수께끼미궁', '불의 수호자', '물의 수호자', '빛의 수호자', '어둠의 수호자',
         '초코보의 추억', '고대 유적', '게일 시장의 기억', '시드의 기억', '프레이아의 기억', '메아의 기억',
         '시로마의 기억', '해리의 기억', '샤를로트의 기억', '플로라의 기억', '마리스의 기억', '로디의 기억',
         '클레어의 기억', '볼그의 기억', '로체 신부의 기억', '메디트의 기억', '스텔라의 기억', '아무리의 기억',
         '다들러의 기억', '크로마의 기억', '전생의 불꽃', '대해원의 주인', '성스러운심판', '위대한 용왕',
         '불과얼음', '던전 오브 히어로!', '이상한 던전']
WHITE, BLACK = 1, 15
X0 = 5


def render(font, text, W):
    line = titletext.render_line(font, [('W', text)])
    lw = len(line[0])
    x0 = X0
    while x0 > 3 and x0 + lw + 1 > W:                    # 판을 늘리지 않게 먼저 글자 시작을 당긴다(3 까지)
        x0 -= 1
    need = (x0 + lw + 1 + 7) // 8 * 8                  # lw 는 끝 글자 뒤 1 px 간격 포함 → 테두리 1 px 만 더함
    assert need <= W, '%r 폭 %d > 원본 판 %d — 이름을 줄이거나 판을 늘릴 것' % (text, need, W)
    ul_end = min(x0 + lw + 11, W)                        # 밑줄은 글자 끝 + 11, 판 안에서
    can = [[0] * W for _ in range(16)]
    ink = [(x0 + x, 1 + y) for y in range(10) for x in range(lw) if line[y][x]]
    for (x, y) in ink:                                       # 테두리 + 아래 그림자
        for dy in (-1, 0, 1, 2):
            for dx in (-1, 0, 1):
                if 0 <= y + dy < 13 and 0 <= x + dx < W:
                    can[y + dy][x + dx] = BLACK
    for (x, y) in ink:
        can[y][x] = WHITE
    for x in range(2, min(ul_end, W)):
        can[14][x] = WHITE
        can[15][x] = BLACK
    return can, W


def rebuild(ncer_b, ncbr_b, font, text):
    cells = ncer.cells(ncer_b)
    objs = cells[0]
    tmpl = objs[0]
    W0 = max(o['x'] + o['w'] for o in objs)
    can, W = render(font, text, W0)
    data = bytearray()
    new = []
    x = 0
    while x < W:                                         # 원본처럼 32 폭 뒤 끝은 16/8 폭
        rest = W - x
        w = 32 if rest >= 32 else (16 if rest >= 16 else 8)
        px = [row[x:x + w] for row in can]
        u = len(data) // 32
        buf = bytearray(w * 16 // 2)
        ncer.put_obj_bitmap(buf, dict(tile=0, w=w, h=16), px, 32)
        data += buf
        new.append(dict(x=x, y=tmpl['y'], w=w, h=16, tile=u, pal=tmpl['pal'], raw=tmpl['raw']))
        x += w
    cells[0] = new
    i = ncbr_b.index(b'RAHC')
    osz = struct.unpack_from('<I', ncbr_b, i + 0x18)[0]
    nsz = max(osz, len(data))
    data += bytes(nsz - len(data))
    blk = bytearray(ncbr_b[i:i + 0x20])
    struct.pack_into('<I', blk, 4, 0x20 + nsz)
    struct.pack_into('<I', blk, 0x18, nsz)
    out = bytearray(ncbr_b[:i]) + blk + bytes(data) + ncbr_b[i + 0x20 + osz:]
    struct.pack_into('<I', out, 8, len(out))
    return titletext.ncer_write(ncer_b, cells), bytes(out), W0, W
