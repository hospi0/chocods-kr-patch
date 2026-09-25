# -*- coding: utf-8 -*-
r"""Shift-JIS 텍스트에 한글 싣기.

게임은 SJIS 문자열을 ARM9 의 NitroSDK SJIS→유니코드 변환(0x20141a0 근처)으로 바꾼 뒤 글꼴(유니코드 CMAP)로 그린다.
변환 표 = ARM9 0x2043100 부터 u16[60 × 0xC0]: 2 바이트 코드 (선행, 후행) 의 유니코드 =
    u16 @ 0x2043100 + 2 × ((선행 − (0x81 | E0 이상 0xC1)) × 0xC0 + 후행) − 0x80
→ 한자 줄 0x8940 부터의 SJIS 코드 2,350 칸을 한글(KS X 1001 순서) 유니코드로 바꿔 쓰고, SJIS 파일의 한글은 그 코드로 적는다.
  (이 칸들의 원래 한자는 번역 뒤 안 쓴다 — 전면 한글화 규칙.)
"""

TABLE_RAM = 0x2043100
ARM9_RAM = 0x2000000


def _hangul_set():
    out = []
    for hi in range(0xB0, 0xC9):
        for lo in range(0xA1, 0xFF):
            out.append(bytes((hi, lo)).decode('cp949'))
    return out


HANGUL = _hangul_set()


def _slots():
    out = []
    for lead in list(range(0x89, 0xA0)) + list(range(0xE0, 0xEB)):
        for trail in range(0x40, 0xFD):
            if trail == 0x7F:
                continue
            out.append((lead, trail))
    return out


SLOT = dict(zip(HANGUL, _slots()))      # 한글 → (선행, 후행)


def table_off(lead, trail):
    """ARM9 바이트 오프셋"""
    row = lead - (0xC1 if lead >= 0xE0 else 0x81)
    return TABLE_RAM - ARM9_RAM + 2 * (row * 0xC0 + trail) - 0x80


def patch_arm9(arm9):
    """변환 표의 한글 칸 2,350 개를 고쳐 쓴 새 ARM9 바이트"""
    a = bytearray(arm9)
    assert a[table_off(0x81, 0x40):table_off(0x81, 0x40) + 4] == b'\x00\x30\x01\x30', '변환 표 위치 불일치'
    for ch, (lead, trail) in SLOT.items():
        o = table_off(lead, trail)
        a[o:o + 2] = ord(ch).to_bytes(2, 'little')
    return bytes(a)


def encode(text):
    """한글은 배정 코드로, 나머지는 cp932. 못 바꾸는 글자는 에러(인코딩 누락 = 빌드 실패)."""
    out = bytearray()
    for ch in text:
        if ch in SLOT:
            out += bytes(SLOT[ch])
        elif 0xE000 <= ord(ch) <= 0xE0BB:                # 조사 표시 코드(josa.py): 변환 표 사용자 정의 행 F040‥ = U+E000‥
            n = ord(ch) - 0xE000
            t = 0x40 + n + (1 if 0x40 + n >= 0x7F else 0)
            out += bytes((0xF0, t))
        elif 0xAC00 <= ord(ch) <= 0xD7A3:
            raise ValueError('KS X 1001 밖 음절 %r' % ch)
        else:
            out += ch.encode('cp932')
    return bytes(out)


def decode(b):
    """검산용: 배정 코드 → 한글, 나머지 cp932"""
    inv = {v: k for k, v in SLOT.items()}
    out = []
    i = 0
    while i < len(b):
        c = b[i]
        if (0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC) and i + 1 < len(b):
            pair = (c, b[i + 1])
            out.append(inv[pair] if pair in inv else bytes(pair).decode('cp932', errors='replace'))
            i += 2
        else:
            out.append(bytes((c,)).decode('cp932', errors='replace'))
            i += 1
    return ''.join(out)


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    t = '녹슨 발톱・초코보 킥 Ｘ'
    e = encode(t)
    print(e.hex(), decode(e) == t, len(SLOT), SLOT['가'], SLOT['힝'])
