# -*- coding: utf-8 -*-
r"""파일 선택 화면 로고(UI/TM/base_16: 4bpp BG 256×192, 칸마다 16색 팔레트, 224 타일) 를 한글 로고로 «통째로» 다시 만든다.

처음 방식(원본 팔레트에 억지로 맞추고 «안 바뀐 칸은 원본 유지»)은 부제가 뭉개지고 원본 일본어 획이 남았다(PoC-2b 실기).
  1) 목표 그림 = 확정 로고 v13. 톱니 몸체 자리(스프라이트가 덮음)는 원본 base_16 화소. 흰 바탕도 «불투명 흰색» — 원본 판이 흰색으로 뒤층(타이틀 그림)을 가린다(투명으로 했더니 바탕 분홍·SQUARE ENIX 가 비침, PoC-2c).
  2) 팔레트 0‥13 을 새로 뽑는다(14벌 × 15색): 칸 평균색 k-means 로 칸을 묶고, 묶음마다 화소 k-means 15색 → 칸 재배정 반복.
     (14·15번 팔레트와 각 팔레트 0번 색은 그대로 — 다른 층이 쓸 수 있다)
  3) 칸마다 색번호 타일 → 같은 타일(뒤집기 포함) 하나로 → 223 개를 넘으면 색 오차가 가장 작은 타일끼리 합친다.
"""
import struct
import numpy as np

NPAL = 14
LIMIT = 224
MAX_TILES = 400          # 파일 선택 스테이트 VRAM: 문자 0x4200(뱅크 H) 뒤 ~0x7800(화면 배치) 까지 비어 있음 = 432칸(docs §15)


def _to15(c):
    r, g, b = [min(31, max(0, int(round(v / 8.0)))) for v in c]
    return r | (g << 5) | (b << 10)


