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


# 오버레이 2(카드 게임·무선 대전 코드) 안의 UTF-16 문자열 — 제자리(원래 길이 안, 나머지 0 채움). 끝 NUL 까지 맞춰 찾는다.
# (2026-09-25 실기: 무선 대전 캐릭터 선택 이름판이 일본어 — charactertext 와 별개인 코드 속 사본)
OV2_STRINGS = [
    ('メーア', '메아'), ('シロマ', '시로마'), ('鉄巨人', '철거인'), ('チョコボ', '초코보'), ('ドルくん', '돌 군'),
    ('ゴーレム', '골렘'), ('サハギン', '사하긴'), ('フレイア', '프레이아'), ('ベヒーモス', '베히모스'),
    ('ヒーローＸ', '히어로Ｘ'), ('チョッカーズ', '초커즈'), ('Mr.モーグリ', 'Mr.모그리'),
    ('『ルールがめん』へもどります。', '『룰 화면』으로 돌아가요.'),
    ('ちゃふー', '차후～'), ('ぎにゃーぶにゃー', '기냐～부냐～'),
    ('けんさくちゅう', '검색 중'), ('けんさくちゅう.', '검색 중.'), ('けんさくちゅう..', '검색 중..'), ('けんさくちゅう...', '검색 중...'),
    ('ぼしゅうちゅう', '모집 중'), ('ぼしゅうちゅう.', '모집 중.'), ('ぼしゅうちゅう..', '모집 중..'), ('ぼしゅうちゅう...', '모집 중...'),
    ('れんしゅうデッキ', '연습 덱'), ('しょきゅうデッキ', '초급 덱'),
]


def patch_ov2(rom):
    ov = rom.loadArm9Overlays()[2]
    assert not ov.compressed
    d = bytearray(rom.files[ov.fileID])
    n = 0
    for jp, ko in OV2_STRINGS:
        a = jp.encode('utf-16-le') + b'\0\0'
        b = ko.encode('utf-16-le') + b'\0\0'
        assert len(b) <= len(a), '%s → %s 길이 넘침' % (jp, ko)
        hits = [i for i in range(len(d) - len(a)) if i % 2 == 0 and d[i:i + len(a)] == a and d[i - 2:i] in (b'\0\0', b'\xff\x7f')] \
            if False else []
        i = d.find(a)
        while i >= 0:
            if i % 2 == 0:
                d[i:i + len(a)] = b + bytes(len(a) - len(b))
                n += 1
            i = d.find(a, i + 2)
    rom.files[ov.fileID] = bytes(d)
    return n, {c for _, ko in OV2_STRINGS for c in ko if 0xAC00 <= ord(c) <= 0xD7A3}


# 카드 게임 이름·덱 이름 입력 자판(PUD/skb/skbdat.skb = UTF-16 표, 쪽마다 60글자: 키 51 + 제어) — 가나만 한글로(사용자 2026-09-25).
# 쪽: 0 히라가나 · 60 히라가나 작은 글자 · 120 가타카나 · 180 가타카나 작은 글자 (゛゜、。ー 키는 그대로)
# 히라가나 = ㅏㅣㅡㅔㅗ 오십음 자리(가기그게고…) · 가타카나 = 거센소리·된소리 등. 「하스피」(は·す·ヒ)는 반드시 칠 수 있게.
SKB_KANA_HIRA = 'あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん'
SKB_KANA_KATA = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン'
SKB_HIRA_KO = '아이으에오가기그게고사시스세소다디드데도나니느네노하히흐헤호마미므메모야유요라리르레로와우응'
SKB_KATA_KO = '어여우유애카키크케코자지즈제조타티트테토차치츠체초파피프페포바비브베보예요위까따빠싸짜왜의은'


