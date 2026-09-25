# -*- coding: utf-8 -*-
r"""카드 게임(romdata/PUD) 남은 글 추출 — 로컬(원본 ROM 필요)에서 한 번 돌려 work/pudtext_src.tsv 를 만든다.

  python tools/puddump.py [출력.tsv]

대상(docs §18): 언어 폴더 ja·jc(또는 파일 이름 _ja_)의 그림 아닌 파일 — pubtutorial/ja/tutorialtext.bin,
mgentryphase/text/ja(jc)/*.ptx, deck/ja/*.txt, wifi/ja/wifitext.bin, pub 오류·대전·칭호 문구, multiplay/text, skb/ja, errorproc.
형식을 다 모르므로 두 갈래로 뽑는다(되쓰기는 형식 확인 뒤 pudbuild 에):
  utf16  UTF-16LE 파일(BOM 또는 짝수 바이트 0 비율로 판정) — 파일 전체를 한 줄로(\n·\r 은 이스케이프), 번호 0
  utf8   그 밖 — NUL 로 끝나는 UTF-8 문자열 중 가나·한자가 든 것, 번호 = 바이트 오프셋(10진)
TSV: 경로<TAB>방식<TAB>번호<TAB>원문   (# 줄 = 파일 머리 64 B 16진, 형식 조사용)
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GFX = ('.NCGR', '.NCLR', '.NSCR', '.NCER', '.NANR', '.PBG', '.POBJ', '.NARC', '.nftr', '.sdat', '.mods')
JP = re.compile(r'[\u3041-\u30FF\u3400-\u9FFF\uFF66-\uFF9F]')


def is_lang(path):
    parts = path.split('/')
    return 'ja' in parts or 'jc' in parts or '_ja_' in parts[-1] or '_ja.' in parts[-1]


def esc(s):
    return s.replace('\\', '\\\\').replace('\t', '\\t').replace('\r', '\\r').replace('\n', '\\n')


def utf16ish(d):
    if d[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return True
    odd = d[1::2][:400]
    return len(odd) > 8 and odd.count(0) + sum(0x30 <= b <= 0x9f for b in odd) > 0.9 * len(odd) and JP.search(
        d.decode('utf-16-le', 'ignore'))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'work', 'pudtext_src.tsv')
    assert build.md5(build.ORIG) == build.ORIG_MD5, '원본 md5 불일치'
    rom = build.ndspy.rom.NintendoDSRom.fromFile(build.ORIG)
    ids = {}

    def walk(folder, pre=''):
        for i, name in enumerate(folder.files):
            ids[pre + name] = folder.firstID + i
        for name, sub in folder.folders:
            walk(sub, pre + name + '/')
    walk(rom.filenames)
    rows, heads, n16, n8 = [], [], 0, 0
    for path in sorted(p for p in ids if p.startswith('romdata/PUD/') and is_lang(p)):
        base = path[:-2] if path.endswith('.z') else path
        if base.endswith(GFX) or '/card/' in path:            # 그림·카드 표(card.bin 은 이미 번역)는 뺀다
            continue
        d = bytes(rom.files[ids[path]])
        if path.endswith('.z'):
            d, _ = build.unz(d)
        if utf16ish(d):
            t = d.decode('utf-16-le' if d[:2] != b'\xfe\xff' else 'utf-16-be', 'replace').lstrip('\ufeff')
            if JP.search(t):
                rows.append((path, 'utf16', 0, t))
                n16 += 1
            continue
        found = False
        for m in re.finditer(rb'[^\x00]{2,}?(?=\x00)', d):
            try:
                t = m.group().decode('utf-8')
            except UnicodeDecodeError:
                continue
            if JP.search(t):
                rows.append((path, 'utf8', m.start(), t))
                found = True
        if found:
            heads.append('# %s  %d B  %s' % (path, len(d), d[:64].hex()))
            n8 += 1
    with open(out, 'w', encoding='utf-8') as fo:
        fo.write('# 카드 게임 남은 글 원문 — tools/puddump.py 가 만듦(경로·방식·번호·원문)\n')
        for h in heads:
            fo.write(h + '\n')
        for path, mode, key, t in rows:
            fo.write('%s\t%s\t%d\t%s\n' % (path, mode, key, esc(t)))
    print('%s: UTF-16 파일 %d · UTF-8 파일 %d · 줄 %d' % (out, n16, n8, len(rows)))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
