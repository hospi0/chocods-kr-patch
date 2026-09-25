# -*- coding: utf-8 -*-
r"""조사 자동 선택 — ARM9 글리프 번호 함수(NNS GetGlyphIndex 꼴, 0x2031178: r0 글꼴, r1 글자 코드)에 훅.

번역문에 «조사 표시 코드»(사용자 영역 U+E000‥)를 쓰면, 훅이 «직전에 조회한 글자»의 받침을 보고 알맞은 조사 글자로 바꿔 원래 함수로 넘긴다.
대사(UTF-8)·SJIS(아이템 등)·메뉴 모든 글자 경로가 이 함수를 거친다(ov2 0x2094784 → 0x2031178 등).
폭 재기와 그리기가 같은 순서로 이 함수를 부르므로 두 번 모두 같은 조사가 나온다.

  표시  U+     받침 있음 / 없음
  {을}  E000   을 / 를
  {이}  E001   이 / 가
  {은}  E002   은 / 는
  {과}  E003   과 / 와
  {으}  E004   으 / (없음)   — 「{으}로」: ㄹ 받침도 (없음)
  {아}  E005   아 / 야
  {이다} E006  이 / (없음)   — 「{이다}다」「{이다}라고」
  (없음) = U+E0FF 폭 0 빈 글리프(글꼴에 넣는다).
한글이 아닌 직전 글자(숫자·영문 등)는 «받침 없음»으로 친다.
SJIS 텍스트: 변환 표의 사용자 정의 행 F040‥ 이 이미 U+E000‥ 으로 바뀐다 → sjiskr.encode 가 F040+n 으로 적는다.

훅 코드·상태 변수 자리 = SJIS 변환 표의 빈 행(선행 0xEB·0xEC, JIS X 0208 미배정 — 전부 0 확인).
"""
import struct
import keystone

HOOK_SITE = 0x2031178          # push {r3, lr}  → b HOOK
RESUME = 0x203117C
TABLE_RAM = 0x2043100
ARM9 = 0x2000000
NULL = 0xE0FF
PAIRS = [('을', '를'), ('이', '가'), ('은', '는'), ('과', '와'), ('으', None), ('아', '야'), ('이', None)]
MARK = {'{을}': 0xE000, '{이}': 0xE001, '{은}': 0xE002, '{과}': 0xE003, '{으}': 0xE004, '{아}': 0xE005, '{이다}': 0xE006}


def row_addr(lead):
    return TABLE_RAM + 2 * ((lead - (0xC1 if lead >= 0xE0 else 0x81)) * 0xC0 + 0x40) - 0x80


FREE_START = row_addr(0xEB)
FREE_END = row_addr(0xED)      # 0xEB·0xEC 두 줄 = 768 B (0xED·0xEE 는 NEC 선정 IBM 확장 한자로 차 있음)


def build():
    hook = FREE_START
    asm = f'''
        push {{r3, lr}}
        ldr  r3, state_p
        sub  r2, r1, #0xE000
        cmp  r2, #7
        bhs  store
        ldr  r12, [r3]
        sub  r12, r12, #0xAC00
        cmp  r12, #0
        blt  nojong
        ldr  lr, lim
        cmp  r12, lr
        bhs  nojong
        ldr  lr, magic
        mul  lr, r12, lr
        lsr  lr, lr, #18
        rsb  lr, lr, lr, lsl #3
        sub  r12, r12, lr, lsl #2
        b    have
    nojong:
        mov  r12, #0
    have:
        adr  lr, ptable
        add  lr, lr, r2, lsl #2
        cmp  r12, #0
        ldrhne r1, [lr]
        ldrheq r1, [lr, #2]
        cmp  r2, #4
        cmpeq r12, #8
        ldrheq r1, [lr, #2]
    store:
        str  r1, [r3]
        b    {RESUME:#x}
    state_p: .word 0
    lim:     .word 11172
    magic:   .word 9363
    ptable:
    '''
    ks = keystone.Ks(keystone.KS_ARCH_ARM, keystone.KS_MODE_ARM)
    enc, _ = ks.asm(asm, hook)
    code = bytearray(enc)
    for a, b in PAIRS:
        code += struct.pack('<HH', ord(a), ord(b) if b else NULL)
    state = hook + len(code)
    code += bytes(4)
    # state_p 채우기: 'state_p' 는 ptable 앞 12 바이트
    sp_off = len(enc) - 12
    struct.pack_into('<I', code, sp_off, state)
    assert hook + len(code) <= FREE_END
    return hook, bytes(code)


def patch_arm9(arm9):
    a = bytearray(arm9)
    s, e = FREE_START - ARM9, FREE_END - ARM9
    assert not any(a[s:e]), '빈 행이 비어 있지 않음'
    hook, code = build()
    a[hook - ARM9:hook - ARM9 + len(code)] = code
    off = HOOK_SITE - ARM9
    assert a[off:off + 4] == bytes.fromhex('08402de9'), a[off:off + 4].hex()   # push {r3, lr}
    rel = (hook - (HOOK_SITE + 8)) >> 2
    a[off:off + 4] = struct.pack('<I', 0xEA000000 | (rel & 0xFFFFFF))           # b hook
    return bytes(a), hook, len(code)


def expand(s):
    """번역 TSV 의 {을} 등 → 표시 코드 글자"""
    for k, v in MARK.items():
        s = s.replace(k, chr(v))
    return s


def simulate(prev, mark):
    """검산용 파이썬 판정(훅과 같은 규칙)"""
    idx = mark - 0xE000
    x = ord(prev) - 0xAC00 if prev else -1
    jong = x % 28 if 0 <= x < 11172 else 0
    a, b = PAIRS[idx]
    ch = a if jong else b
    if idx == 4 and jong == 8:
        ch = b
    return ch or ''


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    h, c = build()
    print(hex(h), len(c))
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
    for i in md.disasm(c[:-4 - 4 * len(PAIRS) - 12], h):
        print(hex(i.address), i.mnemonic, i.op_str)
    for w in ('발톱', '안장', '칼', '초코보', '물', '3'):
        print(w, ''.join(simulate(w[-1], m) for m in range(0xE000, 0xE007)))
