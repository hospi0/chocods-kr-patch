# -*- coding: utf-8 -*-
r"""그림 글자 전수 조사용 — FBC 마다 셀(OBJ)·화면(BG)을 모두 그려 한 장씩 work/survey/<경로>.png 로.
  python tools/gfxsurvey.py <경로 정규식>
OBJ: NCER + NCGR(1D 타일) 또는 NCBR(선형 비트맵; 단위 = RAHC 매핑 0x10→32 B, 0x100010→64 B, 0x200010→128 B).
BG : NSCR + NCGR. 팔레트는 같은 FBC 의 NCLR, 없으면 회색조(글자 판별용).
"""
import os, re, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fbc, lz11, ncer, gfxdump
import ndspy.rom, ndspy.lz10
from PIL import Image, ImageDraw

ORIG = r'C:\claude\roms\nds\Cid to Chocobo no Fushigi na Dungeon - Toki Wasure no Meikyuu DS+ (Japan).nds'
UNIT = {0x10: 32, 0x0: 32, 0x100010: 64, 0x200010: 128, 0x300010: 256}


def gray(v):
    return (v * 17, v * 17, v * 17) if v else (40, 40, 60)


def render_cells(ents, pal):
    er = [b for n, b in ents if b[:4] == b'RECN']
    gr = [b for n, b in ents if b[:4] == b'RGCN']
    out = []
    for e, g in zip(er, gr):
        i = g.index(b'RAHC')
        bpp = struct.unpack_from('<I', g, i + 12)[0]
        mp = struct.unpack_from('<I', g, i + 16)[0]
        linear = struct.unpack_from('<I', g, i + 20)[0] & 0xff
        o, sz = ncer.ncgr_data(g)
        T = g[o:o + sz]
        unit = UNIT.get(mp, 32)
        for c, objs in enumerate(ncer.cells(e)):
            if not objs:
                continue
            x0 = min(ob['x'] for ob in objs); y0 = min(ob['y'] for ob in objs)
            W = max(ob['x'] + ob['w'] for ob in objs) - x0; H = max(ob['y'] + ob['h'] for ob in objs) - y0
            if W > 512 or H > 512:
                continue
            im = Image.new('RGB', (W, H), (40, 40, 60))
            for ob in reversed(objs):
                try:
                    if bpp == 4 and linear:     # 8bpp 선형
                        st = ob['tile'] * unit
                        px = [[T[st + y * ob['w'] + x] if st + y * ob['w'] + x < len(T) else 0 for x in range(ob['w'])] for y in range(ob['h'])]
                    elif bpp == 4:     # 8bpp 타일
                        px = [[0] * ob['w'] for _ in range(ob['h'])]
                        for ty in range(ob['h'] // 8):
                            for tx in range(ob['w'] // 8):
                                t = ob['tile'] * unit // 64 + ty * (ob['w'] // 8) + tx
                                tp = gfxdump.tile_px(T, t, 8)
                                for y in range(8):
                                    for x in range(8):
                                        px[ty * 8 + y][tx * 8 + x] = tp[y][x]
                    elif linear:
                        px = ncer.obj_pixels_bitmap(T, ob, unit)
                    else:
                        ob2 = dict(ob); ob2['tile'] = ob['tile'] * unit // 32
                        px = ncer.obj_pixels(T, ob2)
                except Exception:
                    continue
                for y in range(ob['h']):
                    for x in range(ob['w']):
                        v = px[y][x]
                        if v:
                            k = v if bpp == 4 else ob['pal'] * 16 + v
                            col = pal[k] if pal and k < len(pal) else gray(v & 15)
                            im.putpixel((ob['x'] - x0 + x, ob['y'] - y0 + y), col)
            out.append(('c%d' % c, im))
    return out


def render_bg(ents, pal):
    scr = [b for n, b in ents if b[:4] == b'RCSN']
    gr = [b for n, b in ents if b[:4] == b'RGCN']
    if not scr or not gr:
        return []
    data, bpp = gfxdump.ncgr_tiles(gr[0])
    return [('bg', gfxdump.render_scr(scr[0], data, bpp, pal))]


def sheet(items, title):
    S = 2
    Wmax = 1024
    X = Y = 0
    rowh = 0
    pos = []
    for name, im in items:
        w, h = im.width * S, im.height * S + 12
        if X + w > Wmax:
            X = 0; Y += rowh + 4; rowh = 0
        pos.append((name, im, X, Y)); X += w + 6; rowh = max(rowh, h)
    out = Image.new('RGB', (Wmax, max(1, Y + rowh)), (0, 0, 0))
    d = ImageDraw.Draw(out)
    for name, im, x, y in pos:
        out.paste(im.resize((im.width * S, im.height * S), Image.NEAREST), (x, y + 12))
        d.text((x, y), name, fill=(255, 255, 0))
    return out


def main(pattern, outdir='work/survey'):
    os.makedirs(outdir, exist_ok=True)
    rom = ndspy.rom.NintendoDSRom.fromFile(ORIG)
    ids = {}

    def walk(folder, pre=''):
        for i, name in enumerate(folder.files):
            ids[pre + name] = folder.firstID + i
        for name, sub in folder.folders:
            walk(sub, pre + name + '/')
    walk(rom.filenames)
    n = 0
    for path, fid in sorted(ids.items()):
        if not re.search(pattern, path) or '.FBC' not in path.upper():
            continue
        d = rom.files[fid]
        try:
            if path.endswith('.z'):
                d = lz11.decompress(d) if d[0] == 0x11 else ndspy.lz10.decompress(d)
            ents = list(fbc.walk(d))
        except Exception:
            continue
        pal = None
        for nm, b in ents:
            if b[:4] == b'RLCN':
                pal = ncer.nclr(b)
        items = render_cells(ents, pal) + render_bg(ents, pal)
        if not items:
            continue
        sheet(items, path).save(os.path.join(outdir, path.replace('romdata/', '').replace('/', '__') + '.png'))
        n += 1
    print('그림', n)


if __name__ == '__main__':
    main(sys.argv[1])
