# -*- coding: utf-8 -*-
r"""롬 안 모든 txtbin 문자열 → work/alltext.tsv (파일 · 안쪽 경로 · 번호 · 인코딩 · 원문)
원문 표기는 build.py 번역 TSV 와 같다: \n 줄바꿈 · {ESC} · {13} · {XX} 기타 제어 바이트."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fbc, lz11
import ndspy.rom, ndspy.lz10

ORIG = r'C:\claude\roms\nds\Cid to Chocobo no Fushigi na Dungeon - Toki Wasure no Meikyuu DS+ (Japan).nds'


def esc(s):
    out = []
    for ch in s:
        o = ord(ch)
        if ch == '\n':
            out.append(chr(92) + 'n')
        elif o == 0x1b:
            out.append('{ESC}')
        elif o == 0x13:
            out.append('{13}')
        elif o < 0x20 or ch == '\t':
            out.append('{%02X}' % o)
        else:
            out.append(ch)
    return ''.join(out)


def main():
    rom = ndspy.rom.NintendoDSRom.fromFile(ORIG)
    ids = {}

    def walk(folder, pre=''):
        for i, name in enumerate(folder.files):
            ids[pre + name] = folder.firstID + i
        for name, sub in folder.folders:
            walk(sub, pre + name + '/')
    walk(rom.filenames)
    n = 0
    with open('work/alltext.tsv', 'w', encoding='utf-8') as fo:
        for path, fid in sorted(ids.items()):
            if '.FBC' not in path.upper():
                continue
            d = rom.files[fid]
            if path.endswith('.z'):
                d = lz11.decompress(d) if d[0] == 0x11 else ndspy.lz10.decompress(d)
            if d[:4] != b'\x14\x00\x06\x00':
                continue
            for inner, b in fbc.walk(d):
                if not inner.endswith('.txtbin'):
                    continue
                strs = fbc.txtbin(b)
                enc = fbc.guess_enc(strs)
                enc = 'utf-8' if enc == 'ascii' else enc
                for i, s in enumerate(strs):
                    t = s.decode(enc, errors='replace')
                    if any(ord(c) >= 0x80 for c in t):
                        fo.write('%s\t%s\t%d\t%s\t%s\n' % (path, inner, i, enc, esc(t)))
                        n += 1
    print('문자열', n)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
