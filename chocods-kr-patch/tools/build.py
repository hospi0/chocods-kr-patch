# -*- coding: utf-8 -*-
r"""시드와 초코보 DS+ 한글 빌드

  python tools/build.py <번역.tsv|번역 폴더(work/ko)> <출력.nds|--dry>

번역 TSV: 파일<TAB>txtbin 안쪽 경로<TAB>번호<TAB>번역  또는 머리줄 「@<TAB>파일<TAB>안쪽 경로」 아래 「번호<TAB>번역」  ( \n 줄바꿈 · {ESC}=0x1B · {13}=0x13 쪽 끝 · {XX}=바이트 )
처리: 원본 md5 확인 → 파일마다 LZ 해제 → FBC 펼쳐 txtbin 문자열 교체(인코딩은 그 txtbin 원래 것: UTF-8/Shift-JIS)
      → FBC 다시 조립 → LZ11 재압축 → NitroFS 교체(ndspy) · 글꼴 dsr_fnt 에 갈무리9 한글 덧붙임.
한글 코드: 쓰는 음절만 U+F000‥ 으로 옮겨 적는다(josa.assign) — UTF-8 대사·SJIS 변환 표·조사 훅·글꼴(방식 0 한 블록)이 같은 코드.
글꼴: 한자 전부 + 가나(--kana all: 남김 / text: 번역 안 한 글에 남은 가나만 남김)를 글리프째 빼고 한글을 붙인다(nftr.rebuild).
  python tools/build.py work/ko --dry [--kana all|text]
"""
import glob
import hashlib
import os
import re
import struct
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import areagfx, base16, bgwords, exitlabel, minamegfx, bdf, dgnbanner, fbc, gearlogo, jobname, josa, popupgfx, hudlabel, labelgfx, logoimg, lz11, ncer, nftr, sjiskr, titlegfx, titletext
from PIL import Image
import ndspy.rom, ndspy.lz10

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIG = r'C:\claude\roms\nds\Cid to Chocobo no Fushigi na Dungeon - Toki Wasure no Meikyuu DS+ (Japan).nds'
ORIG_MD5 = '97f8e08589adc30f4f026b64b88b5d48'
FONT_PATH = 'romdata/FONT/dsr_fnt.NFTR'
TEXT_REMAP = {}          # 한글 → 사용자 영역 코드 글자(main 에서 josa.assign 으로 채움) — UTF-8 txtbin 에만
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
                strs[idx] = sjiskr.encode(text) if enc == 'cp932' else remap_text(text).encode(enc)   # SJIS 한글 = 변환 표 배정 코드
            b = fbc.txtbin_build(strs)
        new.append((name, b))
    return fbc.build(new)


def remap_text(text):
    return ''.join(TEXT_REMAP.get(c, c) for c in text)


KBD_PATH = 'romdata/UI/KBD/kbdmap.FBC.z'
# 자판 칸 글자는 글꼴(dsr_fnt)로 그린다(그림 아님 — 2026-09-25 실기 확인). kbdmap = BOM + UTF-16 칸 글자.
# 합언어 정답(work/ko/40_password.tsv)의 한글 음절 전부 + 이름용 흔한 음절(KBD_FILL, 글꼴에 있는 것만)을 가나다순으로
# 히라가나 50 → 가타카나 50 → 그림 문자 쪽 그림 칸(U+E0xx·п Ф ┗) → 기호 쪽(정답에 쓰는 KBD_SIGN_KEEP 빼고) 순서로 채운다.
# (실기 2026-09-25 시험: kbdmap 에 한글(TEXT_REMAP 코드)을 넣으면 칸에 나오고 정답 비교도 그대로 통과)
# 그림 문자 쪽 U+E000‥E006 은 조사 표지(josa)와 겹쳐 조사 글리프가 뜨던 자리 — 이 칸들도 한글 칸이 된다.
KBD_FILL = '가나다라마바사아자차카타파하준민수현연윤혜진성훈경빈솔키토쿠포그미유예슬서지호우은영주선희'
KBD_SIGN_KEEP = set('！？&「」↓…')
KBD_PICTO_SLOT = lambda c: 0xE000 <= ord(c) <= 0xE0FF or c in 'пФ┗'


