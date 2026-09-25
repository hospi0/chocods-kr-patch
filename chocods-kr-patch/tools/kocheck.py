# -*- coding: utf-8 -*-
r"""번역 검사(ROM 없이) — 원문 work/alltext.tsv 와 번역 work/ko/*.tsv 를 1:1 로 맞춰 본다.

  python tools/kocheck.py [번역 폴더|tsv …] [--rare N] [--todo]

검사(오류면 종료 코드 1):
  · 번호가 원문에 있는가 / 두 번 번역했는가
  · 태그 보존: {ESC}XX}1~ 색·{15}CT}1~ 정렬·{11}}1~·%d·아이콘 글자(ы щ ┓ э ① …) 가 원문과 같은 개수
  · 색 태그 짝: 색을 켜면 {ESC}WT}1~ 로 닫고 나서 다음 색
  · 쪽({13}) 수 같음 · 쪽마다 줄 수 ≤ 원문 그 문자열의 최대 줄 수
  · 줄 폭 ≤ 예산(한글·전각 1, 반각 0.5, 부호 뒤 공백은 빌더가 지우므로 뺌) — 예산은 «상자 폭»: 표마다 원문 최대 줄 폭(BUDGET)
  · 가나·한자 남음 · KS X 1001 밖 음절 · 모르는 조사 표시
보고: 본편 글꼴 한글 음절 수(한자 칸 606 / 가나 칸까지 ≈880) · --rare N 이면 N 회 이하 음절 목록(줄이기 후보)
      --todo 면 아직 안 한 원문 수(표별).
"""
import glob
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'alltext.tsv')
KO_DIR = os.path.join(ROOT, 'work', 'ko')
FONT_SLOTS = 606          # dsr_fnt 한자 칸(nftr.replace_kanji) — docs §15
FONT_SLOTS_KANA = 880     # 가나 칸까지 갈아 끼울 때(docs §19)
JOSA = {'{을}': '을를', '{이}': '이가', '{은}': '은는', '{과}': '과와', '{으}': '으', '{아}': '아야', '{이다}': '이'}

# 상자 폭(반각 0.5 단위 합) — 원문 표의 줄 폭 분포에서(보통 최댓값). 없는 표는 그 표 원문 최대 줄 폭.
BUDGET = {
    'EVTMSG': 18,          # 대사 상자 — 원문 18 칸 14줄(19 이상은 특수 줄)
    'UISHPMSG': 19, 'UIRW': 19, 'UIRCHRMSG': 19,
    'ITEM_ALL_TXT1': 16,   # 아이템 긴 설명(메모·일기) — 16 칸 209줄
    'ITEM_ALL_TXT0': 22,   # 아이템 설명 — 22 칸 10줄
    'PLY_ABT': 20,
}
PER_STRING = ('SYSMSG',)   # 창이 제각각 → 그 문자열 원문 최대 줄 폭
ICON_OK = {('dt_SYSMSG.txtbin', 14),   # 「АБВГДЕ」 = だいじなもの 전용 글리프 → 한글로 바꿈(docs §13)
           ('dt_SYSMSG.txtbin', 191), ('dt_SYSMSG.txtbin', 429), ('dt_SYSMSG.txtbin', 430),   # ┣┳ = 좁은 「ギル」 → 길
           ('dt_SYSMSG.txtbin', 420), ('dt_SYSMSG.txtbin', 421),   # ┷┿┝ム┰ず┥る = 좁은 「アイテムあずける/うけとる」
           ('dt_UIRCHRMSG.txtbin', 16), ('dt_ITEM_ALL_TXT1.txtbin', 497)}   # ⑮ = 「転」 글리프 → 전생의 불꽃

# 편지(ITEM_ALL_TXT1 456‥496)의 분홍 글자({ESC}PK}1~)를 이어 읽으면 합언어(DT_UIRWW) — 합언어는 일본어 자판 그대로라
# 한국어 편지에선 분홍 음절이 합언어의 한글 발음이 되게 쓴다(つ=쓰, か·た행 거센소리, 장음 う 는 「우」). 분홍 태그 개수는 원문과 달라도 된다.
HIDDEN = {456: '오모이데가이타이', 457: '보우켄노하지마리다', 458: '아케노묘우조우', 459: '키이로이텐시',
          461: '사리게나이이노리', 462: '만게쓰노요루', 463: '이치린노하나', 464: '카가미노우미', 465: '타이세쓰나히토',
          466: '아이스루코코로', 468: '보쿠노이모우토', 469: '아타시노아니키', 470: '쓰타에타이아이',
          471: '쓰요쿠케다카쿠', 472: '세카이노히호우', 475: '키보우노호시', 476: '코코요리토와니', 477: '나쓰노소라',
          478: '아나타토와타시', 479: '코오레루토키', 480: '메데타이아타마', 481: '코코로노테키', 496: '로만노세카이'}
