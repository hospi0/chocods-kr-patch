# -*- coding: utf-8 -*-
r"""카드 게임(romdata/PUD) 글 — 형식별 풀기·다시 짜기 + 원문 TSV 추출.

  python tools/pudtext.py            → work/pud_src.tsv (경로 · 번호 · 원문) + 무변경 왕복 검사

형식(2026-09-25 조사):
  table  u32 개수 + u32 오프셋[개수](파일 시작 기준) + UTF-8 문자열(NUL 끝)
         battletext·charactertext·*_ja_.dat(칭호·정형문·오류)·wifitext
  ptx    u32 쪽 수 + 쪽마다(u32 바이트 길이 + UTF-16LE 본문). ESC(0x1B)+글자 = 색·굵기, 0x0A = 개행 — 미니게임 설명
  u16z   UTF-16LE 문자열 + NUL(0x0000) — deck/multiplay/skb 의 .txt
글 표기: 개행 \n · ESC {1B} · 그 밖 제어 글자 {XX}.
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pudbuild

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'pud_src.tsv')

TABLE = [
    'romdata/PUD/pub/pubmain/ja/battletext.bin.z',
    'romdata/PUD/pub/pubmain/ja/charactertext.bin.z',
    'romdata/PUD/pub/pubresult/pubresult_shougou_ja_.dat.z',
    'romdata/PUD/pub/pubresult/pubresult_teikei_ja_.dat.z',
    'romdata/PUD/pub/pubresult/textdata_ja_.dat.z',
    'romdata/PUD/pub/errortext_ja_.dat.z',
    'romdata/PUD/errorproc/textdata_ja_.dat.z',
    'romdata/PUD/wifi/ja/wifitext.bin',
    'romdata/PUD/pubtutorial/ja/tutorialtext.bin',       # 카드 게임 튜토리얼 설명
    'romdata/PUD/deck/ja/cardgroup.bin',                 # 「マンドラ族」
]


def esc(s):
    out = []
    for c in s:
        if c == '\n':
            out.append('\\n')
        elif c == '\x1b':
            out.append('{1B}')
        elif 0xDC80 <= ord(c) <= 0xDCFF:
            out.append('{S%02X}' % (ord(c) - 0xDC00))
        elif ord(c) < 0x20 or c == '\\':
            out.append('{%02X}' % ord(c))
        else:
            out.append(c)
    return ''.join(out)


def unesc(s):
    s = s.replace('\\n', '\n')
    s = re.sub(r'\{S([0-9A-F]{2})\}', lambda m: chr(0xDC00 + int(m.group(1), 16)), s)
    return re.sub(r'\{([0-9A-F]{2})\}', lambda m: chr(int(m.group(1), 16)), s)


# ── table
def table_parse(d):
    n = struct.unpack_from('<I', d, 0)[0]
    offs = struct.unpack_from('<%dI' % n, d, 4)
    out = []
    for k, o in enumerate(offs):
        z = d.index(b'\0', o)
        out.append(d[o:z].decode('utf-8', 'surrogateescape'))   # 03 FF xx 제어 = {03}{SFF}{xx}
    end = d.index(b'\0', offs[-1]) + 1 if n else 4
    return out, d[end:]                       # 꼬리(정렬 채움)


def table_build(strs, tail):
    n = len(strs)
    body = bytearray()
    offs = []
    base = 4 + 4 * n
    for s in strs:
        offs.append(base + len(body))
        body += s.encode('utf-8', 'surrogateescape') + b'\0'
    out = struct.pack('<I', n) + struct.pack('<%dI' % n, *offs) + bytes(body)
    return out + bytes(-len(out) % 4) if tail and not tail.strip(b'\0') else out + tail


# ── ptx
def ptx_parse(d):
    n = struct.unpack_from('<I', d, 0)[0]
    p = 4
    out = []
    for _ in range(n):
        ln = struct.unpack_from('<I', d, p)[0]
        out.append(d[p + 4:p + 4 + ln].decode('utf-16-le'))
        p += 4 + ln
    return out, d[p:]


def ptx_build(pages, tail):
    out = bytearray(struct.pack('<I', len(pages)))
    for s in pages:
        b = s.encode('utf-16-le')
        out += struct.pack('<I', len(b)) + b
    return bytes(out) + tail


# ── u16z
def u16z_parse(d):
    t = d.decode('utf-16-le')
    z = t.index('\0')
    return [t[:z]], d[(z + 1) * 2:]


def u16z_build(strs, tail):
    return strs[0].encode('utf-16-le') + b'\0\0' + tail


# ── dcd (덱 편집 카드 자료): u32 첫값 + u32 이름 구역 끝 + [u16 글자수(NUL 포함) + UTF-16]×33 몬스터 이름
#    + 카드 기록 143 [u16 기록 길이 + 8 B + UTF-16 기술 이름 + NUL]
DCD_NAMES = 33


def dcd_parse(d):
    a, end = struct.unpack_from('<II', d, 0)
    p = 8
    out = []
    for _ in range(DCD_NAMES):
        n = struct.unpack_from('<H', d, p)[0]
        out.append(d[p + 2:p + 2 + 2 * n].decode('utf-16-le').rstrip('\0'))
        p += 2 + 2 * n
    assert p == end
    heads = []
    while p < len(d):
        L = struct.unpack_from('<H', d, p)[0]
        heads.append(d[p + 2:p + 10])
        out.append(d[p + 10:p + L].decode('utf-16-le').rstrip('\0'))
        p += L
    return out, (a, heads)


def dcd_build(strs, meta):
    a, heads = meta
    body = bytearray()
    for s in strs[:DCD_NAMES]:
        b = (s + '\0').encode('utf-16-le')
        body += struct.pack('<H', len(b) // 2) + b
    out = bytearray(struct.pack('<II', a, 8 + len(body))) + body
    for h, s in zip(heads, strs[DCD_NAMES:]):
        b = (s + '\0').encode('utf-16-le')
        out += struct.pack('<H', 10 + len(b)) + h + b
    return bytes(out)


FMT = {'dcd': (dcd_parse, dcd_build), 'table': (table_parse, table_build), 'ptx': (ptx_parse, ptx_build), 'u16z': (u16z_parse, u16z_build)}


def targets(rom):
    out = [(p, 'table') for p in TABLE]
    def rec(folder, prefix):
        for n in folder.files:
            yield prefix + n
        for n, sub in folder.folders:
            yield from rec(sub, prefix + n + '/')
    for p in rec(rom.filenames, ''):
        if p.endswith('.ptx') and (p.startswith('romdata/PUD/mgentryphase/text/')
                                   or p.startswith(('romdata/PUD/multiplay/text/ja/', 'romdata/PUD/multiplay/text/jc/'))):
            out.append((p, 'ptx'))
        elif p.endswith('.txt') and p.startswith(('romdata/PUD/deck/ja/', 'romdata/PUD/multiplay/text/ja/',
                                                   'romdata/PUD/multiplay/text/jc/', 'romdata/PUD/skb/ja/')):
            out.append((p, 'u16z'))
        elif p == 'romdata/PUD/deck/ja/deck_card_data.dcd':
            out.append((p, 'dcd'))
    return out


def load(rom, p, kind):
    raw = bytes(rom.getFileByName(p))
    d, comp = pudbuild.unz(raw) if p.endswith('.z') else (raw, None)
    strs, tail = FMT[kind][0](d)
    return d, comp, strs, tail


def apply(rom, ids):
    """work/ko_pud/*.tsv 번역을 ROM 파일에 되쓴다(빌더용). jc 는 ja 와 쪽 수가 같으면 ja 번역을 쓴다. → 쓴 한글 음절 집합"""
    import pudcheck
    K = {k: v[0] for k, v in pudcheck.ko().items()}
    used = set()
    nfile = nline = 0
    for p, kind in targets(rom):
        fid = ids[p]
        raw = bytes(rom.files[fid])
        d, comp = pudbuild.unz(raw) if p.endswith('.z') else (raw, None)
        strs, tail = FMT[kind][0](d)
        ja = p.replace('/jc/', '/ja/')
        ja_n = None
        if '/jc/' in p and ja in ids:
            jd = bytes(rom.files[ids[ja]])
            jd = pudbuild.unz(jd)[0] if ja.endswith('.z') else jd
            ja_n = len(FMT[kind][0](jd)[0])
        new = list(strs)
        hit = 0
        for k in range(len(strs)):
            t = K.get((p, k))
            if t is None and ja_n == len(strs):
                t = K.get((ja, k))
            if t is not None:
                new[k] = unesc(t)
                hit += 1
        if not hit:
            continue
        nd = FMT[kind][1](new, tail)
        rom.files[fid] = pudbuild.rez(nd, comp) if comp else nd
        used |= {c for s in new for c in s if '가' <= c <= '힣'}
        nfile += 1
        nline += hit
    print('  카드 게임 글: 파일 %d · 줄 %d' % (nfile, nline))
    return used


def main():
    import ndspy.rom
    from gfxsurvey import ORIG
    rom = ndspy.rom.NintendoDSRom.fromFile(ORIG)
    rows = []
    bad = []
    for p, kind in targets(rom):
        d, comp, strs, tail = load(rom, p, kind)
        if FMT[kind][1](strs, tail) != d:
            bad.append(p)
        for k, s in enumerate(strs):
            rows.append('%s\t%s\t%d\t%s' % (p, kind, k, esc(s)))
    with open(SRC, 'w', encoding='utf-8', newline='\n') as fo:
        fo.write('# 카드 게임 글 원문(tools/pudtext.py) — 경로\t형식\t번호\t원문\n')
        fo.write('\n'.join(rows) + '\n')
    print('파일 %d · 줄 %d · 왕복 불일치 %d %s' % (len(targets(rom)), len(rows), len(bad), bad[:5]))


if __name__ == '__main__':
    main()
