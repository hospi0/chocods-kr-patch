# -*- coding: utf-8 -*-
r"""영상 자막 한글화 — work/mov_subs.tsv 의 자막을 MODS(Mobiclip) 영상에 입혀 다시 인코딩.

  python tools/movsub.py [--preview]      → work/mov_ko/<이름>.mods  (--preview 면 자막 장면 비교 그림만 my files/그래픽)

방식(사용자 결정 2026-09-25): 원본 자막 자리에 검은 네모 바탕 → 흰 글씨 + 검은 1 px 테두리(갈무리11).
해독 = ffmpeg 9(mobiclip 디코더), 인코딩 = mobipeg(ffmpeg + mobiclip 인코더·mods 먹서).
색: 디코더가 내는 면은 YCgCo(Y·Cg·Co) 그대로 → 네모 안쪽만 RGB 로 그려 YCgCo 로 되돌려 넣고, 나머지 화소는 원본 면 그대로.
음성: DSB_U(VX 코드북)는 원본 음성을 풀어 다시 인코딩(패킷 복사는 음성이 빠짐). DSA_L 은 음성 없음. (DSM_U 는 FastAudio 먹싱이 잘려서 손대지 않음.)
"""
import os
import subprocess
import sys

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as sw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bdf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF9 = r'C:\claude\utils\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe'
MOBI = r'C:\claude\utils\mobipeg-windows-x86_64\ffmpeg.exe'
FONT = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.bdf'
SRC = os.path.join(ROOT, 'work', 'mov')
OUT = os.path.join(ROOT, 'work', 'mov_ko')
SUBS = os.path.join(ROOT, 'work', 'mov_subs.tsv')
AUDIO = {'DSB_U': ('codebook', 'vx_audio')}   # 원본 음성(-mo_audio, 인코더) — 풀어서 다시 인코딩
W, H = 256, 192
FS = W * H * 3 // 2
TOP = 130                              # 자막을 찾는 아래쪽 띠
PAD = 4                                # 네모 여백
LINE = 14                              # 줄 간격(px)
BOX = 0                                # 네모 바탕 색(검정 — 사용자 결정, 흰 네모는 글자가 비어 보였다)


def decode(p):
    raw = subprocess.run([FF9, '-v', 'error', '-i', p, '-f', 'rawvideo', '-pix_fmt', 'yuv420p', '-'],
                         capture_output=True, check=True).stdout
    n = len(raw) // FS
    return np.frombuffer(raw[:n * FS], np.uint8).reshape(n, FS).copy()


