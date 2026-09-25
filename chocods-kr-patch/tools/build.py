# -*- coding: utf-8 -*-
r"""시드와 초코보 DS+ 한글 빌드

  python tools/build.py <번역.tsv|번역 폴더(work/ko)> <출력.nds|--dry>

번역 TSV: 파일<TAB>txtbin 안쪽 경로<TAB>번호<TAB>번역  또는 머리줄 「@<TAB>파일<TAB>안쪽 경로」 아래 「번호<TAB>번역」  ( \n 줄바꿈 · {ESC}=0x1B · {13}=0x13 쪽 끝 · {XX}=바이트 )
처리: 원본 md5 확인 → 파일마다 LZ 해제 → FBC 펼쳐 txtbin 문자열 교체(인코딩은 그 txtbin 원래 것: UTF-8/Shift-JIS)
      → FBC 다시 조립 → LZ11 재압축 → NitroFS 교체(ndspy) · 글꼴 dsr_fnt 에 갈무리9 한글 덧붙임.
"""
import glob
import hashlib
import os
import re
import struct
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import areagfx, base16, bgwords, minamegfx, bdf, dgnbanner, fbc, gearlogo, jobname, josa, popupgfx, hudlabel, labelgfx, logoimg, lz11, ncer, nftr, sjiskr, titlegfx, titletext
from PIL import Image
import ndspy.rom, ndspy.lz10

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIG = r'C:\claude\roms\nds\Cid to Chocobo no Fushigi na Dungeon - Toki Wasure no Meikyuu DS+ (Japan).nds'
ORIG_MD5 = '97f8e08589adc30f4f026b64b88b5d48'
FONT_PATH = 'romdata/FONT/dsr_fnt.NFTR'
HUD_PATH = 'romdata/UI/UPSSTAT/ui_common.FBC.z'
GALMURI9 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri9.bdf'
LOGO_PNG = os.path.join(ROOT, 'work', 'logo', 'v13.png')          # 사용자 확정 한글 로고(docs §12)


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def unesc(s):
    s = s.replace(chr(92) + 'n', '\n').replace('{ESC}', '\x1b').replace('{13}', '\x13')
    return re.sub(r'\{([0-9A-Fa-f]{2})\}', lambda m: chr(int(m.group(1), 16)), s)


def squeeze(s):
    """부호 뒤 공백은 무조건 지운다(전프로젝트 규칙) — 한글이 든 줄만."""
    if not any(0xAC00 <= ord(c) <= 0xD7A3 for c in s):
        return s
    return re.sub(r'([,.!?:;]) +', lambda m: m.group(1), s)


def read_tsv(path):
    """번역 TSV 하나 또는 폴더(안의 *.tsv 전부, 이름 순)"""
    rows = defaultdict(lambda: defaultdict(dict))
    paths = sorted(glob.glob(os.path.join(path, '*.tsv'))) if os.path.isdir(path) else [path]
    for p in paths:
        cur = None
        for line in open(p, encoding='utf-8'):
            line = line.rstrip('\n')
            if not line or line.startswith('#'):
                continue
            cols = line.split('\t')
            if cols[0] == '@':                    # 머리줄 「@ 파일 안쪽경로」 → 아래 줄은 「번호 번역」
                cur = cols[1:3]
                continue
            f, inner, idx, ko = cols if len(cols) == 4 else cur + cols
            rows[f][inner][int(idx)] = squeeze(josa.expand(unesc(ko)))
    return rows


def unz(d):
    if d[0] == 0x11:
        return lz11.decompress(d), 'lz11'
    if d[0] == 0x10:
        return ndspy.lz10.decompress(d), 'lz10'
    raise ValueError('압축 머리 %02x' % d[0])


def patch_fbc(d, repl, prefix=''):
    """repl: {안쪽 경로: {번호: 문자열}} → 새 FBC. 쓴 경로를 repl 에서 지운다."""
    new = []
    for name, b in fbc.entries(d):
        path = prefix + name
        if b[:4] == b'\x14\x00\x06\x00':
            b = patch_fbc(b, repl, path + '/')
        elif path in repl:
            strs = fbc.txtbin(b)
            enc = fbc.guess_enc(strs)
            enc = 'utf-8' if enc == 'ascii' else enc
            for idx, text in repl.pop(path).items():
                assert idx < len(strs), '%s %d 번호 없음' % (path, idx)
                strs[idx] = sjiskr.encode(text) if enc == 'cp932' else text.encode(enc)   # SJIS 한글 = 변환 표 배정 코드
            b = fbc.txtbin_build(strs)
        new.append((name, b))
    return fbc.build(new)


