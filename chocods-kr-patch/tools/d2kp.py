# -*- coding: utf-8 -*-
r"""카드 게임 그림 겉 상자 «D2KP»(.PBG/.POBJ/.pobj) 안 표준 블록 바꾸기.

머리: 'D2KP' + u32 0 + u32 × 8 (종류별 표 위치, 없으면 0xFFFFFFFF).
표: u32 개수 + (u32 위치, u32 크기) × 개수 — 위치는 상자 시작 기준.
블록을 바꿀 때 원래 자리(다음 블록까지)에 들어가면 제자리, 아니면 끝에 붙이고 표를 고친다.
"""
import struct


def entries(d):
    """[(표 안 항목 위치, 블록 위치, 크기)]"""
    assert d[:4] == b'D2KP'
    out = []
    for k in range(8):
        t = struct.unpack_from('<I', d, 8 + 4 * k)[0]
        if t == 0xFFFFFFFF:
            continue
        n = struct.unpack_from('<I', d, t)[0]
        for i in range(n):
            e = t + 4 + 8 * i
            off, sz = struct.unpack_from('<II', d, e)
            out.append((e, off, sz))
    return out


def replace(d, old_off, new):
    d = bytearray(d)
    ents = entries(d)
    hit = [e for e in ents if e[1] == old_off]
    assert hit, '블록 위치 0x%X 가 표에 없음' % old_off
    e, off, sz = hit[0]
    nxt = min([o for _, o, _ in ents if o > off] + [len(d)])
    if len(new) <= nxt - off:
        d[off:off + len(new)] = new
        d[off + len(new):nxt] = bytes(nxt - off - len(new))
        struct.pack_into('<I', d, e + 4, len(new))
    else:
        d += bytes(-len(d) % 0x20)
        noff = len(d)
        d += new
        struct.pack_into('<II', d, e, noff, len(new))
    return bytes(d)
