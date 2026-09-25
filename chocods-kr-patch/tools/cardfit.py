# -*- coding: utf-8 -*-
r"""카드 문구 줄 폭 계산(PUD/font/font.nftr 전진폭, 한글 = 10 px 가정: 본편과 같은 갈무리9 10×10 칸).
0x1C xx(색) 는 폭 0. 줄 = \n 으로 나뉜 조각."""
import struct
import ndspy.rom

_W = None
HANGUL_ADV = 10


def widths():
    global _W
    if _W is None:
        import nftr
        rom = ndspy.rom.NintendoDSRom.fromFile(r'C:\claude\roms\nds\Cid to Chocobo no Fushigi na Dungeon - Toki Wasure no Meikyuu DS+ (Japan).nds')
        F = {l.split('\t')[1]: int(l.split('\t')[0]) for l in open('work/files.tsv', encoding='utf-8')}
        f = nftr.Nftr(bytes(rom.files[F['romdata/PUD/font/font.nftr']]))
        cmap = {}
        for first, last, typ, data in f.cmaps:
            if typ == 0:
                base = struct.unpack_from('<H', data, 0)[0]
                cmap.update({c: base + c - first for c in range(first, last + 1)})
            elif typ == 1:
                for k, c in enumerate(range(first, last + 1)):
                    v = struct.unpack_from('<H', data, 2 * k)[0]
                    if v != 0xffff:
                        cmap[c] = v
            else:
                cmap.update(dict(data))
        _W = {c: f.widths[g][2] for c, g in cmap.items()}
    return _W


def line_w(s):
    W = widths()
    out, i = 0, 0
    while i < len(s):
        ch = s[i]
        if ch == '\x1c':
            i += 2
            continue
        o = ord(ch)
        if 0xAC00 <= o <= 0xD7A3:
            out += HANGUL_ADV
        else:
            out += W.get(o, 10)
        i += 1
    return out


def lines_w(s):
    return [line_w(l) for l in s.split('\n')]
