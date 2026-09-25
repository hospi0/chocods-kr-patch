# -*- coding: utf-8 -*-
r"""NFTR(닌텐도 DS 글꼴) 읽기·다시 쓰기 — 글리프 덧붙이기

구조(dsr_fnt 실측): 'RTFN' 머리 0x10 → FINF(0x1C) → CGLP(글리프 비트맵) → CWDH(폭, 1블록) → CMAP 사슬.
  FINF +0x10/+0x14/+0x18 = CGLP·CWDH·CMAP «데이터» 위치(구획 시작 + 8).
  CGLP: 칸 w·h u8, 글리프 바이트 u16, 기준선·최대폭·bpp·플래그 u8 → 글리프 비트맵(MSB 먼저, 줄 이어 붙임).
  CWDH: 첫 번호 u16 · 끝 번호 u16 · 다음 u32 → 글리프마다 (왼쪽, 글리프 폭, 전진폭) 3 B.
  CMAP 블록: 첫 코드 u16 · 끝 코드 u16 · 방식 u16 · 0 u16 · 다음 블록 데이터 위치 u32 → 방식별 데이터
    (0 = 연속 범위: 첫 번호 u16 / 1 = 표: u16[끝−첫+1] / 2 = 쌍: 개수 u16 + (코드 u16, 번호 u16)×개수, 코드 순)
구획 크기는 4 바이트 정렬.
"""
import struct


def _pad4(b):
    return b + bytes(-len(b) % 4)


class Nftr:
    def __init__(self, d):
        assert d[:4] == b'RTFN'
        self.head = bytearray(d[:0x10])
        p = 0x10
        secs = []
        while p < len(d):
            mag = d[p:p + 4]
            sz = struct.unpack_from('<I', d, p + 4)[0]
            secs.append((mag, d[p:p + sz]))
            p += sz
        assert [m for m, _ in secs[:3]] == [b'FNIF', b'PLGC', b'HDWC'], [m for m, _ in secs]
        self.finf = bytearray(secs[0][1])
        cg = secs[1][1]
        self.cw, self.ch, self.tsize = struct.unpack_from('<BBH', cg, 8)
        self.cg_rest = cg[12:16]
        n = (len(cg) - 16) // self.tsize
        self.glyphs = [cg[16 + i * self.tsize:16 + (i + 1) * self.tsize] for i in range(n)]
        cw = secs[2][1]
        first, last, nxt = struct.unpack_from('<HHI', cw, 8)
        assert first == 0 and nxt == 0, '폭 표가 한 블록이 아님'
        self.widths = [tuple(cw[16 + 3 * i:19 + 3 * i]) for i in range(last + 1)]
        self.glyphs = self.glyphs[:last + 1]
        self.cmaps = []
        for mag, b in secs[3:]:
            assert mag == b'PAMC'
            first, last, typ = struct.unpack_from('<HHH', b, 8)
            data = b[20:]
            if typ == 2:
                cnt = struct.unpack_from('<H', data, 0)[0]
                pairs = [struct.unpack_from('<HH', data, 2 + 4 * k) for k in range(cnt)]
                self.cmaps.append([first, last, typ, pairs])
            else:
                self.cmaps.append([first, last, typ, bytes(data)])

    def add(self, code, bitmap, width):
        """bitmap: tsize 바이트, width: (왼쪽, 폭, 전진). 마지막 방식 2(0‥FFFF) 블록에 쌍을 넣는다."""
        idx = len(self.glyphs)
        assert len(bitmap) == self.tsize
        self.glyphs.append(bytes(bitmap))
        self.widths.append(tuple(width))
        blk = self.cmaps[-1]
        assert blk[2] == 2 and blk[0] == 0 and blk[1] == 0xFFFF
        assert all(c != code for c, _ in blk[3]), '이미 있는 코드 %04X' % code
        blk[3].append((code, idx))
        return idx

    def build(self):
        blk = self.cmaps[-1]
        blk[3].sort()
        out = bytearray(self.head)
        finf_pos = len(out)
        out += self.finf
        cg_pos = len(out)
        cg = bytearray(b'PLGC\0\0\0\0') + struct.pack('<BBH', self.cw, self.ch, self.tsize) + self.cg_rest
        cg += b''.join(self.glyphs)
        cg = _pad4(cg)
        struct.pack_into('<I', cg, 4, len(cg))
        out += cg
        cw_pos = len(out)
        cw = bytearray(b'HDWC\0\0\0\0') + struct.pack('<HHI', 0, len(self.widths) - 1, 0)
        cw += b''.join(bytes(w) for w in self.widths)
        cw = _pad4(cw)
        struct.pack_into('<I', cw, 4, len(cw))
        out += cw
        cm_pos = len(out)
        blocks = []
        for first, last, typ, data in self.cmaps:
            if typ == 2:
                data = struct.pack('<H', len(data)) + b''.join(struct.pack('<HH', c, i) for c, i in data)
            b = bytearray(b'PAMC\0\0\0\0') + struct.pack('<HHHHI', first, last, typ, 0, 0) + data
            blocks.append(_pad4(b))
        pos = cm_pos
        for k, b in enumerate(blocks):
            struct.pack_into('<I', b, 4, len(b))
            nxt = pos + len(b) + 8 if k + 1 < len(blocks) else 0
            struct.pack_into('<I', b, 16, nxt)
            pos += len(b)
        for b in blocks:
            out += b
        struct.pack_into('<III', out, finf_pos + 0x10, cg_pos + 8, cw_pos + 8, cm_pos + 8)
        struct.pack_into('<I', out, 8, len(out))
        return bytes(out)

    def lookup(self, code):
        for first, last, typ, data in self.cmaps:
            if not first <= code <= last:
                continue
            if typ == 0:
                return struct.unpack_from('<H', data, 0)[0] + code - first
            if typ == 1:
                v = struct.unpack_from('<H', data, 2 * (code - first))[0]
                if v != 0xFFFF:
                    return v
            if typ == 2:
                for c, i in data:
                    if c == code:
                        return i
        return None


