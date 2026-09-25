# -*- coding: utf-8 -*-
r"""타이틀 로고(TL/TL.FBC tl_ue, 256×192 8bpp BG) 한글판 그림 만들기.

  python tools/logo.py <원본 렌더 png> <출력 png> [큰 글자 글꼴]

원본 구조(화소 실측):
  · 큰 글자 「時忘れの迷宮」 = 파란 띠(행마다 단색 그라데이션, x=18 열이 깨끗) 에 «흰 글자를 뚫어 놓은» 꼴.
    띠 아래 가장자리는 글자 밑동을 따라 물결친다(띠 = 사각형 ∪ 글자 부풀림).
  · 부제 「チョコボの不思議なダンジョン」 = 남색 리본(y 81‥93) 위 노란 글자 + 남색 테두리. 키 큰 글자는 리본 위로 테두리 혹.
  · 톱니 안 「シドと」 = 갈색 글자.
  · 종 장식(금색)은 큰 글자 위에 얹혀 있다 → 새 글자 뒤에 다시 올린다.
모든 새 그림은 4배로 그린 뒤 줄여 가장자리를 부드럽게 한다.
"""
import sys
from collections import Counter
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

S = 4
WHITE = (248, 248, 248)
FONT = 'C:/claude/utils/font/'
BIG_FONTS = {
    'hansans': FONT + 'logo/BlackHanSans.ttf',
    'myeongjo': FONT + 'nanum-myeongjo/NanumMyeongjoExtraBold.ttf',
    'gasoek': FONT + 'logo/GasoekOne-Regular.ttf',
}
BOLD = {'myeongjo': 2}                                     # 큰 글자 4배 부풀림(px) — 사용자 «아주 살짝만 두껍게»
SUB_FONT = FONT + 'nanum-gothic/NanumGothicExtraBold.ttf'

BIG_TEXT, BIG_BOX = '시간을 잊는 미궁', (17, 97, 175, 128)      # x0,y0,x1,y1 (1배 좌표)
SUB_TEXT, SUB_BOX = '초코보의 이상한 던전', (75, 81, 207, 92)
GEAR_TEXT, GEAR_BOX = '시드와', (44, 77, 61, 85)
GEAR1_C = (53, 79)                                         # 「시드와」 톱니 중심
ROOF = 4                                                   # 부제 테두리를 글자 위로 더 올리는 높이(px)


def text_mask(text, font_path, box, spacing=0.0):
    """글자를 4배로 그려 box 크기(4배)에 맞춰 늘인 L 마스크 → (마스크, 4배 좌상단)"""
    x0, y0, x1, y1 = box
    f = ImageFont.truetype(font_path, 200)
    parts = []
    for ch in text:
        if ch == ' ':
            parts.append(None)
            continue
        bb = f.getbbox(ch)
        m = Image.new('L', (bb[2] - bb[0] + 4, 260), 0)
        ImageDraw.Draw(m).text((2 - bb[0], 10), ch, font=f, fill=255)
        parts.append(m)
    top = min(p.getbbox()[1] for p in parts if p)
    bot = max(p.getbbox()[3] for p in parts if p)
    sp = int(200 * spacing)
    space = 60
    tw = sum((p.getbbox()[2] - p.getbbox()[0]) if p else space for p in parts) + sp * (len(parts) - 1)
    line = Image.new('L', (tw, bot - top), 0)
    cx = 0
    for p in parts:
        if p is None:
            cx += space + sp
            continue
        bb = p.getbbox()
        line.paste(p.crop((bb[0], top, bb[2], bot)), (cx, 0))
        cx += bb[2] - bb[0] + sp
    w, h = (x1 - x0) * S, (y1 - y0) * S
    return line.resize((w, h), Image.LANCZOS), (x0 * S, y0 * S)


def grow(m, px):
    return m.filter(ImageFilter.MaxFilter(2 * px + 1)) if px > 0 else m


def paste_mask(canvas, mask, pos):
    full = Image.new('L', canvas.size, 0)
    full.paste(mask, pos)
    return full