def replace_nested(d, repl, prefix=''):
    """중첩 FBC 에서 {경로: 새 바이트} 교체 → 새 FBC. 쓴 경로는 repl 에서 지운다."""
    new = []
    for name, b in fbc.entries(d):
        path = prefix + name
        if path in repl:
            b = repl.pop(path)
        elif b[:4] == b'\x14\x00\x06\x00':
            b = replace_nested(b, repl, path + '/')
        new.append((name, b))
    return fbc.build(new)


def patch_gfx(rom, ids, dsr):
    """그림 글자: 타이틀 안내문·타이틀 메뉴·아이템 메뉴·스테이터스·타이틀 로고"""
    def edit(path, fn):
        fid = ids[path]
        d = lz11.decompress(rom.files[fid])
        repl = fn(dict(fbc.walk(d)))
        left = dict(repl)
        nd = replace_nested(d, left)
        assert not left, '못 찾은 안쪽 경로 %s' % list(left)
        c = lz11.compress(nd)
        assert lz11.decompress(c) == nd
        rom.files[fid] = c
        print('  %s  그림 %s' % (path, ', '.join(sorted(repl))))

    def by_ext(ents, ext):
        return next((k, v) for k, v in ents.items() if k.endswith('.' + ext))

    def ui_text(ents):
        (kc, c), (kb, b) = by_ext(ents, 'NCER'), by_ext(ents, 'NCBR')
        nc, nb, _ = titletext.build(c, b, dsr)
        return {kc: nc, kb: nb}

    def ui_title(ents):
        (kc, c), (kb, b) = by_ext(ents, 'NCER'), by_ext(ents, 'NCBR')
        nc, nb, _ = titlegfx.build(c, b, dsr)
        return {kc: nc, kb: nb}

    def labels(path):
        def fn(ents):
            (kc, c), (kg, g) = by_ext(ents, 'NCER'), by_ext(ents, 'NCGR')
            ng, done = labelgfx.apply(path, c, g)
            assert done
            return {kg: ng}
        return fn


    edit('romdata/UI/TM/ui_text.FBC.z', ui_text)
    edit('romdata/UI/TM/ui_title.FBC.z', ui_title)
    edit(labelgfx.ITEM, labels(labelgfx.ITEM))
    edit(labelgfx.DGN, labels(labelgfx.DGN))
    edit(labelgfx.CLOAK, labels(labelgfx.CLOAK))
    edit(labelgfx.KAIZO, labels(labelgfx.KAIZO))
    def popup(e):
        kc = next(k for k in e if k.endswith('.NCER')); kb = next(k for k in e if k.endswith('.NCBR'))
        nc, nb = popupgfx.build(e[kc], e[kb])
        return {kc: nc, kb: nb}
    edit('romdata/UI/DMGCNTR/num_counter.FBC.z', popup)      # 상태 변화 팝업
    cid_scrs = []                                            # 바탕 UI 낱말(bg_base_cid 타일)
    for p in ids:
        if p.startswith('romdata/UI/') and p.endswith('_cid.FBC.z') and 'BASEUI' not in p:
            cid_scrs += [b for b in dict(fbc.walk(lz11.decompress(rom.files[ids[p]]))).values() if b[:4] == b'RCSN']

    def bgw(e):
        g = e['bg_base_cid.NCGR']
        for tmpl, vars_, region, lines, erase, bgf in bgwords.JOBS:
            js0 = [b for b in dict(fbc.walk(lz11.decompress(rom.files[ids[tmpl.format(v='cid')]]))).values() if b[:4] == b'RCSN'][0]
            js = [x for x in cid_scrs if x == js0][0]
            g = bgwords.patch(g, cid_scrs, js, region, lines, erase, bgf)
        return {'bg_base_cid.NCGR': g}
    edit('romdata/UI/BASEUI/bg_base_cid.FBC.z', bgw)
    for path, (unit, names) in minamegfx.FILES.items():      # 필드 지도 지명
        def mn(e, unit=unit, names=names):
            kc = next(k for k in e if k.endswith('.NCER')); kb = next(k for k in e if k.endswith('.NCBR'))
            nc, nb = minamegfx.build(e[kc], e[kb], unit, names, titletext.Font(dsr))
            return {kc: nc, kb: nb}
        edit(path, mn)
    for key, text in areagfx.NAMES.items():                  # 필드 지역 이름
        edit('romdata/UI/AREANAME/area_%s.FBC.z' % key,
             lambda e, text=text: {next(k for k in e if k.endswith('.NCGR')):
                                   areagfx.build(next(v for k, v in e.items() if k.endswith('.NCER')),
                                                 next(v for k, v in e.items() if k.endswith('.NCGR')), text)})
    font = titletext.Font(dsr)
    for path in sorted(p for p in ids if p.startswith('romdata/UI/JOBCFACE/')):   # 스테이터스 창 직업명 그림
        key = path.split('/')[-1].split('.')[0]
        kind, job = key.split('_', 1)
        text = jobname.JOBS.get(job) or ('히어로X' if key == 'jobico_noname' else None)   # jobico2_noname = 「????」
        if not text:
            continue
        edit(path, lambda e, text=text: {next(k for k in e if k.endswith('.NCGR')):
                                         jobname.patch(next(v for k, v in e.items() if k.endswith('.NCER')),
                                                       next(v for k, v in e.items() if k.endswith('.NCGR')), font, text)})
    for n, name in enumerate(dgnbanner.NAMES):          # 던전 입장 이름 33개 — 원본 판 크기 안(assert)
        def banner(e, name=name, n=n):
            kc = next(k for k in e if k.endswith('.NCER'))
            kb = next(k for k in e if k.endswith('.NCBR'))
            nc, nb, w0, w = dgnbanner.rebuild(e[kc], e[kb], font, name)
            assert len(nb) == len(e[kb])
            return {kc: nc, kb: nb}
        edit('romdata/UI/DGNFLOOR/DGN_%02d.FBC.z' % n, banner)

    # 파일 선택 로고(base_16) + 도는 톱니(gear_16) — 타이틀에서도 톱니 스프라이트가 로고를 덮는다
    logo_img = Image.open(LOGO_PNG).convert('RGB')
    orig_img = orig_logo_image(rom, ids)

    def pal_of(path):
        return ncer.nclr(list(dict(fbc.walk(lz11.decompress(rom.files[ids[path]]))).values())[0])
    gp = pal_of('romdata/UI/CMN/gear_16.FBC.z')
    bp = pal_of('romdata/UI/CMN/base_16.FBC.z')
    gents = dict(fbc.walk(lz11.decompress(rom.files[ids['romdata/UI/TM/gear_16.FBC.z']])))
    gmask = gearlogo.gear_mask(gents['gear_16.NCER'], gents['gear_16.NCGR'], gp)
    edit('romdata/UI/TM/gear_16.FBC.z',
         lambda e: {'gear_16.NCGR': gearlogo.patch_gear(e['gear_16.NCER'], e['gear_16.NCGR'], gp, logo_img)})

    # 로고 판: 팔레트 0‥13 새로 뽑고 칸 전부 다시(원본 팔레트 억지 맞춤은 부제가 뭉개졌다 — PoC-2b), 칸 수 284 → 문자 영역 확장
    bents = dict(fbc.walk(lz11.decompress(rom.files[ids['romdata/UI/TM/base_16.FBC.z']])))
    cents = dict(fbc.walk(lz11.decompress(rom.files[ids['romdata/UI/CMN/base_16.FBC.z']])))
    ckey, pl = next(iter(cents.items()))
    bpal = logoimg._pal(pl)
    orig_base = render4(bents['base_16.NSCR'], bents['base_16.NCGR'], bpal)
    ns, nc, npl, ntile, merged = base16.rebuild(bents['base_16.NSCR'], bents['base_16.NCGR'], pl, logo_img, gmask, orig_base)
    assert not merged
    edit('romdata/UI/TM/base_16.FBC.z', lambda e: {'base_16.NSCR': ns, 'base_16.NCGR': nc})
    edit('romdata/UI/CMN/base_16.FBC.z', lambda e: {ckey: npl})
    print('    base_16 타일 %d' % ntile)
    # 타이틀 로고(tl_ue) = 파일 선택 화면과 똑같은 그림(로고 판 + 톱니 0프레임) — 사용자 «아예 밑에걸로 처음 그림도»
    comp = render4(ns, nc, logoimg._pal(npl))
    gents2 = dict(fbc.walk(lz11.decompress(rom.files[ids['romdata/UI/TM/gear_16.FBC.z']])))
    comp = gearlogo.overlay_gear(comp, gents2['gear_16.NCER'], gents2['gear_16.NCGR'], gp, 0)
    comp.save(os.path.join(ROOT, 'work', 'logo', 'title_from_fileselect.png'))

    def logo(ents):
        p = 'tl_ue.fbc/TITLE_UE.'
        s2, g2, n = logoimg.replace(ents[p + 'NSCR'], ents[p + 'NCGR'], ents[p + 'NCLR'], comp)
        return {p + 'NSCR': s2, p + 'NCGR': g2}
    edit('romdata/TL/TL.FBC.z', logo)