def patch_skb(rom, ids):
    fid = ids['romdata/PUD/skb/skbdat.skb']
    t = list(bytes(rom.files[fid]).decode('utf-16-le'))
    t0 = list(t)                                       # 원본(작은 글자 쪽의 자리 기준)
    assert len(SKB_HIRA_KO) == len(SKB_KANA_HIRA) and len(SKB_KATA_KO) == len(SKB_KANA_KATA)
    n = 0
    for base, kana, ko in ((0, SKB_KANA_HIRA, SKB_HIRA_KO), (60, SKB_KANA_HIRA, SKB_HIRA_KO),
                           (120, SKB_KANA_KATA, SKB_KATA_KO), (180, SKB_KANA_KATA, SKB_KATA_KO)):
        norm = ''.join(t0[:51]) if base < 120 else ''.join(t0[120:171])     # 작은 글자 쪽도 보통 쪽 자리로 맞춤
        keys = [c for c in norm if c not in '゛゜、。ー']
        slots = [k for k, c in enumerate(norm) if c not in '゛゜、。ー']
        assert ''.join(keys) == kana, (base, ''.join(keys))
        for k, c in zip(slots, ko):
            t[base + k] = c
            n += 1
    rom.files[fid] = ''.join(t).encode('utf-16-le')
    assert all(c in SKB_HIRA_KO + SKB_KATA_KO for c in '하스피')   # 사용자 이름「하스피」
    return n, set(SKB_HIRA_KO) | set(SKB_KATA_KO)


GALMURI7 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri7.bdf'


def patch_cardfont(rom, ids, used):
    """카드 설명·대전 칸의 8×8 카드 글꼴(PUD/card/cardfont.nftr.z) — 한자 칸을 한글(갈무리7)로. 원래 한글이 없어 설명이 빈칸으로 나왔다(실기 2026-09-25)."""
    p = 'romdata/PUD/card/cardfont.nftr.z'
    fid = ids[p]
    d, comp = unz(rom.files[fid])
    f = nftr.Nftr(d)
    G, asc = bdf.load(GALMURI7)
    items = []
    for ch in sorted(used):
        arr, adv = bdf.render(G, asc, ord(ch), f.cw, f.ch, 7)   # 원래 글자처럼 0‥6행(기준선 asc=9 를 쓰면 2‥8행 → 아래 잘림, 실기 2026-09-25)
        bits = ''.join(str(v) for row in arr for v in row)
        bits += '0' * (-len(bits) % 8)
        bm = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
        w = max([x + 1 for row in arr for x, v in enumerate(row) if v] or [f.cw])
        items.append((ord(ch), bm + bytes(f.tsize - len(bm)), (0, w, w + 1)))
    nftr.replace_kanji(f, items)
    out = f.build()
    assert len(out) == len(d), '카드 글꼴 크기가 바뀜'
    rom.files[fid] = rez(out, comp)
    return len(items)


def patch_pud(rom, ids):
    for p in ('romdata/PUD/card/card.bin.z', 'romdata/PUD/card/ja/card.bin.z'):
        ROM_ORIG_FILES[p] = bytes(rom.files[ids[p]])
    g = patch_graphics(rom, ids)
    used, cn = patch_cards(rom, ids)
    import pudtext                                   # 카드 게임 글(튜토리얼·그림책 설명·대전 로그·Wi-Fi·덱…) — work/ko_pud
    used |= pudtext.apply(rom, ids)
    n2, u2 = patch_ov2(rom)                           # 오버레이 2 UTF-16 문자열(캐릭터 이름·덱 이름 등)
    used |= u2
    n3, u3 = patch_skb(rom, ids)                      # 이름·덱 이름 입력 자판(가나 → 한글)
    used |= u3
    print('  카드 게임: 입력 자판 가나 %d칸 → 한글' % n3)
    nf = patch_font(rom, ids, used)
    ncf = patch_cardfont(rom, ids, used)              # 카드 설명 8×8 글꼴
    print('  카드 게임: 오버레이 2 문자열 %d곳 · 카드 글꼴 한글 %d자' % (n2, ncf))
    print('  카드 게임: 그림 %d 파일 · 카드 이름 그림 %d · card.bin 2 · 글꼴 한글 %d자' % (g, cn, nf))