def patch_kbd(rom, ids):
    pw = read_tsv(os.path.join(ROOT, 'work', 'ko', '40_password.tsv'))
    need = sorted({c for r in pw.values() for m in r.values() for t in m.values() for c in t if 0xAC00 <= ord(c) <= 0xD7A3})
    fid = ids[KBD_PATH]
    d, comp = unz(rom.files[fid])
    ents = fbc.entries(d)
    maps = {name: list(b[2:].decode('utf-16-le')) for name, b in ents if name.endswith('.kbdmap')}
    slots = [('jp_hiragana.kbdmap', k) for k in range(len(maps['jp_hiragana.kbdmap']))]
    slots += [('jp_katakana.kbdmap', k) for k in range(len(maps['jp_katakana.kbdmap']))]
    slots += [('picto.kbdmap', k) for k, c in enumerate(maps['picto.kbdmap']) if KBD_PICTO_SLOT(c)]
    slots += [('sign.kbdmap', k) for k, c in enumerate(maps['sign.kbdmap']) if c not in KBD_SIGN_KEEP]
    assert len(need) <= len(slots), '합언어 음절 %d > 자판 칸 %d' % (len(need), len(slots))
    fill = [c for c in KBD_FILL if c not in need and c in TEXT_REMAP]
    freq = defaultdict(int)                            # 그다음은 번역문에 자주 나오는 음절 순
    for f in glob.glob(os.path.join(ROOT, 'work', 'ko', '*.tsv')):
        for ln in open(f, encoding='utf-8'):
            for c in ln:
                if 0xAC00 <= ord(c) <= 0xD7A3:
                    freq[c] += 1
    fill += [c for c in sorted(freq, key=lambda c: -freq[c]) if c not in need and c not in fill and c in TEXT_REMAP]
    syl = sorted(need + fill[:len(slots) - len(need)])
    for (name, k), c in zip(slots, syl):
        maps[name][k] = remap_text(c)
    left = len(slots) - len(syl)
    for name, k in slots[len(syl):]:                   # 남는 칸은 빈칸(가나·그림이 남지 않게)
        maps[name][k] = '　'
    new = []
    for name, b in ents:
        if name in maps:
            nb = b[:2] + ''.join(maps[name]).encode('utf-16-le')
            assert len(nb) == len(b)
            b = nb
        new.append((name, b))
    nd = fbc.build(new)
    rom.files[fid] = lz11.compress(nd) if comp else nd
    print('  %s  자판: 칸 %d = 합언어 음절 %d + 이름용 %d (빈칸 %d)' % (KBD_PATH, len(slots), len(need), len(syl) - len(need), left))


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
    import kbdlabel                                          # 입력 자판 라벨(かな·カナ·゛·゜·小字·きりかえ)
    edit('romdata/UI/KBD/kbdres.FBC.z', lambda e: {'kbd_jp.NCGR': kbdlabel.build(e['kbd_jp.NCGR']),
                                                    'kbd_mark.NCGR': kbdlabel.build(e['kbd_mark.NCGR'], kbdlabel.KIRIKAE)})
    for var in bgwords.VARIANTS:                             # 바탕 UI 낱말(bg_base_<지역> 타일) — 지역판마다
        jobs = [j for j in bgwords.JOBS if var in j[1]]
        if not jobs:
            continue
        scrs = []
        for p in ids:
            if p.startswith('romdata/UI/') and p.endswith('_%s.FBC.z' % var) and 'BASEUI' not in p:
                scrs += [b for b in dict(fbc.walk(lz11.decompress(rom.files[ids[p]]))).values() if b[:4] == b'RCSN']

        def bgw(e, var=var, jobs=jobs, scrs=scrs):
            key = 'bg_base_%s.NCGR' % var
            g = e[key]
            for tmpl, vars_, region, lines, erase, bgf in jobs:
                js0 = [b for b in dict(fbc.walk(lz11.decompress(rom.files[ids[tmpl.format(v=var)]]))).values() if b[:4] == b'RCSN'][0]
                js = [x for x in scrs if x == js0][0]
                g = bgwords.patch(g, scrs, js, region, lines, erase, bgf)
            return {key: g}
        edit('romdata/UI/BASEUI/bg_base_%s.FBC.z' % var, bgw)
    for path, (unit, names) in minamegfx.FILES.items():      # 필드 지도 지명
        def mn(e, unit=unit, names=names):
            kc = next(k for k in e if k.endswith('.NCER')); kb = next(k for k in e if k.endswith('.NCBR'))
            nc, nb = minamegfx.build(e[kc], e[kb], unit, names, titletext.Font(dsr))
            return {kc: nc, kb: nb}
        edit(path, mn)
    xfonts = exitlabel.fonts_for(dsr)
    for path, (unit, linear, span, labels) in exitlabel.FILES.items():   # 필드 출구 표시(필드 맵 ▷ 등)
        def xl(e, unit=unit, linear=linear, span=span, labels=labels):
            kc = next(k for k in e if k.endswith('.NCER')); kb = next(k for k in e if k.endswith(('.NCGR', '.NCBR')))
            nc, nb, _, _ = exitlabel.build(e[kc], e[kb], unit, linear, span, labels, xfonts)
            return {kc: nc, kb: nb}
        edit(path, xl)
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