ACROSTIC = {504: '기관차조사해보라고요'}   # 줄 첫 글자(원문 きかんしゃしらべろよ = 기관차를 조사해 봐)

TAG = re.compile(r'\{ESC\}[A-Z]{2}\}\d~|\{[0-9A-Fa-f]{2}\}(?:[A-Z]{2}\}\d~|\}\d~)?|%[0-9]*[dsxc]|\\n')
KANA_KANJI = re.compile(r'[ぁ-ヺヽ-ヿ㐀-鿿ｦ-ﾟ々〆]')   # ・ー 는 부호
COLOR = re.compile(r'\{ESC\}([A-Z]{2})\}\d~')


def hangul(c):
    return 0xAC00 <= ord(c) <= 0xD7A3


def ks_set():
    out = set()
    for hi in range(0xB0, 0xC9):
        for lo in range(0xA1, 0xFF):
            out.add(bytes((hi, lo)).decode('cp949'))
    return out


def load(path):
    """줄 번호, [파일, 안쪽 경로, 번호, 글] — 머리줄 「@ 파일 안쪽경로」 아래 「번호 번역」 도 펼친다."""
    cur = None
    for n, line in enumerate(open(path, encoding='utf-8'), 1):
        line = line.rstrip('\n')
        if not line or line.startswith('#'):
            continue
        p = line.split('\t')
        if p[0] == '@':
            cur = p[1:3]
            continue
        yield n, (cur + p if len(p) == 2 and cur else p)


def source():
    src = {}
    for _, p in load(SRC):
        src[(p[0], p[1], int(p[2]))] = p[4]
    return src


def squeeze(s):
    return re.sub(r'([,.!?:;]) +', r'\1', s) if any(hangul(c) for c in s) else s


def plain(s):
    """태그 뺀 글(줄바꿈 \n·쪽 {13} 은 남김)"""
    s = s.replace('{13}', '\x13')
    s = re.sub(r'\{ESC\}[A-Z]{2}\}\d~|\{[0-9A-Fa-f]{2}\}(?:[A-Z]{2}\}\d~|\}\d~)?', '', s)
    for k in JOSA:
        s = s.replace(k, '가')          # 조사 한 글자 폭
    return s


def width(line):
    return sum(0.5 if unicodedata.east_asian_width(c) in 'NaH' else 1 for c in line.rstrip())


def pages(s):
    return [pg.split('\\n') for pg in plain(s).split('\x13')]


def icons(s):
    """아이콘·특수 글자(원문이 키릴·괘선·원숫자 자리를 빌려 씀) — 한글·가나·한자·ASCII·흔한 부호 밖"""
    s = TAG.sub('', s.replace('{13}', ''))
    for k in JOSA:
        s = s.replace(k, '')
    return Counter(c for c in s if ord(c) > 0x7E and not hangul(c) and not KANA_KANJI.match(c)
                   and c not in '〇·　！？、。「」『』（）…・～ー―：；，．＋－％／＝＆＊＃＠＜＞【】［］｛｝〜×→←↑↓☆★○●◎◇◆□■△▲▽▼♪♥“”‘’　０１２３４５６７８９'
                   and not ('Ａ' <= c <= 'ｚ'))


def color_state(s):
    """색 태그 짝 오류 목록, 끝에 열린 색"""
    bad, cur = [], None
    for m in COLOR.finditer(s):
        c = m.group(1)
        if c == 'WT':
            cur = None
        elif cur:
            bad.append('색 %s 닫기 전에 %s' % (cur, c))
        else:
            cur = c
    return bad, cur


