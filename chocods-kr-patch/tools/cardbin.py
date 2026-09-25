# -*- coding: utf-8 -*-
r"""카드 게임 카드 표(PUD/card/card.bin, card/ja/card.bin) 읽기·쓰기.

머리 10 u32: [기록 수, 기록 위치, ?, 이름 풀, 기록 수, 기술 풀, 설명 수, 설명 풀, 기록 수, 능력 풀]
기록 24 B × N: [id, 카드 번호, 이름 오프셋, 기술 오프셋, 설명 오프셋, 능력 오프셋] (오프셋 = 각 풀 시작 기준)
풀 = UTF-8 NUL 끝 문자열. 제어: 0x1C xx = 색 바꿈(TSV 에서 {Cxx}), 개행 = \n.
"""
import struct

POOLS = ('name', 'skill', 'desc', 'abil')


def parse(d):
    h = struct.unpack_from('<10I', d, 0)
    starts = [h[3], h[5], h[7], h[9], len(d)]
    n = h[0]
    recs = [list(struct.unpack_from('<6I', d, h[1] + 24 * i)) for i in range(n)]
    pools = {}
    for k, name in enumerate(POOLS):
        raw = d[starts[k]:starts[k + 1]]
        strs, o = {}, 0
        for s in raw.split(b'\0')[:-1]:
            strs[o] = s.decode('utf-8')
            o += len(s) + 1
        pools[name] = strs
    return h, recs, pools


def esc(s):
    out = []
    for ch in s:
        if ch == '\n':
            out.append(chr(92) + 'n')                    # TSV 한 줄 안에 \n 두 글자로
        elif ord(ch) < 0x20:
            out.append('{C%02X}' % ord(ch))
        else:
            out.append(ch)
    return ''.join(out)


def unesc(s):
    import re
    s = s.replace(chr(92) + 'n', chr(10))
    return re.sub(r'\{C([0-9A-F]{2})\}', lambda m: chr(int(m.group(1), 16)), s)


def build(d, trans):
    """trans = {(풀, 원래 오프셋): 새 문자열} → 새 card.bin(풀 다시 쌓고 기록 오프셋 고침)"""
    h, recs, pools = parse(d)
    h = list(h)
    out_pools, remap = [], {}
    for k, name in enumerate(POOLS):
        buf, m = bytearray(), {}
        for o, s in pools[name].items():
            m[o] = len(buf)
            buf += trans.get((name, o), s).encode('utf-8') + b'\0'
        if len(buf) and pools[name] and 0 not in m:
            pass
        out_pools.append(buf)
        remap[name] = m
    head_len = h[1] + 24 * len(recs)
    body = bytearray()
    starts = []
    pos = head_len
    for buf in out_pools:
        starts.append(pos)
        pos += len(buf)
    h[3], h[5], h[7], h[9] = starts
    out = bytearray(struct.pack('<10I', *h))
    out += d[40:h[1]]
    for r in recs:
        r = list(r)
        for k, name in enumerate(POOLS):
            if r[2 + k] in remap[name]:
                r[2 + k] = remap[name][r[2 + k]]
        out += struct.pack('<6I', *r)
    for buf in out_pools:
        out += buf
    return bytes(out)
