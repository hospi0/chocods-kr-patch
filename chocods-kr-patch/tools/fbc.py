# -*- coding: utf-8 -*-
r"""FBC 컨테이너 · txtbin 문자열 표

FBC 머리(0x40, 빈 곳은 '0'(0x30) 채움):
  +0x00 u16 0x14 · +0x02 u16 6 · +0x06 u16 항목 수 · +0x08 표1(시작) · +0x0C 표2(크기) · +0x10 표3(이름)
  +0x14 데이터 시작 · +0x18 데이터 끝 · +0x1C 파일 크기            (표 위치·값은 모두 0x20 정렬)
  항목 i: 시작 = 표1[i] + 표1위치 · 크기 = u32 @ (표2[i] + 표2위치) · 이름 = C 문자열 @ (표3[i] + 표3위치)
  항목은 다시 FBC 일 수 있다(중첩). 이름 끝이 .csvbin(행 표) / .txtbin(문자열) 짝.

txtbin: u32 크기 · u32 개수 · 8 B 0 · u32 오프셋[개수](txtbin 시작 기준) · NUL 종단 문자열(4 B 정렬)
  인코딩은 파일마다 다르다: 이벤트 메시지 = UTF-8, 아이템 등 = Shift-JIS. 태그 = ESC(0x1B) + «XX}n~».
"""
import struct


def parse(d):
    """→ [(이름, 시작, 크기)]"""
    assert d[:2] == b'\x14\x00', d[:4].hex()
    n = struct.unpack_from('<H', d, 6)[0]
    t1, t2, t3 = struct.unpack_from('<III', d, 8)
    out = []
    for i in range(n):                                   # 세 표의 값은 «자기 표 위치» 기준 오프셋
        st = struct.unpack_from('<I', d, t1 + 4 * i)[0] + t1
        sz = struct.unpack_from('<I', d, struct.unpack_from('<I', d, t2 + 4 * i)[0] + t2)[0]
        no = struct.unpack_from('<I', d, t3 + 4 * i)[0] + t3
        name = d[no:d.index(b'\0', no)].decode('latin1')
        out.append((name, st, sz))
    return out


def walk(d, prefix=''):
    """중첩 FBC 를 펼쳐 (경로, 바이트) 를 낸다."""
    for name, st, sz in parse(d):
        b = d[st:st + sz]
        if b[:2] == b'\x14\x00' and b[2:4] == b'\x06\x00':
            yield from walk(b, prefix + name + '/')
        else:
            yield prefix + name, b


def txtbin(b):
    size, n = struct.unpack_from('<II', b, 0)
    offs = struct.unpack_from('<%dI' % n, b, 0x10)
    return [b[o:b.index(b'\0', o)] for o in offs]


def _fill(n, ch=b'0'):
    return ch * n


def _align(b, a, ch):
    return b + ch * (-len(b) % a)


def build(entries):
    """entries: [(이름, 바이트)] → FBC. 원본 배치를 그대로 흉내 낸다(무변경 왕복 = 원본과 같음, check_roundtrip)."""
    n = len(entries)
    tsz = ((4 * n + 0x1F) // 0x20) * 0x20
    t1, t2, t3 = 0x40, 0x40 + tsz, 0x40 + 2 * tsz
    data_pos = 0x40 + 3 * tsz
    body = bytearray()
    starts = []
    for name, b in entries:
        starts.append(data_pos + len(body))
        body += b
        body += b'0' * (-len(b) % 0x20)                       # 항목 데이터는 '0'(0x30) 으로 0x20 정렬 (그림 FBC 실측)
    size_pos = data_pos + len(body)
    sizes = bytearray()
    size_offs = []
    for name, b in entries:
        size_offs.append(size_pos + len(sizes))
        sizes += struct.pack('<I', len(b)) + _fill(0x1C)          # 크기 = 정렬 전 실제 길이
    name_pos = size_pos + len(sizes)
    names = bytearray()
    name_offs = []
    for name, b in entries:
        name_offs.append(name_pos + len(names))
        nb = name.encode('latin1') + b'\0'
        names += _align(nb, 0x20, b'0')
    total = name_pos + len(names)
    v1 = [s - t1 for s in starts]
    v2 = [s - t2 for s in size_offs]
    v3 = [s - t3 for s in name_offs]
    head = bytearray(struct.pack('<HHHHIIIIIIII', 0x14, 6, 0, n, t1, t2, t3, v1[0], v2[0], v3[0], 0, 0))[:0x20]
    head += bytes(0x20)
    tabs = b''.join(_align(b''.join(struct.pack('<I', v) for v in vs), 0x20, b'0') for vs in (v1, v2, v3))
    out = bytes(head) + tabs + bytes(body) + bytes(sizes) + bytes(names)
    assert len(out) == total
    return out


def entries(d):
    """→ [(이름, 바이트)] (크기는 표2 값 그대로 = 0x20 정렬된 길이)"""
    return [(name, d[st:st + sz]) for name, st, sz in parse(d)]


def txtbin_build(strs):
    """strs: [bytes] → txtbin. 문자열은 NUL 뒤 0x00 으로 4 B 정렬."""
    n = len(strs)
    head = 0x10 + 4 * n
    body = bytearray()
    offs = []
    for s in strs:
        offs.append(head + len(body))
        body += s + b'\0'
        body += bytes(-len(body) % 4)
    size = head + len(body)
    return struct.pack('<II', size, n) + bytes(8) + b''.join(struct.pack('<I', o) for o in offs) + bytes(body)


def guess_enc(strs):
    raw = b''.join(strs)
    if not any(c >= 0x80 for c in raw):
        return 'ascii'
    try:
        raw.decode('utf-8')
        return 'utf-8'
    except UnicodeDecodeError:
        return 'cp932'
