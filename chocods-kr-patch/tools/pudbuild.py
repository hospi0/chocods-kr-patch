# -*- coding: utf-8 -*-
r"""카드 게임(romdata/PUD) 한글화 빌드 단계 — build.py 에서 patch_pud(rom, ids) 로 부른다.

1) 그림: work/pud_specs.json(셀별 설정) → D2KP 상자 안 NCGR(·NCER) 되쓰기, pubtopmenu NARC(배너·로고),
   조작 설명 머리글 48(pudsousa), 카드 이름 그림 147(cardname)
2) 카드 표 card.bin 두 벌(루트·ja) ← work/card_ko.tsv
3) 카드 게임 글꼴 PUD/font/font.nftr: 한자 칸을 한글로(크기 불변, 번역 전 글이 쓰는 한자 work/pud_keep_kanji.txt 는 남김)
압축은 원본과 같은 방식(LZ10/LZ11)으로 되돌린다.
"""
import json
import os
import sys
import ndspy.lz10
import ndspy.narc
import bdf
import cardbin
import cardname
import d2kp
import lz11
import ncer
import nftr
import pudbanner
import pudlabel
import pudlogo
import pudsousa

WORK = os.path.join(os.path.dirname(__file__), '..', 'work')
GALMURI9 = 'C:/claude/utils/font/Galmuri-v2.40.3/Galmuri9.bdf'


def unz(raw):
    raw = bytes(raw)
    if raw[:1] == b'\x11':
        return bytes(lz11.decompress(raw)), 'lz11'
    if raw[:1] == b'\x10':
        return bytes(ndspy.lz10.decompress(raw)), 'lz10'
    return raw, None


def rez(d, comp):
    if comp == 'lz11':
        return bytes(lz11.compress(d))
    if comp == 'lz10':
        return bytes(ndspy.lz10.compress(d))
    return d


def ep_palette(rom, ids):
    d, _ = unz(rom.files[ids['romdata/PUD/mgentryphase/ja/ep_sprite1.POBJ.z']])
    return pudlabel.blocks(d)['RLCN']


def apply_cells(sp, sp0, spec, pal):
    """work/pud_specs.json 한 파일분(셀 → [글자, 영역, 글꼴, 지우기, 채움, 정렬, 바깥테두리, 테두리색])"""
    for c, t in spec.items():
        t = (t + [None] * 7)[:8] if isinstance(t, list) else [t] + [None] * 7
        if not t[0]:
            continue
        cell = int(c.split('#')[0])
        if isinstance(t[4], str) and t[4].startswith('grad:'):
            t[4] = pudlabel.ramp(sp0, int(t[4][5:]), pal)
        mode = t[3]
        if mode == 'seg':
            pudlabel.rewrap_seg(sp, cell, t[0], pal, seg=tuple(t[1]) if t[1] else None, font=t[2] or 'Galmuri11', fill=t[4] or 'hgrad')
        elif mode == 'ttf':
            pudlabel.ttf_cell(sp, cell, t[0], pal, order=t[4] or 'lumr')
        elif mode == 'glyph':
            pudlabel.glyph_cell(sp, cell, t[0], pal, font=t[2] or 'Galmuri7', fill=t[4])
        elif mode == 'rewrap':
            pudlabel.rewrap(sp, cell, t[0], font=t[2] or 'Galmuri9', fill=t[4] or 'grad', pal=pal)
        else:
            pudlabel.relabel(sp, cell, t[0], rect=tuple(t[1]) if t[1] else None, font=t[2], erase_to=mode, fill=t[4],
                             align=t[5] or 'center', ring=bool(t[6]), edge_c=t[7], pal=pal)


def patch_sprite_box(d, spec, relayout, pal_block):
    """D2KP 상자 한 개 → 고친 상자"""
    B = pudlabel.blocks(d)
    if 'RLCN' not in B:
        B['RLCN'] = pal_block
    pal = ncer.nclr(B['RLCN'][1])
    (co, cb), (go, gb) = B['RECN'], B['RGCN']
    nb, ngb = cb, gb
    if relayout:
        nb, ngb = pudlabel.relayout(cb, gb, {int(k): v for k, v in relayout.items()}, pal)
    if spec:
        sp = pudlabel.Sprites(nb, ngb)
        sp0 = pudlabel.Sprites(cb, gb)
        apply_cells(sp, sp0, spec, pal)
        ngb = sp.result()
    out = d
    if ngb != gb:
        out = d2kp.replace(out, go, ngb)
    if nb != cb:
        out = d2kp.replace(out, pudlabel.blocks(out)['RECN'][0], nb)
    return out


