# -*- coding: utf-8 -*-
r"""NSBMD/NSBTX 안 TEX0 텍스처 읽기·쓰기(형식 1 A3I5 · 2 4색 · 3 16색 · 4 256색 · 6 A5I3 · 7 직접색; 5 압축은 안 다룸)."""
import struct

FMT_BPP = {1: 8, 2: 2, 3: 4, 4: 8, 6: 8, 7: 16}


def _names(d, o, n):
    return [d[o + 16 * i:o + 16 * i + 16].split(b'\0')[0].decode('ascii', 'replace') for i in range(n)]


def _dict(d, o):
    """3D 사전: → (이름 목록, 자료 위치, 자료 크기)"""
    n = d[o + 1]
    size = struct.unpack_from('<H', d, o + 2)[0]
    ptree = o + 4 + 4 + 4 * n            # 헤더 8 + 트리 (n+1)*4
    ptree = o + 8 + 4 * (n + 1)
    dsz = struct.unpack_from('<H', d, ptree)[0]
    data = ptree + 4
    names = _names(d, data + dsz * n, n)
    return names, data, dsz, n


def parse(d):
    """→ (tex0 위치, textures[{name,fmt,w,h,off,size,c0}], palettes[{name,off}], 텍스처 자료 시작, 팔레트 자료 시작)"""
    t = d.find(b'TEX0')
    assert t >= 0
    tex_data = t + struct.unpack_from('<I', d, t + 0x14)[0]
    tex_dict = t + struct.unpack_from('<H', d, t + 0x0E)[0]
    pal_dict = t + struct.unpack_from('<I', d, t + 0x34)[0]
    pal_data = t + struct.unpack_from('<I', d, t + 0x38)[0]
    names, data, dsz, n = _dict(d, tex_dict)
    texs = []
    for i in range(n):
        p0, p1 = struct.unpack_from('<II', d, data + dsz * i)
        off = (p0 & 0xFFFF) << 3
        fmt = (p0 >> 26) & 7
        w = 8 << ((p0 >> 20) & 7)
        h = 8 << ((p0 >> 23) & 7)
        c0 = (p0 >> 29) & 1
        texs.append(dict(name=names[i], fmt=fmt, w=w, h=h, off=tex_data + off, size=w * h * FMT_BPP.get(fmt, 0) // 8, c0=c0,
                         param_at=data + dsz * i))
    pn, pdata, pdsz, pnn = _dict(d, pal_dict)
    pals = []
    for i in range(pnn):
        po = struct.unpack_from('<H', d, pdata + pdsz * i)[0] << 3
        pals.append(dict(name=pn[i], off=pal_data + po))
    return t, texs, pals


def bgr(v):
    return ((v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31)


def decode(d, tex, pal_off, npal=256):
    """→ (w, h, [(r,g,b,a)])"""
    w, h, fmt, o = tex['w'], tex['h'], tex['fmt'], tex['off']
    pal = [bgr(struct.unpack_from('<H', d, pal_off + 2 * i)[0]) for i in range(min(npal, (len(d) - pal_off) // 2))]
    out = []
    for i in range(w * h):
        if fmt == 3:
            v = (d[o + i // 2] >> (4 * (i & 1))) & 15
            a = 0 if (v == 0 and tex['c0']) else 255
            out.append(pal[v] + (a,))
        elif fmt == 4:
            v = d[o + i]
            a = 0 if (v == 0 and tex['c0']) else 255
            out.append(pal[v] + (a,))
        elif fmt == 2:
            v = (d[o + i // 4] >> (2 * (i & 3))) & 3
            out.append(pal[v] + (0 if (v == 0 and tex['c0']) else 255,))
        elif fmt == 1:
            v = d[o + i]
            out.append(pal[v & 31] + ((v >> 5) * 255 // 7,))
        elif fmt == 6:
            v = d[o + i]
            out.append(pal[v & 7] + ((v >> 3) * 255 // 31,))
        elif fmt == 7:
            v = struct.unpack_from('<H', d, o + 2 * i)[0]
            out.append(bgr(v) + (255 if v & 0x8000 else 0,))
        else:
            out.append((255, 0, 255, 255))
    return w, h, out
