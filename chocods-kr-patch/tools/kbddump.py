# -*- coding: utf-8 -*-
r"""합언어 자판(UI/KBD) 조사 — 로컬(원본 ROM 필요)에서 돌려 자판이 어떤 글자를 내는지, 탁음(゛゜)을 조합하는지 본다.

  python tools/kbddump.py [출력.txt]      (기본 work/kbd_dump.txt)

대상: UI/KBD/kbd·kbdmap·kbdres, UI/RMTCWORD/kbd_nyuryoku, UI/DT/DT_UIRMTCWORDW (FBC 안쪽 파일 전부).
안쪽 파일마다: 이름·크기·머리 16진, 그리고 UTF-16LE·UTF-8·Shift-JIS 로 읽었을 때 가나가 보이면 그 글자열.
탁음 키가 따로 있으면 ゛(U+309B)·゜(U+309C)·濁 이 보이고, 없으면 が·ぱ 같은 완성 글자가 표에 직접 들어 있다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build
import fbc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = ('romdata/UI/KBD/', 'romdata/UI/RMTCWORD/', 'romdata/UI/DT/DT_UIRMTCWORDW')
KANA = re.compile(r'[ぁ-ヿ゛゜ｦ-ﾟ]')


def kana_runs(d):
    """세 인코딩으로 읽어 가나가 3자 이상 든 조각"""
    out = []
    for enc, step in (('utf-16-le', 2), ('utf-8', 1), ('cp932', 1)):
        for off in range(step if enc == 'utf-16-le' else 1):
            s = d[off:].decode(enc, 'replace')
            runs = [m.group(0) for m in re.finditer(r'[ぁ-ヿ゛゜ｦ-ﾟ　-〿！-～]{3,}', s)]
            if sum(len(r) for r in runs) >= 6:
                out.append('%s+%d: %s' % (enc, off, ' | '.join(runs)))
    return out


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'work', 'kbd_dump.txt')
    assert build.md5(build.ORIG) == build.ORIG_MD5, '원본 md5 불일치'
    rom = build.ndspy.rom.NintendoDSRom.fromFile(build.ORIG)
    ids = {}

    def walk(folder, pre=''):
        for i, name in enumerate(folder.files):
            ids[pre + name] = folder.firstID + i
        for name, sub in folder.folders:
            walk(sub, pre + name + '/')
    walk(rom.filenames)
    lines = []
    for path in sorted(p for p in ids if p.startswith(TARGETS)):
        d = bytes(rom.files[ids[path]])
        if path.endswith('.z'):
            d = build.unz(d)[0]
        lines.append('=== %s (%d B)' % (path, len(d)))
        items = list(fbc.walk(d)) if d[:2] == b'\x14\x00' else [('(raw)', d)]
        for name, b in items:
            lines.append('--- %s (%d B) 머리 %s' % (name, len(b), b[:32].hex(' ')))
            for r in kana_runs(b):
                lines.append('    ' + r)
                if '゛' in r or '゜' in r:
                    lines.append('    ★ 탁음·반탁음 부호(゛゜) 있음')
            if name.endswith(('map', '.bin', 'csvbin')) or 'map' in name:
                for i in range(0, min(len(b), 512), 32):
                    lines.append('    %04x  %s' % (i, b[i:i + 32].hex(' ')))
    open(out, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print(out, len(lines), '줄')


if __name__ == '__main__':
    main()