def replace_kanji(f, items, keep=frozenset()):
    """items: [(한글 코드, 비트맵, 폭)] → 마지막 방식 2 블록의 한자(U+4E00‥9FFF) 쌍을 차례로 한글 코드로 바꾸고 그 글리프를 덮는다.
    글꼴 크기 불변(SYS 힙 여유 4 KB 뿐 — docs §9). 쓴 한자 수를 돌려준다."""
    blk = f.cmaps[-1]
    assert blk[2] == 2
    kanji = [k for k, (c, i) in enumerate(blk[3]) if 0x4E00 <= c <= 0x9FFF and chr(c) not in keep]   # keep = 아직 쓰이는 한자(번역 전 글)
    assert len(items) <= len(kanji), '한글 %d > 한자 칸 %d' % (len(items), len(kanji))
    for (code, bm, width), k in zip(items, kanji):
        c, idx = blk[3][k]
        blk[3][k] = (code, idx)
        f.glyphs[idx] = bytes(bm)
        f.widths[idx] = tuple(width)
    return len(items)


# ── 글자 목록 구조 바꾸기(docs §9 뒤 «연속 범위» 안) ──────────────────────────────
# 한글은 쓰는 음절만 사용자 영역 U+F000‥ 에 차례로 붙여(텍스트 쪽 코드도 build 가 같이 바꿈) CMAP 방식 0 한 블록으로 —
# 글자당 CMAP 쌍 4 B 가 없어져 비트맵 + 폭 만(dsr_fnt 13 + 3 = 16 B). 버리는 글자(한자·가나 등)는 글리프째 뺀다.
# NNS 글자 찾기는 CMAP 사슬을 앞에서부터 보고 «범위에 드는 첫 블록»에서 끝낸다 → 블록마다 원래 범위를 그대로 두고
# 버린 코드는 방식 1 표의 0xFFFF(없음)로, 새 한글 블록은 사슬 맨 앞(범위가 다른 블록과 안 겹치게 — 0‥FFFF 방식 2 는 뒤).

NOT_FOUND = 0xFFFF
FINF_ALT = 0x0A          # FINF 구획 안 대체 글자 번호 u16 (NNS: 머리 8 · 종류 u8 · 줄 간격 s8 · 대체 글자 u16)


def code_map(f):
    """코드 → 글리프 번호(첫 블록 우선, NNS 와 같은 순서)"""
    out = {}
    for first, last, typ, data in f.cmaps:
        if typ == 0:
            base = struct.unpack_from('<H', data, 0)[0]
            items = ((c, base + c - first) for c in range(first, last + 1))
        elif typ == 1:
            items = ((c, struct.unpack_from('<H', data, 2 * (c - first))[0]) for c in range(first, last + 1))
        else:
            items = iter(data)
        for c, i in items:
            if i != NOT_FOUND and c not in out and first <= c <= last:
                out[c] = i
    return out