def down(img):
    return img.resize((img.width // S, img.height // S), Image.LANCZOS)


def make(src_path, out_path, big='hansans'):
    src = Image.open(src_path).convert('RGB')
    W, H = src.size
    sp = src.load()
    out = src.copy()
    op = out.load()

    # ── 원본에서 읽는 것: 띠 그라데이션(x=18 열), 종 장식, 리본 색
    band = {}                                           # 행마다 띠에서 가장 흔한 파랑(한 열만 보면 왼쪽 가장자리 음영이 섞인다)
    for y in range(94, 132):
        cs = [sp[x, y] for x in range(14, 250) if sp[x, y][0] < 0x40 and sp[x, y][2] > 0x60]
        band[y] = Counter(cs).most_common(1)[0][0] if cs else band[y - 1]
    for y in range(132, 140):
        band[y] = band[131]
    bell = {(x, y): sp[x, y] for x in range(20, 50) for y in range(112, 136)
            if (lambda c: c[0] > 0x80 and c[0] >= c[1] > c[2] + 0x18)(sp[x, y])}
    navy_row = {}
    for y in range(66, 94):
        cs = [sp[x, y] for x in range(60, 250) if sp[x, y][0] < 0x30 and sp[x, y][2] > 0x50]
        if cs:
            navy_row[y] = Counter(cs).most_common(1)[0][0]
    rib = {y: Counter(sp[x, y] for x in range(120, 250) if sp[x, y][0] < 0x30 and sp[x, y][2] > 0x50).most_common(1)[0][0]
           for y in range(81, 94)}

    # ── 1) 큰 글자 영역 비우기(흰 바탕) — ®(x≥176, y≥121) 와 DS 는 둔다
    for x in range(12, 177):
        for y in range(94, 138):
            if x >= 176 and y >= 121:
                continue
            op[x, y] = WHITE
    # ── 2) 새 띠 = 사각형 ∪ 글자 2px 부풀림, 4배로 그려 줄임
    tm, pos = text_mask(BIG_TEXT, BIG_FONTS[big], BIG_BOX, 0.02)
    T4 = paste_mask(Image.new('L', (W * S, H * S)), tm, pos)
    rect = Image.new('L', (W * S, H * S), 0)
    ImageDraw.Draw(rect).rounded_rectangle((15 * S, 94 * S - 8, 177 * S, 127 * S), radius=3 * S, fill=255)
    B4 = ImageChops.lighter(rect, grow(T4, 2 * S))
    grad = Image.new('RGB', (W, H), WHITE)
    gp = grad.load()
    for y in range(H):
        for x in range(W):
            gp[x, y] = band.get(y, WHITE)
    B = down(B4)
    reg = (12, 90, 178, 138)
    out.paste(grad.crop(reg), reg[:2], B.crop(reg))
    # 원래 띠(오른쪽, DS 쪽)와 윗줄은 원본 유지
    for x in range(12, 177):
        for y in range(94, 96):
            if B.getpixel((x, y)) > 200:
                op[x, y] = sp[x, y] if sp[x, y][2] > 0x60 and sp[x, y][2] - sp[x, y][0] > 0x50 else band[y]   # 회색 섞인 옛 획 가장자리는 버림
    # 띠 왼쪽 위 모서리는 원본의 둥근 테두리 그대로(새 글자 부풀림이 모서리를 네모지게 만들었다)
    for x in range(12, 22):                              # 새 띠가 원본보다 1 px 왼쪽·위라 모서리도 (−1, −1) 옮겨 붙인다(사용자)
        for y in range(91, 101):
            op[x - 1, y - 1] = sp[x, y]
    for x in range(12, 22):                              # 옮기면서 원본 띠 윗줄(y 94)이 y 93 으로 올라와 생긴 3 px 찌꺼기
        op[x, 93] = WHITE
    # ── 3) 흰 글자
    Tw = down(grow(T4, BOLD.get(big, 0)))
    out.paste(Image.new('RGB', (W, H), WHITE).crop(reg), reg[:2], Tw.crop(reg))
    for (x, y), c in bell.items():
        op[x, y] = c
    for x in range(176, 182):                          # 「宮」 오른쪽 끝 조각·띠 사각형 이음매 지우기(금색 D 는 둔다)
        for y in range(94, 121):
            if not (sp[x, y][0] > sp[x, y][2] + 0x30):
                op[x, y] = band[y]

    # ── 4) 부제: 리본 다시 칠하고 노란 글자 + 남색 테두리
    body = lambda c: c != WHITE and not (c[0] < 0x40 and c[2] > 0x50) and not (c[0] > 0xc0 and c[2] < 0x60)
    gear = lambda c: c[0] > 0x90 and c[1] > 0x60 and c[0] > c[2] and c[0] - c[2] < 0x70   # 톱니 색(베이지·분홍)
    for x in range(62, 214):
        for y in range(73, 94):
            c = sp[x, y]
            if c == WHITE or (x < 97 and gear(c)):
                continue
            if y >= 81:                                  # 리본: 원본 모양 그대로 남색
                op[x, y] = rib[y]
            elif c[0] > 0xa0 and c[2] < 0x70:            # 리본 위(톱니 쪽 혹 포함)는 원본 그대로, 노란 획만 남색으로
                op[x, y] = rib.get(y, (8, 48, 120))
    sm, spos = text_mask(SUB_TEXT, SUB_FONT, SUB_BOX, 0.04)
    S4 = paste_mask(Image.new('L', (W * S, H * S)), sm, spos)
    # 남색 장식 테두리: 원본처럼 글자 위로 «지붕»처럼 두껍게(사용자) — 2.5 px 부풀림을 위로 ROOF px 까지 끌어올려 합친다
    g4 = grow(S4, int(2.5 * S))
    roof = g4.copy()
    for dy in range(S, ROOF * S + 1, S):
        roof = ImageChops.lighter(roof, ImageChops.offset(g4, 0, -dy))
    edge = down(roof.filter(ImageFilter.GaussianBlur(S * 0.4)))
    ImageDraw.Draw(edge).rectangle((0, 94, W, H), fill=0)   # 리본 아래(큰 글자 띠)로 번지지 않게 — 띠 윗줄에 짙은 줄이 생겼다
    fill = down(S4)
    navy = Image.new('RGB', (W, H), WHITE)              # 테두리 색 = 원본 남색 행별 그라데이션(위 짙음 → 아래 밝음)
    npx = navy.load()
    for y in range(H):
        for x in range(W):
            npx[x, y] = navy_row.get(y, rib.get(y, (8, 48, 120)))
    yel = Image.new('RGB', (W, H))
    yp = yel.load()
    for y in range(H):
        t = min(1, max(0, (y - SUB_BOX[1]) / (SUB_BOX[3] - SUB_BOX[1])))
        c = tuple(int(a + (b - a) * t) for a, b in zip((255, 236, 120), (240, 176, 0)))
        for x in range(W):
            yp[x, y] = c
    out.paste(navy, (0, 0), edge)
    out.paste(yel, (0, 0), fill)

    # ── 5) 톱니 「시드와」: 원본 톱니 아래 이빨(y 88‥98)이 띠 위에 얹혀 있었다 → 새 띠 위에 원본 화소 그대로 다시 붙인다
    for x in range(30, 72):
        for y in range(86, 98):
            if y >= 94 and not 41 <= x <= 63:            # 띠 위 이빨은 x 41‥63 뿐(그 밖 밝은 점은 옛 글자 획 — 「간」 위 흰 점)
                continue
            if gear(sp[x, y]) or (x < 66 and body(sp[x, y]) and gear(sp[x, y - 1])):
                op[x, y] = sp[x, y]
    # 톱니 오른쪽 아래(x 62‥68, y 86‥93)는 원본에서 「チ」 획 끝이 덮고 있었다 → 톱니 원(중심 53,79 반지름 16.5) 안쪽이면
    # 왼쪽 이웃 톱니 색으로 이어 채운다(노란 획을 남색으로 지우면서 생긴 홈)
    for y in range(86, 94):
        for x in range(62, 69):
            c = sp[x, y]
            if (x - GEAR1_C[0]) ** 2 + (y - GEAR1_C[1]) ** 2 <= 16.5 ** 2 and not gear(c) and not (c[0] < 0x40 and c[2] > 0x50):
                op[x, y] = op[x - 1, y]
    for x in range(40, 68):
        for y in range(70, 92):
            c = sp[x, y]
            if c[0] < 0xc8 and c[0] > c[2] + 0x20 and c[1] < 0xb8:
                op[x, y] = (224, 208, 184)
    gm, gpos = text_mask(GEAR_TEXT, SUB_FONT, GEAR_BOX, 0.03)
    G4 = paste_mask(Image.new('L', (W * S, H * S)), gm, gpos)
    out.paste(Image.new('RGB', (W, H), (104, 48, 16)), (0, 0), down(grow(G4, 1)))
    out.save(out_path)
    return out


if __name__ == '__main__':
    make(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 'hansans')