def budget_of(inner, orig):
    for k, v in BUDGET.items():
        if k in inner:
            return v
    return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    rare = None
    if '--rare' in sys.argv:
        rare = int(sys.argv[sys.argv.index('--rare') + 1])
        args = [a for a in args if a != str(rare)]
    paths = []
    for a in args or [KO_DIR]:
        paths += sorted(glob.glob(os.path.join(a, '*.tsv'))) if os.path.isdir(a) else [a]
    src = source()
    table_max = defaultdict(float)
    for (f, inner, i), t in src.items():
        for pg in pages(t):
            for ln in pg:
                table_max[inner] = max(table_max[inner], width(ln))
    KS = ks_set()
    errs = []
    done = {}
    syl = Counter()
    where = {}
    for path in paths:
        for n, p in load(path):
            loc = '%s:%d' % (os.path.relpath(path, ROOT), n)
            if len(p) != 4:
                errs.append('%s 칸 수 %d(4 이어야)' % (loc, len(p)))
                continue
            f, inner, i, ko = p
            key = (f, inner, int(i))
            if key not in src:
                errs.append('%s 원문에 없는 번호 %s' % (loc, key))
                continue
            if key in done:
                errs.append('%s 중복 번역(앞 %s)' % (loc, done[key]))
            done[key] = loc
            jp = src[key]
            e = []
            letter = inner.endswith('dt_ITEM_ALL_TXT1.txtbin') and (int(i) in HIDDEN or int(i) in ACROSTIC)
            if letter:
                pink = ''.join(re.findall(r'\{ESC\}PK\}1~(.*?)\{ESC\}WT\}1~', ko.replace('\\n', '')))
                want = HIDDEN.get(int(i), '')
                if pink != want:
                    e.append('분홍 글자 「%s」 ≠ 합언어 발음 「%s」' % (pink, want))
                if int(i) in ACROSTIC:
                    head = ''.join(ln.strip()[:1] for ln in ko.split('\\n'))
                    if head != ACROSTIC[int(i)]:
                        e.append('줄 첫 글자 「%s」 ≠ 「%s」' % (head, ACROSTIC[int(i)]))
            strip_pk = (lambda t: t.replace('{ESC}PK}1~', '').replace('{ESC}WT}1~', '')) if letter else (lambda t: t)
            if Counter(TAG.findall(strip_pk(jp))) - Counter(TAG.findall(strip_pk(ko))) - Counter({'\\n': 99}) or \
               Counter(TAG.findall(strip_pk(ko))) - Counter(TAG.findall(strip_pk(jp))) - Counter({'\\n': 99}):
                a = Counter(TAG.findall(strip_pk(jp))); b = Counter(TAG.findall(strip_pk(ko)))
                a.pop('\\n', None); b.pop('\\n', None)
                e.append('태그 다름 원문%s 번역%s' % (dict(a - b), dict(b - a)))
            if icons(jp) != icons(ko) and (inner.split('/')[-1], int(i)) not in ICON_OK:
                e.append('아이콘 다름 원문%s 번역%s' % (dict(icons(jp) - icons(ko)), dict(icons(ko) - icons(jp))))
            if ko.count('{13}') != jp.count('{13}'):
                e.append('쪽 수 %d → %d' % (jp.count('{13}'), ko.count('{13}')))
            bad, cur = color_state(ko)
            e += bad
            if cur and not color_state(jp)[1]:
                e.append('색 %s 안 닫힘' % cur)
            if ko.endswith('\\n') != jp.endswith('\\n'):
                e.append('끝 줄바꿈 다름')
            jp_pages, ko_pages = pages(jp), pages(squeeze(ko))
            max_lines = max(len(pg) for pg in jp_pages)
            bud = budget_of(inner, jp)
            if bud is None:
                if any(k in inner for k in PER_STRING):   # 버튼({15}CT/RT)은 원문 폭, 로그·도움말은 창이 넓다(최소 18)
                    bud = max(width(ln) for pg in jp_pages for ln in pg)
                    bud = max(bud, 5 if '{15}' in jp else 18)   # 버튼은 같은 메뉴끼리 크기 공유(가장 긴 원문 せつめい·セーブする 4‥5)
                else:
                    bud = table_max[inner]
            for pg in ko_pages:
                if len(pg) > max_lines:
                    e.append('쪽 줄 수 %d > %d' % (len(pg), max_lines))
                for ln in pg:
                    if width(ln) > bud:
                        e.append('줄 폭 %.1f > %.1f 「%s」' % (width(ln), bud, ln.strip()))
            kk = KANA_KANJI.findall(TAG.sub('', ko))
            if kk:
                e.append('가나·한자 남음 %s' % ''.join(kk))
            for m in re.finditer(r'\{([^}]*)\}', ko):
                if any(hangul(c) for c in m.group(1)) and m.group(0) not in JOSA:
                    e.append('모르는 조사 %s' % m.group(0))
            body = ko
            for k, v in JOSA.items():
                body = body.replace(k, v)
            for c in body:
                if hangul(c):
                    if c not in KS:
                        e.append('KS X 1001 밖 %s' % c)
                    syl[c] += 1
                    where.setdefault(c, (loc, ko))
            for x in e:
                errs.append('%s [%s #%s] %s' % (loc, inner.split('/')[-1], i, x))
    for x in errs:
        print('✗', x)
    n = len(syl)
    print('번역 %d줄 · 오류 %d · 음절 %d (한자 칸 %d%s / 가나 포함 %d%s)' % (
        len(done), len(errs), n, FONT_SLOTS, ' 넘음' if n > FONT_SLOTS else '', FONT_SLOTS_KANA,
        ' 넘음' if n > FONT_SLOTS_KANA else ''))
    if '--todo' in sys.argv:
        todo = Counter()
        tot = Counter()
        for key, t in src.items():
            if KANA_KANJI.search(t):
                tot[key[1]] += 1
                if key not in done:
                    todo[key[1]] += 1
        for k in tot:
            print('  %-50s 남음 %4d / %4d' % (k, todo[k], tot[k]))
    if rare is not None:
        for c, k in sorted(syl.items(), key=lambda x: (x[1], x[0])):
            if k > rare:
                break
            loc, ko = where[c]
            print('  %s %d  %s  %s' % (c, k, loc, ko[:60]))
    sys.exit(1 if errs else 0)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