KANJI = [(0x3400, 0x9FFF), (0xF900, 0xFAFF)]
KANA = [(0x3041, 0x30FA), (0x30FD, 0x30FF), (0xFF66, 0xFF9F)]      # ・(30FB)·ー(30FC) 는 부호로 늘 남김


def in_ranges(c, ranges):
    return any(a <= c <= b for a, b in ranges)


def leftover_text(rows):
    """번역 안 한 본편 글(work/alltext.tsv 중 rows 에 없는 줄, ダミー 빼고)"""
    out = []
    for line in open(os.path.join(ROOT, 'work', 'alltext.tsv'), encoding='utf-8'):
        f = line.rstrip('\n').split('\t')
        if len(f) < 5 or f[4] == 'ダミー':
            continue
        if int(f[2]) not in rows.get(f[0], {}).get(f[1], {}):
            out.append(f[4])
    return out


def glyph_of(G, asc, f, ch):
    arr, adv = bdf.render(G, asc, ord(ch), f.cw, f.ch, 10)   # 가나처럼 1‥9 행
    bits = ''.join(str(v) for row in arr for v in row)
    bits += '0' * (-len(bits) % 8)
    bm = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
    return bm + bytes(f.tsize - len(bm)), (0, 9, 10)


GALMURI7 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri7.bdf'
# 가나 «그림 글리프»(키릴 자리)를 한글 그림으로 다시 그린다 — 직업 화면 라벨(시스템 메시지 320‥346 등)이 이 글자를 쓴다.
# 이 줄들은 글자 칸 윗줄이 가려져서(실기 2026-09-25 「식업」·「직업 변경」 윗도트 잘림) 보통 한글 글리프를 못 쓴다:
#  · г д = 「직」「업」 갈무리7(3‥9행, 「Lv」 아이콘과 같은 높이) — 목록·초상화 아래 「직업Lv」
#  · Ё Ж З И = 「직」「업」「변」「경」 갈무리9 를 가운데 줄 하나 빼고 윗부분을 1도트 내림 — 탭 「직업 변경」
PICTURE_G7 = {'г': '직', 'д': '업'}
PICTURE_G9_DOWN = {'Ё': ('직', 6), 'Ж': ('업', 5), 'З': ('변', 6), 'И': ('경', 6)}   # (글자, 뺄 행)


def _pack10(rows, tsize):
    bits = ''.join('1' if v else '0' for r in rows for v in r[:10])
    bits += '0' * (tsize * 8 - len(bits))
    return bytes(int(bits[k:k + 8], 2) for k in range(0, tsize * 8, 8))


def picture_glyphs(f, G9, asc9):
    G7, asc7 = bdf.load(GALMURI7)
    for code, ch in PICTURE_G7.items():
        arr, adv = bdf.render(G7, asc7, ord(ch), 10, 10, 10)
        w = max(x for r in arr for x, v in enumerate(r) if v) + 1
        i = f.lookup(ord(code))
        f.glyphs[i] = _pack10(arr, f.tsize)
        f.widths[i] = (0, w, w + 1)
    for code, (ch, cut) in PICTURE_G9_DOWN.items():
        arr, adv = bdf.render(G9, asc9, ord(ch), 10, 10, 10)
        assert not any(arr[0]), ch
        rows = [[0] * 10] + arr[:cut] + arr[cut + 1:]            # cut 행을 빼고 그 위를 한 줄 내림
        assert len(rows) == 10
        w = max(x for r in rows for x, v in enumerate(r) if v) + 1
        i = f.lookup(ord(code))
        f.glyphs[i] = _pack10(rows, f.tsize)
        f.widths[i] = (0, w, adv)


