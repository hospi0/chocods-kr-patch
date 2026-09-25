# -*- coding: utf-8 -*-
r"""조사 자동 선택 — ARM9 글리프 번호 함수(NNS GetGlyphIndex 꼴, 0x2031178: r0 글꼴, r1 글자 코드)에 훅.

번역문에 «조사 표시 코드»(사용자 영역 U+E000‥)를 쓰면, 훅이 «직전에 조회한 글자»의 받침을 보고 알맞은 조사 글자로 바꿔 원래 함수로 넘긴다.
한글은 빌드 때 쓰는 음절만 U+F000‥ 으로 옮겨 적는다(assign — [받침 없음][ㄹ 받침][그 밖] 순서, 글꼴도 같은 코드) → 훅은 경계 비교만.
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


PUA_BASE = 0xF000             # 한글 음절을 옮겨 적는 사용자 영역(글꼴 CMAP 방식 0 한 블록 — nftr.rebuild)


def jong_class(ch):
    """0 = 받침 없음 · 1 = ㄹ 받침 · 2 = 그 밖 받침"""
    j = (ord(ch) - 0xAC00) % 28
    return 0 if j == 0 else 1 if j == 8 else 2


def assign(used):
    """쓰는 한글 음절 → 사용자 영역 코드. [받침 없음][ㄹ][그 밖] 순서로 붙여 훅이 경계 두 개로 받침을 가린다.
    돌려줌: (한글→코드 dict, 받침 없음 수 a, a+ㄹ 수 al, 전체 n)"""
    used = set(used) | {c for pr in PAIRS for c in pr if c}
    order = sorted(used, key=lambda c: (jong_class(c), ord(c)))
    remap = {c: PUA_BASE + k for k, c in enumerate(order)}
    a = sum(1 for c in order if jong_class(c) == 0)
    al = a + sum(1 for c in order if jong_class(c) == 1)
    return remap, a, al, len(order)


def build(pua):
    """pua = assign(...) 결과. 직전 글자 코드 x = 직전 − PUA_BASE: x ≥ n(부호 없는 비교, 음수 포함) 또는 x < a → 받침 없음,
    x < al → ㄹ(8), 그 밖 → 받침 있음(1). 조사 표 = 옮겨 적은 코드."""
    remap, a, al, n = pua
    hook = FREE_START
    asm = f'''
        push {{r3, lr}}
        ldr  r3, state_p
        sub  r2, r1, #0xE000
        cmp  r2, #7
        bhs  store
        ldr  r12, [r3]
        ldr  lr, base
        sub  r12, r12, lr
        ldr  lr, cnt_n
        cmp  r12, lr
        bhs  nojong
        ldr  lr, cnt_a
        cmp  r12, lr
        blo  nojong
        ldr  lr, cnt_al
        cmp  r12, lr
        movlo r12, #8
        movhs r12, #1
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
    base:    .word {PUA_BASE}
    cnt_n:   .word {n}
    cnt_a:   .word {a}
    cnt_al:  .word {al}
    ptable:
    '''
    ks = keystone.Ks(keystone.KS_ARCH_ARM, keystone.KS_MODE_ARM)
    enc, _ = ks.asm(asm, hook)
    code = bytearray(enc)
    for x, y in PAIRS:
        code += struct.pack('<HH', remap[x], remap[y] if y else NULL)
    state = hook + len(code)
    code += bytes(4)
    sp_off = len(enc) - 20                 # state_p 는 ptable 앞 다섯 번째 워드
    struct.pack_into('<I', code, sp_off, state)
    assert hook + len(code) <= FREE_END
    return hook, bytes(code)


def patch_arm9(arm9, pua):
    a = bytearray(arm9)
    s, e = FREE_START - ARM9, FREE_END - ARM9
    assert not any(a[s:e]), '빈 행이 비어 있지 않음'
    hook, code = build(pua)
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
    """검산용 파이썬 판정(한글 기준 — 훅과 같은 규칙)"""
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
    pua = assign('발톱안장칼초코보물')
    h, c = build(pua)
    print(hex(h), len(c))
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
    for i in md.disasm(c[:-4 - 4 * len(PAIRS) - 20], h):
        print(hex(i.address), i.mnemonic, i.op_str)