def render4(nscr, ncgr, pal):
    """4bpp BG → RGB 256×192, 투명(0) 은 흰 바탕"""
    import gfxdump
    d, bpp = gfxdump.ncgr_tiles(ncgr)
    im = gfxdump.render_scr(nscr, d, bpp, pal).crop((0, 0, 256, 192))
    px = im.load()
    si = nscr.index(b'NRCS')
    m = struct.unpack_from('<1024H', nscr, si + 0x14)
    for ty in range(24):
        for tx in range(32):
            e = m[ty * 32 + tx]
            t, hf, vf = e & 0x3ff, (e >> 10) & 1, (e >> 11) & 1
            for y in range(8):
                for x in range(8):
                    xx, yy = (7 - x if hf else x), (7 - y if vf else y)
                    b = d[t * 32 + yy * 4 + xx // 2]
                    if not (b >> (4 * (xx & 1))) & 15:
                        px[tx * 8 + x, ty * 8 + y] = (248, 248, 248)
    return im


def orig_logo_image(rom, ids):
    """원본 tl_ue 렌더(RGB) — base_16 에서 «바뀐 블록» 판정 기준"""
    ents = dict(fbc.walk(lz11.decompress(rom.files[ids['romdata/TL/TL.FBC.z']])))
    p = 'tl_ue.fbc/TITLE_UE.'
    idx = logoimg.index_image(ents[p + 'NSCR'], ents[p + 'NCGR'])
    pal = logoimg._pal(ents[p + 'NCLR'])
    im = Image.new('RGB', (len(idx[0]), len(idx)))
    im.putdata([pal[v] for r in idx for v in r])
    return im


# 오버레이 0 안 SJIS 기본값(새 게임 때 세이브로 복사) — 원문 바이트 길이 안에서 제자리
OV0_STRINGS = [('すっぴん', '스핑'), ('炎の守護者', '불의수호자')]


def patch_ov0(rom):
    ovs = rom.loadArm9Overlays()
    ov = ovs[0]
    assert not ov.compressed
    d = bytearray(rom.files[ov.fileID])
    for jp, ko in OV0_STRINGS:
        a = jp.encode('cp932')
        i = d.find(a + b'\0')
        assert i > 0 and d.find(a + b'\0', i + 1) < 0, jp
        b = sjiskr.encode(ko)
        assert len(b) <= len(a), '%s → %s 길이 %d > %d' % (jp, ko, len(b), len(a))
        d[i:i + len(a)] = b + bytes(len(a) - len(b))
        print('  ov0 0x%X  %s → %s' % (ov.ramAddress + i, jp, ko))
    rom.files[ov.fileID] = bytes(d)


def hangul_set():
    out = []
    for hi in range(0xB0, 0xC9):
        for lo in range(0xA1, 0xFF):
            out.append(bytes((hi, lo)).decode('cp949'))
    return out


FONT_GROW_MAX = 2000   # SYS 힙(149,448 B) 여유가 원본 실행 중 4,416 B 뿐 → 글꼴은 이만큼만 늘릴 수 있다(docs §9)


def build_font(orig, used):
    f = nftr.Nftr(orig)
    G, asc = bdf.load(GALMURI9)
    n = 0
    items = []
    for ch in sorted(used):
        arr, adv = bdf.render(G, asc, ord(ch), f.cw, f.ch, 10)   # 가나처럼 1‥9 행
        bits = ''.join(str(v) for row in arr for v in row)
        bits += '0' * (-len(bits) % 8)
        bm = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
        bm = bm + bytes(f.tsize - len(bm))
        items.append((ord(ch), bm, (0, 9, 10)))
    items.append((josa.NULL, bytes(f.tsize), (0, 0, 0)))   # 조사 «없음» = 폭 0 빈 글리프
    n = nftr.replace_kanji(f, items)          # 한자 칸을 한글로 갈아 끼움(글꼴 크기 불변)
    out = f.build()
    assert len(out) - len(orig) <= FONT_GROW_MAX, '글꼴이 %d B 늘어남 — SYS 힙 한도 초과' % (len(out) - len(orig))
    return out, n


def main():
    tsv, out = sys.argv[1], sys.argv[2]
    assert md5(ORIG) == ORIG_MD5, '원본 md5 불일치'
    rom = ndspy.rom.NintendoDSRom.fromFile(ORIG)
    ids = {}

    def walk(folder, pre=''):
        for i, name in enumerate(folder.files):
            ids[pre + name] = folder.firstID + i
        for name, sub in folder.folders:
            walk(sub, pre + name + '/')
    walk(rom.filenames)
    rows = read_tsv(tsv)
    for path, repl in rows.items():
        fid = ids[path]
        d = rom.files[fid]
        comp = None
        if path.endswith('.z'):
            d, comp = unz(d)
        nd = patch_fbc(d, repl)
        assert not repl, '못 찾은 안쪽 경로 %s' % list(repl)
        if comp:
            nd = lz11.compress(nd)
            assert lz11.decompress(nd) == patch_fbc(unz(rom.files[fid])[0], read_tsv(tsv)[path])
        rom.files[fid] = nd
        print('  %s  %d → %d B' % (path, len(rom.files[fid]) if False else len(d), len(nd)))
    rom.arm9 = sjiskr.patch_arm9(rom.arm9)        # SJIS→유니코드 표의 한자 칸 2,350 개 = 한글
    rom.arm9, hook, hlen = josa.patch_arm9(rom.arm9)   # 조사 자동 선택 훅(글리프 번호 함수)
    print('  ARM9 조사 훅 0x%X (%d B)' % (hook, hlen))
    print('  ARM9 SJIS 변환 표 한글 %d칸' % len(sjiskr.SLOT))
    fid = ids[HUD_PATH]                           # 위 화면 HUD 그림 글자(チョコボ·おなか)
    d = lz11.decompress(rom.files[fid])
    ents = fbc.entries(d)
    assert fbc.build(ents) == d
    ncer_b = next(b for n, b in ents if n.endswith('.NCER'))
    ents = [(n, hudlabel.patch_ui_common(b, ncer_b) if n.endswith('.NCGR') else b) for n, b in ents]
    rom.files[fid] = lz11.compress(fbc.build(ents))
    print('  %s  그림 글자 %s' % (HUD_PATH, ' · '.join(h[2] for h in hudlabel.HUD)))
    patch_ov0(rom)
    patch_gfx(rom, ids, rom.files[ids[FONT_PATH]])   # 원본 글꼴(dsr)로 그림 글자 조판 — 한글은 갈무리9
    import chaptitle                                 # 장 제목 그림 6(evt_title_0N)
    print('  장 제목 그림 %d 파일' % chaptitle.patch_rom(rom, ids, replace_nested))
    import pudbuild                                  # 카드 게임(PUD): 그림·카드 표·카드 게임 글꼴
    pudbuild.patch_pud(rom, ids)
    fid = ids[FONT_PATH]
    used = {c for r in read_tsv(tsv).values() for m in r.values() for t in m.values() for c in t if 0xAC00 <= ord(c) <= 0xD7A3}
    used |= {c for pr in josa.PAIRS for c in pr if c}      # 조사 글자는 늘 넣는다
    missing = used - set(hangul_set())
    assert not missing, 'KS X 1001 밖 음절 %s' % ''.join(sorted(missing))
    font, n = build_font(rom.files[fid], used)
    print('  글꼴 %s +%d자  %d → %d B' % (FONT_PATH, n, len(rom.files[fid]), len(font)))
    rom.files[fid] = font
    if out == '--dry':                            # 예행: 모든 변환·검사만 하고 ROM 은 안 쓴다
        print('예행 완료(ROM 안 씀)')
        return
    rom.saveToFile(out)
    full = os.path.getsize(ORIG)                  # 원본은 0xFF 로 128 MB 까지 채워져 있다 → 같은 크기로
    cur = os.path.getsize(out)
    assert cur <= full, 'ROM 이 원본 용량(%d)을 넘음: %d' % (full, cur)
    with open(out, 'ab') as fo:
        fo.write(b'\xff' * (full - cur))
    print('완료 %s  (사용 %d / %d B)  md5 %s' % (out, cur, full, md5(out)))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