def planes(f):
    Y = f[:W * H].reshape(H, W)
    U = f[W * H:W * H * 5 // 4].reshape(H // 2, W // 2)
    V = f[W * H * 5 // 4:].reshape(H // 2, W // 2)
    return Y, U, V


def to_rgb(f):
    Y, U, V = planes(f)
    Y = Y.astype(int)
    Cg = U.repeat(2, 0).repeat(2, 1).astype(int) - 128
    Co = V.repeat(2, 0).repeat(2, 1).astype(int) - 128
    t = Y - Cg
    return np.clip(np.stack([t + Co, Y + Cg, t - Co], -1), 0, 255)


def sub_mask(f, grey=False):
    """원본 자막 화소(흰 글자 + 그 둘레 검은 테두리) — 아래 띠 기준 좌표. grey = 회색 「…」『』 까지(배경 오검출 있음)"""
    im = to_rgb(f)[TOP:]
    wht = (im.min(-1) > 140) & (im.max(-1) - im.min(-1) < 40) if grey else im.min(-1) > 215
    dk = im.max(-1) < 60
    near_dk = sw(np.pad(dk, 2), (5, 5)).any((-1, -2))
    near_wh = sw(np.pad(wht, 2), (5, 5)).any((-1, -2))
    return (wht & near_dk) | (dk & near_wh)


def render_text(lines, G, asc):
    """→ (역할 판: 0 없음 · 1 흰 글자 · 2 검은 테두리)"""
    rows = []
    for ln in lines:
        glyphs = []
        for ch in ln:
            g = G.get(ord(ch))
            adv = g[4] if g else 6
            arr, _ = bdf.render(G, asc, ord(ch), adv, LINE, asc)
            glyphs.append(arr)
        w = sum(len(a[0]) for a in glyphs)
        rows.append((w, glyphs))
    Wt = max(w for w, _ in rows) + 2
    Ht = LINE * len(rows) + 2
    ink = np.zeros((Ht, Wt), bool)
    for k, (w, glyphs) in enumerate(rows):
        x = 1 + (Wt - 2 - w) // 2
        for a in glyphs:
            a = np.array(a, bool)
            ink[1 + k * LINE:1 + k * LINE + a.shape[0], x:x + a.shape[1]] |= a
            x += a.shape[1]
    border = sw(np.pad(ink, 1), (3, 3)).any((-1, -2)) & ~ink
    role = np.where(ink, 1, np.where(border, 2, 0))
    ys, xs = np.nonzero(role)
    return role[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def paint(frames, a, b, lines, G, asc):
    """프레임 a‥b 에 네모 + 한글. 원본 자막 자리 = 구간 전체 자막 화소의 합집합 경계."""
    union = np.zeros((H - TOP, W), bool)
    broad = np.zeros((H - TOP, W), bool)
    for i in range(a, b + 1):
        union |= sub_mask(frames[i])
        broad |= sub_mask(frames[i], grey=True)
    ys, xs = np.nonzero(union)                                 # 세로 = 흰 글자 줄 범위
    oy0, oy1 = ys.min(), ys.max()
    band = broad[oy0:oy1 + 1]                                  # 가로 = 그 줄 안의 회색 부호까지, 흰 글자 경계에서 이어진 것만
    cols = np.nonzero(band.any(0))[0]
    ox0, ox1 = xs.min(), xs.max()
    while ox1 + 1 < W and (ox1 + 1 in cols or ox1 + 2 in cols or ox1 + 3 in cols):
        ox1 += 1
    while ox0 - 1 >= 0 and (ox0 - 1 in cols or ox0 - 2 in cols or ox0 - 3 in cols):
        ox0 -= 1
    oy0 += TOP; oy1 += TOP
    role = render_text(lines, G, asc)
    th, tw = role.shape
    cy, cx = (oy0 + oy1 + 1) // 2, (ox0 + ox1 + 1) // 2
    ty, tx = cy - th // 2, cx - tw // 2
    by0, by1 = max(0, min(oy0, ty) - PAD), min(H - 1, max(oy1, ty + th - 1) + PAD)
    bx0, bx1 = max(0, min(ox0, tx) - PAD), min(W - 1, max(ox1, tx + tw - 1) + PAD)
    by0 -= by0 & 1; bx0 -= bx0 & 1; by1 |= 1; bx1 |= 1       # 색 면(2×2)에 맞춤
    by1 = min(by1, H - 1); bx1 = min(bx1, W - 1)
    for i in range(a, b + 1):
        rgb = to_rgb(frames[i]).astype(float)
        rgb[by0:by1 + 1, bx0:bx1 + 1] = BOX                        # 네모 바탕
        reg = rgb[ty:ty + th, tx:tx + tw]
        reg[role == 1] = 255
        reg[role == 2] = 0
        R, G_, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        Yn = (R + 2 * G_ + B) / 4
        Cg = (-R + 2 * G_ - B) / 4 + 128
        Co = (R - B) / 2 + 128
        Y, U, V = planes(frames[i])
        Y[by0:by1 + 1, bx0:bx1 + 1] = np.clip(np.rint(Yn[by0:by1 + 1, bx0:bx1 + 1]), 0, 255)
        sl = np.s_[by0 // 2:(by1 + 1) // 2, bx0 // 2:(bx1 + 1) // 2]
        blk = lambda P: P[by0:by1 + 1, bx0:bx1 + 1].reshape((by1 + 1 - by0) // 2, 2, (bx1 + 1 - bx0) // 2, 2).mean((1, 3))
        U[sl] = np.clip(np.rint(blk(Cg)), 0, 255)
        V[sl] = np.clip(np.rint(blk(Co)), 0, 255)
    return (bx0, by0, bx1, by1)


def extend(frames, a, b):
    """문턱 아래로 희미하게 남은 앞뒤 프레임까지 넓힌다"""
    while a > 0 and sub_mask(frames[a - 1]).sum() > 5:
        a -= 1
    while b + 1 < len(frames) and sub_mask(frames[b + 1]).sum() > 5:
        b += 1
    return a, b


def load_subs():
    out = {}
    for ln in open(SUBS, encoding='utf-8'):
        if ln.startswith('#') or not ln.strip():
            continue
        name, a, b, jp, ko = ln.rstrip('\n').split('\t')
        out.setdefault(name, []).append((int(a), int(b), ko.split('\\n')))
    return out


def encode(name, frames, dst):
    raw = dst + '.yuv'
    frames.tofile(raw)
    cmd = [MOBI, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'yuv420p',
           '-s', '%dx%d' % (W, H), '-r', '12', '-i', raw]
    wav = dst + '.wav'
    if name in AUDIO:           # 패킷 복사(-c:a copy)는 음성이 통째로 빠진다 → 풀어서 다시 인코딩(왕복 시험 길이 일치)
        subprocess.run([MOBI, '-hide_banner', '-loglevel', 'error', '-y', '-i', os.path.join(SRC, name + '.mods'),
                        '-map', '0:a', '-c:a', 'pcm_s16le', wav], check=True)
        cmd += ['-i', wav, '-map', '0:v', '-map', '1:a', '-c:a', AUDIO[name][1], '-mo_audio', AUDIO[name][0]]
    # ⛔ -mobiclip 기본값 0 = 표준 H.264 + moflex 비트 1(3DS 방식) → ffmpeg 는 풀지만 DS 에선 영상이 먹통(t3 실기).
    #    2 = MODS(DS) 표, moflex 0 → 프레임 머리 비트가 원본과 같은 꼴.
    cmd += ['-c:v', 'mobiclip', '-mobiclip', '2', '-moflex', '0', '-f', 'mods', dst]
    subprocess.run(cmd, check=True)
    if os.path.exists(wav):
        os.remove(wav)
    os.remove(raw)


def main():
    preview = '--preview' in sys.argv
    G, asc = bdf.load(FONT)
    os.makedirs(OUT, exist_ok=True)
    shots = []
    for name, subs in load_subs().items():
        frames = decode(os.path.join(SRC, name + '.mods'))
        orig = frames.copy()
        for a, b, lines in subs:
            a, b = extend(orig, a, b)
            box = paint(frames, a, b, lines, G, asc)
            print('  %s %d‥%d 네모 %s 「%s」' % (name, a, b, box, ' / '.join(lines)))
            shots.append((name, (a + b) // 2, orig, frames))
        if not preview:
            dst = os.path.join(OUT, name + '.mods')
            encode(name, frames, dst)
            print('  → %s %d B (원본 %d B)' % (dst, os.path.getsize(dst), os.path.getsize(os.path.join(SRC, name + '.mods'))))
    if preview:
        from PIL import Image
        ims = [Image.fromarray(np.concatenate([to_rgb(o[k]), to_rgb(f[k])], 1).astype(np.uint8)) for _, k, o, f in shots]
        sheet = Image.new('RGB', (W * 2, H * len(ims)))
        for n, im in enumerate(ims):
            sheet.paste(im, (0, n * H))
        p = os.path.join(ROOT, 'my files', '그래픽', '20_영상자막(왼원본_오른한글).png')
        sheet.save(p)
        print('  미리보기', p)


if __name__ == '__main__':
    main()
