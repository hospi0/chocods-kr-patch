# -*- coding: utf-8 -*-
r"""글자 목록 구조 바꾸기 검산(ROM 없이 돌아감)

  python tools/test_pua.py

1) 조사 훅(josa.build)을 unicorn 으로 실제 ARM 명령 그대로 돌려, 옮겨 적은 코드에서 josa.simulate(한글 기준)와 같은 조사가 나오는지
   — 번역에 쓰인 모든 음절 × 조사 7개 + 한글 아닌 직전 글자.
2) 가짜 NFTR(dsr_fnt 꼴: ASCII·히라가나·가타카나 방식 0, 전각 방식 1, 0‥FFFF 방식 2 한자 쌍)로 nftr.rebuild →
   남긴 코드는 같은 비트맵, 버린 코드는 없음, 새 한글·조사 빈 글리프 찾기, 다시 쓰고 읽어도 같음, 크기 계산.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import josa
import nftr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def used_syllables():
    import glob
    s = set()
    for p in glob.glob(os.path.join(ROOT, 'work', 'ko', '*.tsv')):
        for line in open(p, encoding='utf-8'):
            if line[:1] not in '#@':
                s |= {c for c in line if 0xAC00 <= ord(c) <= 0xD7A3}
    return s


def test_hook():
    from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
    from unicorn.arm_const import UC_ARM_REG_R1, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_PC
    used = used_syllables()
    pua = josa.assign(used)
    remap, a, al, n = pua
    hook, code = josa.build(pua)
    mu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    mu.mem_map(0x2000000, 0x100000)
    mu.mem_write(hook, code)
    sp = 0x20F0000

    def call(ch_code):
        mu.reg_write(UC_ARM_REG_SP, sp)
        mu.reg_write(UC_ARM_REG_R1, ch_code)
        mu.emu_start(hook, josa.RESUME)
        assert mu.reg_read(UC_ARM_REG_PC) == josa.RESUME
        return mu.reg_read(UC_ARM_REG_R1)

    inv = {v: k for k, v in remap.items()}
    bad = 0
    prevs = sorted(used) + ['3', 'A', '…', '!']
    for p in prevs:
        pc = remap.get(p, ord(p))
        for m in range(0xE000, 0xE007):
            assert call(pc) == pc                    # 보통 글자는 그대로 넘기고 기억
            got = call(m)
            want = josa.simulate(p, m)
            want_code = remap[want] if want else josa.NULL
            if got != want_code:
                bad += 1
                if bad < 10:
                    print('  ✗', p, hex(m), inv.get(got, hex(got)), want)
    print('훅: 음절 %d(받침 없음 %d · ㄹ %d · 그 밖 %d) × 조사 7 + 비한글 4 — 틀림 %d'
          % (n, a, al - a, n - al, bad))
    assert bad == 0
    print('훅 크기 %d B (빈 곳 %d B)' % (len(code), josa.FREE_END - josa.FREE_START))


def fake_font():
    f = nftr.Nftr.__new__(nftr.Nftr)
    f.head = bytearray(b'RTFN\xff\xfe\x00\x01' + bytes(4) + b'\x10\x00\x00\x00')
    f.finf = bytearray(b'FNIF\x1c\x00\x00\x00' + bytes(20))
    f.cw, f.ch, f.tsize = 10, 10, 13
    f.cg_rest = bytes((9, 10, 1, 0))
    f.glyphs, f.widths, f.cmaps = [], [], []

    def g(code):
        f.glyphs.append(struct.pack('<I', code) + bytes(9))
        f.widths.append((0, 9, 10))
        return len(f.glyphs) - 1
    for first, last in ((0x20, 0x7E), (0x3041, 0x3093), (0x30A1, 0x30FC)):
        i0 = g(first)
        for c in range(first + 1, last + 1):
            g(c)
        f.cmaps.append([first, last, 0, struct.pack('<HH', i0, 0)])
    tbl = [g(c) if c % 3 else 0xFFFF for c in range(0xFF01, 0xFF5F)]
    f.cmaps.append([0xFF01, 0xFF5E, 1, struct.pack('<%dH' % len(tbl), *tbl)])
    pairs = [(c, g(c)) for c in [0x25CB, 0x0410, 0x0411, 0x2460] + list(range(0x4E00, 0x4E00 + 606))]
    f.cmaps.append([0, 0xFFFF, 2, pairs])
    alt = f.cmaps[0][3]
    struct.pack_into('<H', f.finf, nftr.FINF_ALT, 0x3F - 0x20)       # 대체 글자 = '?'
    return nftr.Nftr(f.build())


def test_font():
    orig = fake_font()
    ob = orig.build()
    before = nftr.code_map(orig)
    keep_kana = set('きぼうのほし')
    drop = {c for c in before if 0x4E00 <= c <= 0x9FFF or (0x3041 <= c <= 0x30FA and chr(c) not in keep_kana)}
    hangul = [(struct.pack('<I', 0x10000 + k) + bytes(9), (0, 9, 10)) for k in range(300)]
    f = nftr.Nftr(ob)
    dropped, h0, moved = nftr.rebuild(f, drop, josa.PUA_BASE, hangul, extra=[(josa.NULL, bytes(13), (0, 0, 0))])
    nb = f.build()
    f2 = nftr.Nftr(nb)
    for font in (f, f2):
        for c, i in before.items():
            got = nftr.lookup_nns(font, c)
            if c in drop:
                assert got == nftr.NOT_FOUND, hex(c)
            else:
                assert font.glyphs[got] == orig.glyphs[i], hex(c)
        for k in range(300):
            assert font.glyphs[nftr.lookup_nns(font, josa.PUA_BASE + k)][:4] == struct.pack('<I', 0x10000 + k)
        assert nftr.lookup_nns(font, josa.NULL) != nftr.NOT_FOUND
        alt = struct.unpack_from('<H', font.finf, nftr.FINF_ALT)[0]
        assert font.glyphs[alt][:4] == struct.pack('<I', 0x3F)
    per = orig.tsize + 3
    print('가짜 글꼴: 버린 글리프 %d · 새 한글 300 → %d → %d B (%+d, 한글 한 자 %d B)'
          % (dropped, len(ob), len(nb), len(nb) - len(ob), per))


def test_build():
    """build.py 쪽 이음(갈무리9 대신 가짜 글자 그림): 번역 전부 → 코드 배정 → UTF-8·SJIS 표·글꼴이 같은 코드"""
    import build
    import bdf
    import sjiskr
    rows = build.read_tsv(os.path.join(ROOT, 'work', 'ko'))
    used = {c for r in rows.values() for m in r.values() for t in m.values() for c in t if 0xAC00 <= ord(c) <= 0xD7A3}
    used |= {c for _, ko in build.OV0_STRINGS for c in ko if 0xAC00 <= ord(c) <= 0xD7A3}
    pua = josa.assign(used)
    build.TEXT_REMAP.clear()
    build.TEXT_REMAP.update({k: chr(v) for k, v in pua[0].items()})
    for r in rows.values():
        for m in r.values():
            for t in m.values():
                assert not any(0xAC00 <= ord(c) <= 0xD7A3 for c in build.remap_text(t))
    bdf.load = lambda p: (None, 0)
    bdf.render = lambda G, asc, cp, w, h, n: ([[(cp >> k) & 1 for k in range(10)]] * 10, 10)
    out, n, msg = build.build_font(fake_font().build(), pua, None)
    f = nftr.Nftr(out)
    assert all(nftr.lookup_nns(f, v) != nftr.NOT_FOUND for v in pua[0].values())
    arm9 = bytearray(0x50000)
    o = sjiskr.table_off(0x81, 0x40)
    arm9[o:o + 4] = b'\x00\x30\x01\x30'
    a = sjiskr.patch_arm9(bytes(arm9), pua[0])
    for ch, v in pua[0].items():
        o = sjiskr.table_off(*sjiskr.SLOT[ch])
        assert int.from_bytes(a[o:o + 2], 'little') == v
    left = build.leftover_text(rows)
    print('빌드 이음: 음절 %d · UTF-8 에 한글 코드 안 남음 · SJIS 표 = 글꼴 코드 · 번역 안 한 글 %d줄(가나 %d자)'
          % (n, len(left), len({c for t in left for c in t if build.in_ranges(ord(c), build.KANA)})))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    test_hook()
    test_font()
    test_build()
    print('모두 통과')