def lookup_nns(f, code):
    """NNS 방식 검산: 범위에 드는 첫 블록에서 끝"""
    for first, last, typ, data in f.cmaps:
        if first <= code <= last:
            if typ == 0:
                return struct.unpack_from('<H', data, 0)[0] + code - first
            if typ == 1:
                return struct.unpack_from('<H', data, 2 * (code - first))[0]
            return next((i for c, i in data if c == code), NOT_FOUND)
    return NOT_FOUND


def rebuild(f, drop, base, glyphs, extra=()):
    """drop: 버릴 코드 집합 · glyphs: [(비트맵, 폭)] → 코드 base, base+1, … (방식 0 블록, 사슬 맨 앞)
    extra: [(코드, 비트맵, 폭)] → 마지막 0‥FFFF 방식 2 블록에 쌍으로(조사 «없음» 빈 글리프 등).
    제자리에서 f 를 고친다. 돌려줌 = (버린 글리프 수, 새 한글 첫 번호, 번호가 바뀐 남은 글리프 수)
    (게임이 글리프를 코드 아닌 번호로 직접 그리는 곳이 있으면 «번호가 바뀐» 글리프가 틀어진다 — 실기에서 확인할 것)"""
    cmap = code_map(f)
    alt = struct.unpack_from('<H', f.finf, FINF_ALT)[0]
    keep_idx = {i for c, i in cmap.items() if c not in drop} | {alt}
    n_old = len(f.glyphs)
    order = [i for i in range(n_old) if i in keep_idx]
    new = {o: n for n, o in enumerate(order)}
    f.glyphs = [f.glyphs[i] for i in order]
    f.widths = [f.widths[i] for i in order]
    struct.pack_into('<H', f.finf, FINF_ALT, new[alt])
    blocks = []
    for first, last, typ, data in f.cmaps:
        if typ == 2:
            blocks.append([first, last, 2, [(c, new[i]) for c, i in data if c not in drop and i in new]])
            continue
        if typ == 0:
            b0 = struct.unpack_from('<H', data, 0)[0]
            idx = [b0 + c - first for c in range(first, last + 1)]
        else:
            idx = list(struct.unpack_from('<%dH' % (last - first + 1), data, 0))
        codes = range(first, last + 1)
        nidx = [NOT_FOUND if (c in drop or i == NOT_FOUND or i not in new) else new[i] for c, i in zip(codes, idx)]
        if typ == 0 and NOT_FOUND not in nidx and nidx == list(range(nidx[0], nidx[0] + len(nidx))):
            blocks.append([first, last, 0, struct.pack('<HH', nidx[0], 0)])
        else:
            blocks.append([first, last, 1, struct.pack('<%dH' % len(nidx), *nidx)])
    h0 = len(f.glyphs)
    if glyphs:
        end = base + len(glyphs) - 1
        clash = [b for b in blocks if b[1] - b[0] < 0xFFFF and not (end < b[0] or b[1] < base)]
        assert not clash, '새 한글 범위 %04X‥%04X 가 기존 블록과 겹침 %s' % (base, end, [(hex(b[0]), hex(b[1])) for b in clash])
        assert not any(base <= c <= end for c in cmap if c not in drop), '새 한글 범위에 이미 쓰는 코드'
        for bm, w in glyphs:
            assert len(bm) == f.tsize
            f.glyphs.append(bytes(bm))
            f.widths.append(tuple(w))
        blocks.insert(0, [base, end, 0, struct.pack('<HH', h0, 0)])
    if extra:
        cat = blocks[-1]
        assert cat[2] == 2 and cat[0] == 0 and cat[1] == 0xFFFF, '마지막 블록이 0‥FFFF 방식 2 가 아님'
        for code, bm, w in extra:
            assert code not in {c for c, _ in cat[3]}, '이미 있는 코드 %04X' % code
            cat[3].append((code, len(f.glyphs)))
            f.glyphs.append(bytes(bm))
            f.widths.append(tuple(w))
    f.cmaps = blocks
    return n_old - len(order), h0, sum(1 for o, n in new.items() if o != n)
