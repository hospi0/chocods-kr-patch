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