def _from15(v):
    return ((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3)


def _kmeans(X, k, iters=12, seed=0):
    rng = np.random.default_rng(seed)
    X = np.asarray(X, float)
    if len(X) <= k:
        C = np.vstack([X, np.repeat(X[:1], k - len(X), 0)]) if len(X) else np.zeros((k, 3))
        return C
    uniq = np.unique(X, axis=0)
    if len(uniq) <= k:
        return np.vstack([uniq, np.repeat(uniq[:1], k - len(uniq), 0)])
    C = uniq[rng.choice(len(uniq), k, replace=False)]
    for _ in range(iters):
        d = ((X[:, None, :] - C[None]) ** 2).sum(-1)
        a = d.argmin(1)
        for j in range(k):
            m = X[a == j]
            if len(m):
                C[j] = m.mean(0)
    return C


def rebuild(nscr, ncgr, nclr, target, keep_mask=None, orig_render=None):
    """target: PIL RGB 256×192. keep_mask: 화면 좌표 집합(원본 화소 사용), orig_render: 원본 base_16 렌더(RGB)."""
    T = np.asarray(target.convert('RGB')).astype(int).copy()
    if keep_mask:
        O = np.asarray(orig_render.convert('RGB')).astype(int)
        for (x, y) in keep_mask:
            if 0 <= x < 256 and 0 <= y < 192:
                r, g, b = O[y, x]
                if r > 0x90 and g > 0x60 and r > b and r - b < 0x70:   # 톱니 색만 원본 — 옛 「チ」 획 가장자리가 「초」 위 점으로 남았다(PoC-2d)
                    T[y, x] = O[y, x]
    opaque = np.ones(T.shape[:2], bool)                 # 전부 불투명(0번 색 안 씀)
    BW, BH = 32, 24
    blocks = []
    for by in range(BH):
        for bx in range(BW):
            blocks.append((T[by * 8:by * 8 + 8, bx * 8:bx * 8 + 8].reshape(64, 3), opaque[by * 8:by * 8 + 8, bx * 8:bx * 8 + 8].reshape(64)))
    live = [i for i, (_, m) in enumerate(blocks) if m.any()]
    # 1) 칸 묶기
    means = np.array([blocks[i][0][blocks[i][1]].mean(0) for i in live])
    C = _kmeans(means, NPAL, 20)
    assign = {i: int(((means[k] - C) ** 2).sum(1).argmin()) for k, i in enumerate(live)}
    pals = None
    for it in range(6):
        pals = []
        for p in range(NPAL):
            px = [blocks[i][0][blocks[i][1]] for i in live if assign[i] == p]
            X = np.vstack(px) if px else np.zeros((1, 3))
            P = _kmeans(X, 15, 15, seed=p)
            P = np.array([_from15(_to15(c)) for c in P], float)
            pals.append(P)
        for i in live:
            cols, m = blocks[i]
            cs = cols[m]
            errs = [((cs[:, None, :] - P[None]) ** 2).sum(-1).min(1).sum() for P in pals]
            assign[i] = int(np.argmin(errs))
    # 2) 칸 → 색번호 타일
    tiles = {}          # 64 색번호 튜플 → 타일 번호
    order = [tuple([0] * 64)]
    tiles[order[0]] = 0
    entries = [0] * (BW * BH)
    use = {}            # 타일 → [(칸, 팔레트)]

    def flip(t, hf, vf):
        return tuple(t[(7 - y if vf else y) * 8 + (7 - x if hf else x)] for y in range(8) for x in range(8))
    for i in range(BW * BH):
        if i not in assign:
            entries[i] = (0, 0, 0, 0)
            continue
        p = assign[i]
        P = pals[p]
        cols, m = blocks[i]
        idx = tuple(int(((c - P) ** 2).sum(1).argmin()) + 1 if mm else 0 for c, mm in zip(cols, m))
        entries[i] = (idx, p)
    # 같은 타일(뒤집기 포함)
    final = []
    for i, e in enumerate(entries):
        if e == (0, 0, 0, 0):
            final.append((0, 0, 0, 0))
            continue
        idx, p = e
        hit = None
        for hf in (0, 1):
            for vf in (0, 1):
                f = flip(idx, hf, vf)
                if f in tiles:
                    hit = (tiles[f], hf, vf)
                    break
            if hit:
                break
        if not hit:
            tiles[idx] = len(order)
            order.append(idx)
            hit = (tiles[idx], 0, 0)
        final.append((hit[0], hit[1], hit[2], p))
        use.setdefault(hit[0], []).append((i, p, hit[1], hit[2]))
    # 3) 넘치면 합치기 — 타일 a 를 b 로 바꿨을 때 a 를 쓰는 칸들의 색 오차 합이 가장 작은 쌍
    merged = []

    def cost(a, b):
        e = 0
        for (i, p, hf, vf) in use.get(a, []):
            cols, m = blocks[i]
            tb = flip(order[b], hf, vf)
            P = np.vstack([[248, 248, 248], pals[p]])
            e += ((cols - P[list(tb)]) ** 2).sum()
        return e
    while len(order) > MAX_TILES:
        cand = sorted(range(1, len(order)), key=lambda a: len(use.get(a, [])))[:40]
        best = None
        for a in cand:
            for b in range(1, len(order)):
                if a == b:
                    continue
                c = cost(a, b)
                if best is None or c < best[0]:
                    best = (c, a, b)
        c, a, b = best
        merged.append(int(c ** 0.5))
        for (i, p, hf, vf) in use.pop(a, []):
            final[i] = (b, hf, vf, p)
            use.setdefault(b, []).append((i, p, hf, vf))
        # a 를 지우고 번호 당김
        order.pop(a)
        final = [(t - (1 if t > a else 0), hf, vf, p) if t else (t, hf, vf, p) for (t, hf, vf, p) in final]
        use = {(k - (1 if k > a else 0)): v for k, v in use.items()}
    # 쓰기
    i = ncgr.index(b'RAHC')
    csz = struct.unpack_from('<I', ncgr, i + 0x18)[0]
    n_rows = max(csz // 32, (len(order) + 31) // 32 * 32) // 32      # 32칸 줄 단위
    nsz = n_rows * 32 * 32
    data = bytearray(nsz)
    for n, t in enumerate(order):
        for j in range(64):
            data[n * 32 + j // 2] |= t[j] << (4 * (j & 1))
    blk = bytearray(ncgr[i:i + 0x20])
    struct.pack_into('<I', blk, 4, 0x20 + nsz)                  # RAHC 블록 크기
    struct.pack_into('<H', blk, 8, n_rows)                      # 높이(타일 줄)
    struct.pack_into('<I', blk, 0x18, nsz)                      # 문자 데이터 크기
    ncgr2 = bytearray(ncgr[:i]) + blk + bytes(data) + ncgr[i + 0x20 + csz:]
    struct.pack_into('<I', ncgr2, 8, len(ncgr2))                # 파일 크기
    si = nscr.index(b'NRCS')
    ssz = struct.unpack_from('<I', nscr, si + 0x10)[0]
    m = list(struct.unpack_from('<%dH' % (ssz // 2), nscr, si + 0x14))
    for k, (t, hf, vf, p) in enumerate(final):
        m[k] = t | (hf << 10) | (vf << 11) | (p << 12)
    nscr2 = nscr[:si + 0x14] + struct.pack('<%dH' % len(m), *m) + nscr[si + 0x14 + ssz:]
    j = nclr.index(b'TTLP')
    raw = list(struct.unpack_from('<256H', nclr, j + 0x18))
    for p in range(NPAL):
        for k in range(15):
            raw[p * 16 + 1 + k] = _to15(pals[p][k])
    nclr2 = nclr[:j + 0x18] + struct.pack('<256H', *raw) + nclr[j + 0x18 + 512:]
    return nscr2, bytes(ncgr2), nclr2, len(order), merged
