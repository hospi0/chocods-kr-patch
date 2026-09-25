# -*- coding: utf-8 -*-
r"""카드 게임 글 중 «정형 문구»를 카드 번역표(work/card_ko.tsv)로 자동 번역 → work/ko_pud/30_auto.tsv

  python tools/pudauto.py

  · mgentryphase/text/ja/secret/*.ptx — 「エピローグN出現」「牧場のおともだち「이름」出現」「「번호 소환수 기술」出現」…
  · deck/ja/deck_card_data.dcd — 몬스터 이름 33 + 카드 기술 이름 143
  · deck/ja/cardgroup.bin — 「マンドラ族」
표에 없는 말은 끝에 목록으로 찍는다(그 줄은 쓰지 않음).
"""
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'pud_src.tsv')
OUT = os.path.join(ROOT, 'work', 'ko_pud', '30_auto.tsv')

# 목장 친구 이름(본편에 안 나옴 — 새 음역, 거센소리 규칙)
FRIENDS = {'アイアイ': '아이아이', 'イエロウ': '옐로우', 'グリン': '그린', 'ザヴィ': '자비', 'ジャロ': '자로',
           'ジョー': '조', 'スイニー': '스위니', 'ドーリー': '돌리', 'ブラウ': '브라우', 'ブルース': '브루스',
           'ベッキー': '베키', 'ベルデ': '베르데', 'モギー': '모기', 'モモ': '모모', 'ワカバ': '와카바'}
MENU = {'ひとりでトライアル': '혼자서 트라이얼', 'バトル': '배틀'}      # 카드 게임 그림 번역(work/pud_specs.json)과 같은 표기
EXTRA = {'マンドラ族': '만드라족'}
SKILL_ALIAS = {'マイティーガード': 'マイティガード'}               # secret 표기 ↔ 카드 표 표기
BS = chr(92) + 'n'
N = r'([０-９0-9]+)'
# 해금 조건(색 없는 줄, 끝 {00}) — 숫자는 원문 그대로
COND = [
    (r'トライアルで' + N + r'pt以上かくとくする', r'트라이얼에서 \1pt 이상 획득'),
    (r'トライアルで' + N + r'ｍ以上およぐ', r'트라이얼에서 \1ｍ 이상 헤엄치기'),
    (r'トライアルで' + N + r'分' + N + r'秒以内にゴールする', r'트라이얼에서 \1분 \2초 안에 골인'),
    (r'トライアルで' + N + r'秒以内にゴールする', r'트라이얼에서 \1초 안에 골인'),
    (r'トライアルで' + N + r'分以内にゴールする', r'트라이얼에서 \1분 안에 골인'),
    (r'トライアルで' + N + r'mまでのぼる', r'트라이얼에서 \1m까지 오르기'),
    (r'トライアルで一度もカベにぶつからず' + re.escape(BS) + r'ゴールする', '트라이얼에서 벽에 한 번도' + BS.replace('\\', '\\\\') + '부딪히지 않고 골인'),
    (r'トライアルで落石のダメージを' + re.escape(BS) + r'一度も受けずにゴールする', '트라이얼에서 낙석 대미지를' + BS.replace('\\', '\\\\') + '한 번도 받지 않고 골인'),
    (r'バトルでレベル' + N + r'に' + N + r'pt以上かくとくして' + re.escape(BS) + r'勝利する',
     r'배틀에서 레벨\1에게 \2pt 이상' + BS.replace('\\', '\\\\') + r'획득하고 승리'),
    (r'バトルでレベル' + N + r'にノーミスで勝利する', r'배틀에서 레벨\1에게 노미스로 승리'),
    (r'バトルでレベル' + N + r'に勝利する', r'배틀에서 레벨\1에게 승리'),
    (r'バトルで' + N + r'pt以上かくとくする', r'배틀에서 \1pt 이상 획득'),
]


def pools():
    name, skill = {}, {}
    for ln in open(os.path.join(ROOT, 'work', 'card_ko.tsv'), encoding='utf-8'):
        q = ln.rstrip('\n').split('\t')
        if len(q) != 3:
            continue
        key = unicodedata.normalize('NFKC', q[1])
        if q[0] == 'name':
            name[key] = q[2]
        elif q[0] == 'skill':
            skill[key] = q[2]
    return name, skill


MG = {}                                           # 그림책 설명 고유 쪽: 원문 → 번역(work/mg_unique_ko.tsv)
for _ln in open(os.path.join(ROOT, 'work', 'mg_unique_ko.tsv'), encoding='utf-8'):
    if not _ln.startswith('#') and '\t' in _ln:
        _a, _b = _ln.rstrip('\n').split('\t')
        MG[_a] = _b


