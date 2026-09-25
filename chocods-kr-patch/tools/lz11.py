# -*- coding: utf-8 -*-
"""닌텐도 LZ11 (0x11) 해제·압축 — romdata/**/*.z

머리 4 B: 0x11 + 풀린 크기 u24(0 이면 뒤 4 B 에 u32). 플래그 바이트(MSB 먼저) 뒤 토큰 8개.
참조 토큰: 첫 니블 0 → 3 B(길이 0x11+), 1 → 4 B(길이 0x111+), 그 밖 → 2 B(길이 니블+1). 거리 12비트+1.
"""
import struct


def decompress(d):
    assert d[0] == 0x11, '%02x' % d[0]
    size = d[1] | d[2] << 8 | d[3] << 16
    p = 4
    if size == 0:
        size = struct.unpack_from('<I', d, 4)[0]
        p = 8
    out = bytearray()
    while len(out) < size:
        flags = d[p]
        p += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if not flags & (0x80 >> bit):
                out.append(d[p])
                p += 1
                continue
            b0 = d[p]
            ind = b0 >> 4
            if ind == 0:
                ln = (((b0 & 0xF) << 4) | (d[p + 1] >> 4)) + 0x11
                disp = ((d[p + 1] & 0xF) << 8 | d[p + 2]) + 1
                p += 3
            elif ind == 1:
                ln = (((b0 & 0xF) << 12) | (d[p + 1] << 4) | (d[p + 2] >> 4)) + 0x111
                disp = ((d[p + 2] & 0xF) << 8 | d[p + 3]) + 1
                p += 4
            else:
                ln = ind + 1
                disp = ((b0 & 0xF) << 8 | d[p + 1]) + 1
                p += 2
            for _ in range(ln):
                out.append(out[-disp])
    return bytes(out[:size])


def compress(data):
    """탐욕 LZ11(길이 3‥0x10110, 거리 1‥0x1000). 해시 창."""
    n = len(data)
    out = bytearray()
    if n < 0x1000000:
        out += bytes((0x11, n & 0xFF, n >> 8 & 0xFF, n >> 16 & 0xFF))
    else:
        out += b'\x11\0\0\0' + struct.pack('<I', n)
    heads = {}
    i = 0
    while i < n:
        flag_pos = len(out)
        out.append(0)
        flags = 0
        for bit in range(8):
            if i >= n:
                break
            best_len, best_d = 0, 0
            if i + 3 <= n:
                key = data[i:i + 3]
                for j in reversed(heads.get(key, [])[-64:]):
                    d = i - j
                    if d > 0x1000:
                        break
                    l = 3
                    mx = min(0x10110, n - i)
                    while l < mx and data[j + l] == data[i + l]:
                        l += 1
                    if l > best_len:
                        best_len, best_d = l, d
                        if l == mx:
                            break
            if best_len >= 3:
                flags |= 0x80 >> bit
                dd = best_d - 1
                if best_len <= 0x10:
                    out += bytes((((best_len - 1) << 4) | (dd >> 8), dd & 0xFF))
                elif best_len <= 0x110:
                    l = best_len - 0x11
                    out += bytes((l >> 4, ((l & 0xF) << 4) | (dd >> 8), dd & 0xFF))
                else:
                    l = best_len - 0x111
                    out += bytes((0x10 | (l >> 12), (l >> 4) & 0xFF, ((l & 0xF) << 4) | (dd >> 8), dd & 0xFF))
                for k in range(i, i + best_len):
                    if k + 3 <= n:
                        heads.setdefault(data[k:k + 3], []).append(k)
                i += best_len
            else:
                out.append(data[i])
                if i + 3 <= n:
                    heads.setdefault(data[i:i + 3], []).append(i)
                i += 1
        out[flag_pos] = flags
    while len(out) % 4:
        out.append(0)
    return bytes(out)
