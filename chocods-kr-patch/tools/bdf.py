# -*- coding: utf-8 -*-
"""BDF 비트맵 글꼴 읽기 → {코드: (폭, 높이, x오프셋, y오프셋, 전진폭, 행 비트열 목록)}"""


def load(path):
    glyphs = {}
    asc = None
    cur = None
    rows = None
    for line in open(path, encoding='utf-8', errors='replace'):
        t = line.split()
        if not t:
            continue
        k = t[0]
        if k == 'FONT_ASCENT':
            asc = int(t[1])
        elif k == 'ENCODING':
            cur = {'code': int(t[1])}
        elif k == 'DWIDTH' and cur is not None:
            cur['adv'] = int(t[1])
        elif k == 'BBX' and cur is not None:
            cur['bbx'] = tuple(int(v) for v in t[1:5])
        elif k == 'BITMAP':
            rows = []
        elif k == 'ENDCHAR':
            w, h, xo, yo = cur['bbx']
            glyphs[cur['code']] = (w, h, xo, yo, cur.get('adv', w), rows)
            cur, rows = None, None
        elif rows is not None:
            v = int(k, 16)
            nbits = len(k) * 4
            bw = cur['bbx'][0]
            rows.append([(v >> (nbits - 1 - i)) & 1 for i in range(bw)])
    return glyphs, asc


def render(glyphs, asc, code, cw, ch, base):
    """code 글리프를 cw×ch 칸에 기준선 base(위에서 행 번호)로 놓은 0/1 2차원 배열."""
    g = glyphs.get(code)
    out = [[0] * cw for _ in range(ch)]
    if not g:
        return out, 0
    w, h, xo, yo, adv, rows = g
    top = base - (yo + h)
    for r, row in enumerate(rows):
        y = top + r
        if 0 <= y < ch:
            for c, v in enumerate(row):
                x = xo + c
                if v and 0 <= x < cw:
                    out[y][x] = 1
    return out, adv
