# -*- coding: utf-8 -*-
r"""UI 그림 전수 렌더 → work/gfx/<경로>.png (NSCR 있으면 화면 배치, 없으면 타일 시트 32칸 폭).
팔레트: 같은 FBC 의 NCLR, 없으면 회색조. 그림 글자 목록 작성용."""
import os, re, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fbc, lz11
import ndspy.rom, ndspy.lz10
from PIL import Image

ORIG = r'C:\claude\roms\nds\Cid to Chocobo no Fushigi na Dungeon - Toki Wasure no Meikyuu DS+ (Japan).nds'
GRAY4 = [(v * 17, v * 17, v * 17) for v in range(16)]


def ncgr_tiles(b):
    i = b.index(b'RAHC')
    h, w, bpp = struct.unpack_from('<HHI', b, i + 8)
    sz = struct.unpack_from('<I', b, i + 0x18)[0]
    return b[i + 0x20:i + 0x20 + sz], (4 if bpp == 3 else 8)


def tile_px(data, t, bpp):
    tb = 32 if bpp == 4 else 64
    s = data[t * tb:(t + 1) * tb]
    if len(s) < tb:
        return [[0] * 8 for _ in range(8)]
    if bpp == 4:
        return [[(s[y * 4 + x // 2] >> (4 * (x & 1))) & 15 for x in range(8)] for y in range(8)]
    return [[s[y * 8 + x] for x in range(8)] for y in range(8)]


def color(v, pal, bpp, pn=0):
    if pal:
        k = pn * 16 + v if bpp == 4 else v
        return pal[k] if k < len(pal) else (255, 0, 255)
    return GRAY4[v] if bpp == 4 else (v, v, v)


def render_sheet(data, bpp, pal):
    tb = 32 if bpp == 4 else 64
    n = len(data) // tb
    cols = 32
    rows = max(1, (n + cols - 1) // cols)
    im = Image.new('RGB', (cols * 8, rows * 8), (255, 0, 255))
    for t in range(n):
        px = tile_px(data, t, bpp)
        for y in range(8):
            for x in range(8):
                im.putpixel(((t % cols) * 8 + x, (t // cols) * 8 + y), color(px[y][x], pal, bpp))
    return im


def render_scr(scr, data, bpp, pal):
    i = scr.index(b'NRCS')
    w, h = struct.unpack_from('<HH', scr, i + 8)
    sz = struct.unpack_from('<I', scr, i + 0x10)[0]
    m = struct.unpack_from('<%dH' % (sz // 2), scr, i + 0x14)
    tw, th = w // 8, h // 8
    im = Image.new('RGB', (w, h), (255, 0, 255))
    for k, e in enumerate(m[:tw * th]):
        t, hf, vf, pn = e & 0x3ff, (e >> 10) & 1, (e >> 11) & 1, e >> 12
        px = tile_px(data, t, bpp)
        tx, ty = (k % 32) + (k // 1024) * 32, (k // 32) % 32   # 256 폭 스크린 블록
        if tw <= 32:
            tx, ty = k % tw, k // tw
        for y in range(8):
            for x in range(8):
                v = px[7 - y if vf else y][7 - x if hf else x]
                im.putpixel((tx * 8 + x, ty * 8 + y), color(v, pal, bpp, pn))
    return im


def main(pattern):
    rom = ndspy.rom.NintendoDSRom.fromFile(ORIG)
    ids = {}

    def walk(folder, pre=''):
        for i, name in enumerate(folder.files):
            ids[pre + name] = folder.firstID + i
        for name, sub in folder.folders:
            walk(sub, pre + name + '/')
    walk(rom.filenames)
    for path, fid in sorted(ids.items()):
        if not re.search(pattern, path) or '.FBC' not in path:
            continue
        d = rom.files[fid]
        if path.endswith('.z'):
            d = lz11.decompress(d) if d[0] == 0x11 else ndspy.lz10.decompress(d)
        if d[:4] != b'\x14\x00\x06\x00':
            continue
        ents = list(fbc.walk(d))
        pal = None
        for n, b in ents:
            if b[:4] == b'RLCN':
                j = b.index(b'TTLP')
                psz = struct.unpack_from('<I', b, j + 0x10)[0]
                pal = [((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3) for c in struct.unpack_from('<%dH' % (psz // 2), b, j + 0x18)]
        scr = [b for n, b in ents if b[:4] == b'RCSN']
        for n, b in ents:
            if b[:4] != b'RGCN':
                continue
            data, bpp = ncgr_tiles(b)
            out = 'work/gfx/' + path.replace('romdata/', '').replace('/', '__') + '__' + n.replace('/', '_') + '.png'
            im = render_scr(scr[0], data, bpp, pal) if scr else render_sheet(data, bpp, pal)
            im.save(out)
            print(out, im.size, bpp)


if __name__ == '__main__':
    main(sys.argv[1])