def build_font(orig, pua, keep_kana):
    """keep_kana: 남길 가나 코드 집합(None = 전부). → (새 글꼴, 한글 수, 보고 문자열)"""
    remap, a, al, n = pua
    f = nftr.Nftr(orig)
    G, asc = bdf.load(GALMURI9)
    order = sorted(remap, key=remap.get)
    assert [remap[c] for c in order] == list(range(josa.PUA_BASE, josa.PUA_BASE + n))
    glyphs = [glyph_of(G, asc, f, ch) for ch in order]
    codes = nftr.code_map(f)
    drop = {c for c in codes if in_ranges(c, KANJI) or (in_ranges(c, KANA) and keep_kana is not None and c not in keep_kana)}
    dropped, h0, moved = nftr.rebuild(f, drop, josa.PUA_BASE, glyphs, extra=[(josa.NULL, bytes(f.tsize), (0, 0, 0))])
    picture_glyphs(f, G, asc)
    out = f.build()
    per = f.tsize + 3
    room = FONT_GROW_MAX - (len(out) - len(orig))
    msg = '한자·가나 %d자 뺌 · 한글 %d자 · %d → %d B (%+d, 한도 +%d) · 여유 %d B = 한글 약 %d자 %s · 번호 바뀐 글리프 %d' % (
        dropped, n, len(orig), len(out), len(out) - len(orig), FONT_GROW_MAX, room, abs(room) // per,
        '더' if room >= 0 else '넘음', moved)
    return out, n, msg


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
    kana_mode = sys.argv[sys.argv.index('--kana') + 1] if '--kana' in sys.argv else 'all'
    assert kana_mode in ('all', 'text'), kana_mode
    rows = read_tsv(tsv)
    used = {c for r in rows.values() for m in r.values() for t in m.values() for c in t if 0xAC00 <= ord(c) <= 0xD7A3}
    used |= {c for _, ko in OV0_STRINGS for c in ko if 0xAC00 <= ord(c) <= 0xD7A3}
    missing = used - set(hangul_set())
    assert not missing, 'KS X 1001 밖 음절 %s' % ''.join(sorted(missing))
    pua = josa.assign(used)                       # 한글 → U+F000‥ (받침 없음·ㄹ·그 밖 순)
    TEXT_REMAP.update({k: chr(v) for k, v in pua[0].items()})
    left = leftover_text(rows)
    left_kana = {ord(c) for t in left for c in t if in_ranges(ord(c), KANA)}
    left_kanji = sorted({c for t in left for c in t if in_ranges(ord(c), KANJI)})
    if left_kanji:
        print('  ! 번역 안 한 글에 남은 한자 %d자(글꼴에서 빠짐): %s' % (len(left_kanji), ''.join(left_kanji[:40])))
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
    patch_kbd(rom, ids)                               # 이름·합언어 입력 자판(한글 음절 칸 · 그림 문자 쪽 조사 표지 충돌)
    rom.arm9 = sjiskr.patch_arm9(rom.arm9, pua[0])   # SJIS→유니코드 표의 한자 칸 2,350 개 = 한글(옮겨 적은 코드)
    rom.arm9, hook, hlen = josa.patch_arm9(rom.arm9, pua)   # 조사 자동 선택 훅(글리프 번호 함수)
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
    for name in ('DSA_L', 'DSB_U'):                  # 영상 자막(tools/movsub.py 가 만든 work/mov_ko/*.mods)
        p = os.path.join(ROOT, 'work', 'mov_ko', name + '.mods')
        assert os.path.exists(p), '%s 없음 — python tools/movsub.py 먼저' % p
        rom.files[ids['romdata/MOV/%s.mods' % name]] = open(p, 'rb').read()
        print('  romdata/MOV/%s.mods  자막 영상 %d B' % (name, os.path.getsize(p)))
    fid = ids[FONT_PATH]
    orig_font = rom.files[fid]
    results = {}
    for mode, keep in (('all', None), ('text', left_kana)):     # 두 방식 다 재서 보여 준다(쓰는 건 --kana)
        try:
            results[mode] = build_font(orig_font, pua, keep)
            print('  글꼴[가나 %s] %s' % ('전부 남김' if keep is None else '남은 글의 %d자만' % len(keep), results[mode][2]))
        except AssertionError as e:
            print('  글꼴[가나 %s] 안 됨: %s' % (mode, e))
    font, n, msg = results[kana_mode]
    assert len(font) - len(orig_font) <= FONT_GROW_MAX, '글꼴이 %d B 늘어남 — SYS 힙 한도 초과(docs §9)' % (len(font) - len(orig_font))
    print('  글꼴 %s 가나 %s 로 씀' % (FONT_PATH, kana_mode))
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