def main():
    name, skill = pools()
    rows = [ln.rstrip('\n').split('\t') for ln in open(SRC, encoding='utf-8') if not ln.startswith('#')]
    out, miss = [], set()

    def nm(s):
        k = unicodedata.normalize('NFKC', s)
        return name.get(k) or EXTRA.get(k)

    def sk(s):
        s = SKILL_ALIAS.get(s, s)
        return skill.get(unicodedata.normalize('NFKC', s))

    def card(num, a, b):
        x, y = nm(a), sk(b)
        if x is None or y is None:
            miss.add('카드 %s / %s' % (a, b))
            return None
        return '「%s %s %s」' % (unicodedata.normalize('NFKC', num), x, y)   # 번호는 반각(전각 10px → 폭 절약)

    import pudcheck
    width = pudcheck.Width()
    LIMIT = 182                                   # secret 상자 = 원문 secret 최대 줄 폭(pudcheck)

    def fit(ko):
        """넘치면 「등장」 앞 공백 → 번호 뒤 공백 순으로 뺀다"""
        if width(ko) > LIMIT:
            ko = ko.replace('」 등장', '」등장')
        if width(ko) > LIMIT:
            ko = re.sub(r'「([０-９0-9]{3}) ', r'「\1', ko)
        return ko

    for p, kind, i, t in rows:
        if '/ja/secret/' in p:
            if t == '{00}':
                continue
            m = re.fullmatch(r'(\{1B\}C)?\{1B\}G(.*?)\{1B\}\{1B\}\{00\}', t)
            if not m:
                body = t[:-4] if t.endswith('{00}') else None
                for pat, rep in COND:
                    if body is not None and re.fullmatch(pat, body):
                        out.append((p, i, re.sub(pat, rep, body) + '{00}'))
                        break
                else:
                    miss.add('형식 ' + t)
                continue
            head, body = m.group(1) or '', m.group(2)
            ko = None
            e = re.fullmatch(r'エピローグ([１２３])出現', body)
            f = re.fullmatch(r'牧場のおともだち「(.+?)」(出現)?', body)
            c = re.fullmatch(r'「([０-９0-9]{3})\s+(.+?)\s+(.+?)」出現', body)
            g = re.fullmatch(r'「(.+?)」出現', body)
            ce = re.fullmatch(r'「([０-９0-9]{3})\s+(.+?)\s+(.+?)」・エピローグ([１２３])出現', body)
            if ce:
                cc = card(ce.group(1), ce.group(2), ce.group(3))
                if cc is None:
                    continue
                ko = '%s·에필로그%s 등장' % (cc, ce.group(4))
            elif e:
                ko = '에필로그%s 등장' % e.group(1)
            elif f:
                n = FRIENDS.get(f.group(1))
                if n is None:
                    miss.add('친구 ' + f.group(1))
                    continue
                ko = '목장 친구 「%s」%s' % (n, ' 등장' if f.group(2) else '')
            elif c:
                a, b = nm(c.group(2)), sk(c.group(3))
                if a is None or b is None:
                    miss.add('카드 %s / %s' % (c.group(2), c.group(3)))
                    continue
                ko = '「%s %s %s」 등장' % (c.group(1), a, b)
            elif g and g.group(1) in MENU:
                ko = '「%s」 등장' % MENU[g.group(1)]
            else:
                miss.add('문구 ' + body)
                continue
            out.append((p, i, '%s{1B}G%s{1B}{1B}{00}' % (head, ko)))
        elif p.endswith('deck_card_data.dcd'):
            if not t:
                continue
            k = int(i)
            v = nm(t) if k < 33 else sk(t)
            if v is None:
                miss.add(('이름 ' if k < 33 else '기술 ') + t)
                continue
            out.append((p, i, v))
        elif p.endswith('cardgroup.bin'):
            out.append((p, i, EXTRA[t]))
        elif '/ja/expl/' in p or '/ja/trial/' in p:
            if t in MG:
                out.append((p, i, MG[t]))
            elif re.search(r'[ぁ-ヿ一-鿿]', t):
                miss.add('그림책 설명 ' + t[:30])
    with open(OUT, 'w', encoding='utf-8', newline='\n') as fo:
        fo.write('# 자동 생성(tools/pudauto.py) — 손으로 고치지 말고 표(card_ko.tsv·FRIENDS·MENU)를 고칠 것\n')
        for p, i, k in out:
            fo.write('%s\t%s\t%s\n' % (p, i, k))
    print('자동 %d줄 → %s' % (len(out), OUT))
    for m in sorted(miss):
        print('  못 찾음', m)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