def patch_graphics(rom, ids):
    S = json.load(open(os.path.join(WORK, 'pud_specs.json'), encoding='utf-8'))
    palb = ep_palette(rom, ids)
    keys = {k.split('relayout:')[-1].split('@')[0] for k in S}
    n = 0
    for path in sorted(keys):
        narcs = sorted({k.split('@')[1] for k in S if k.startswith(path + '@')})
        fid = ids[path]
        if narcs:                                       # pubtopmenu: NARC 안 3(배너)·4(로고)
            nc = ndspy.narc.NARC(bytes(rom.files[fid]))
            for k in narcs:
                i = int(k)
                d, comp = unz(nc.files[i])
                B = pudlabel.blocks(d)
                pal = ncer.nclr(B['RLCN'][1])
                go, gb = B['RGCN']
                ngb = pudbanner.build(B['RECN'][1], gb, pal) if i == 3 else pudlogo.build(B['RECN'][1], gb, pal)
                nc.files[i] = rez(d2kp.replace(d, go, ngb), comp)
                n += 1
            rom.files[fid] = nc.save()
            continue
        d, comp = unz(rom.files[fid])
        nd = patch_sprite_box(d, S.get(path), S.get('relayout:' + path), palb)
        rom.files[fid] = rez(nd, comp)
        n += 1
    for path, fid in ids.items():                       # 놀이 방법 머리글 48
        if '/mgentryphase/ja/sousa_' in path:
            d, comp = unz(rom.files[fid])
            rom.files[fid] = rez(pudsousa.patch(d), comp)
            n += 1
    return n


def card_maps():
    sys.path.insert(0, WORK)
    from card_words_ko import NAMES, SKILLS, GFX_SHORT
    return NAMES, SKILLS, GFX_SHORT


def patch_cards(rom, ids):
    rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(WORK, 'card_ko.tsv'), encoding='utf-8')][1:]
    tr = {cardbin.unesc(jp): cardbin.unesc(ko) for _, jp, ko in rows}
    for path in ('romdata/PUD/card/card.bin.z', 'romdata/PUD/card/ja/card.bin.z'):
        fid = ids[path]
        d, comp = unz(rom.files[fid])
        h, recs, pools = cardbin.parse(d)
        m = {(p, o): tr[s] for p in cardbin.POOLS for o, s in pools[p].items() if s in tr}
        miss = [s for p in cardbin.POOLS for o, s in pools[p].items() if s and s not in tr]
        assert not miss, '번역 없는 카드 문구 %d개: %r' % (len(miss), miss[:3])
        rom.files[fid] = rez(cardbin.build(d, m), comp)
    NAMES, SKILLS, SHORT = card_maps()
    ids_map = {}
    for path in ('romdata/PUD/card/card.bin.z', 'romdata/PUD/card/ja/card.bin.z'):
        d, _ = unz(ROM_ORIG_FILES[path])
        h, recs, pools = cardbin.parse(d)
        ids_map.update({'%04d' % r[0]: (pools['name'].get(r[2]), pools['skill'].get(r[3])) for r in recs})

    def sk(s):
        kai = s.endswith('･改') or s.endswith('・改')
        b = s[:-2] if kai else s
        return SKILLS[b] + ('·개' if kai else '')
    n = 0
    for path, fid in ids.items():
        if '/PUD/card/ja/name_' not in path:
            continue
        nm, s = ids_map[path[-11:-7]]
        g, comp = unz(rom.files[fid])
        rom.files[fid] = rez(cardname.render(g, NAMES[nm], SHORT.get(sk(s), sk(s))), comp)
        n += 1
    return set(c for _, _, ko in rows for c in cardbin.unesc(ko) if 0xAC00 <= ord(c) <= 0xD7A3), n


ROM_ORIG_FILES = {}


def patch_font(rom, ids, used):
    fid = ids['romdata/PUD/font/font.nftr']
    orig = bytes(rom.files[fid])
    f = nftr.Nftr(orig)
    G, asc = bdf.load(GALMURI9)
    items = []
    for ch in sorted(used):
        arr, adv = bdf.render(G, asc, ord(ch), f.cw, f.ch, 10)
        bits = ''.join(str(v) for row in arr for v in row)
        bits += '0' * (-len(bits) % 8)
        bm = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
        items.append((ord(ch), bm + bytes(f.tsize - len(bm)), (0, 9, 10)))
    keep = set(open(os.path.join(WORK, 'pud_keep_kanji.txt'), encoding='utf-8').read())
    nftr.replace_kanji(f, items, keep)
    out = f.build()
    assert len(out) == len(orig), '카드 게임 글꼴 크기가 바뀜'
    rom.files[fid] = out
    return len(items)


def patch_pud(rom, ids):
    for p in ('romdata/PUD/card/card.bin.z', 'romdata/PUD/card/ja/card.bin.z'):
        ROM_ORIG_FILES[p] = bytes(rom.files[ids[p]])
    g = patch_graphics(rom, ids)
    used, cn = patch_cards(rom, ids)
    nf = patch_font(rom, ids, used)
    print('  카드 게임: 그림 %d 파일 · 카드 이름 그림 %d · card.bin 2 · 글꼴 한글 %d자' % (g, cn, nf))
