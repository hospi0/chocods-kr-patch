# -*- coding: utf-8 -*-
r"""배포 묶음 — dist/ChocoboDS_KR_v0.9/ (xdelta + xdelta.exe + readme.txt + 패치적용.bat)

  python tools/make_dist.py [패치본.nds]     # 기본 = work/ 의 가장 최근 chocods_ko_t*.nds

규칙: 해시는 MD5 대문자 · readme 머리말 형식 고정 · 한국어 문서는 CP949(CRLF) · 버전은 v0.9 꼴.
readme 에 합언어(비밀번호) 한국어 정답 58개 목록을 넣는다(배포용 35개는 게임 안에서 알 수 없다).
"""
import glob, hashlib, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build

VER = 'v0.9'
NAME = 'Cid to Chocobo no Fushigi na Dungeon - Toki Wasure no Meikyuu DS+ (Japan).nds'
PKG = 'ChocoboDS_KR_' + VER
DIST = os.path.join(ROOT, 'dist', PKG)
PATCH = PKG + '.xdelta'
XDELTA = r'C:\claude\project\chocobo-kr-patch\dist\Chocobo_KR_v0.9\xdelta.exe'


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


README = """시드와 초코보의 이상한 던전 ~시간을 잊는 미궁~ DS+ (NDS 일본판) 한글 패치 {ver}
==========================================

1개의 롬 파일 {name} 에
패치하시면 됩니다.

원본md5 : {src}
패치md5 : {dst}

입니다.


[ 적용 방법 ]

1. 원본 .nds 파일과 이 패치 묶음을 한 폴더에 둡니다.
2. 「패치적용.bat」 을 실행합니다.
3. 배치가 원본 MD5 를 먼저 확인하고, 끝난 뒤 결과 MD5 까지 검사합니다.
   원본은 .bak 으로 남겨 둡니다.


[ 바뀌는 것 ]

■ 본편 대사·메뉴·아이템·몬스터·어빌리티·편지·시스템 문구 전부
■ 그림 글자(타이틀·HUD·메뉴·장 제목·직업명·던전 이름·지명·출구 표시 등)
■ 영상 자막 2편(데모 A·B)
■ 조사(을/를·이/가…) 자동 선택
■ 카드 게임 「팝업 듀얼」: 카드 이름·설명, 튜토리얼, 그림책 게임 설명, 대전·결과·Wi-Fi·덱 편집 화면
■ 합언어(비밀번호) 입력: 한글 자판 + 한국어 정답 (아래 목록)
■ 이름·덱 이름 입력 자판 한글


[ 합언어(비밀번호) 한국어 정답 ]

편지의 분홍 글자를 이어 읽으면 정답이 됩니다. 배포용 비밀번호도 한국어로 바꿨습니다.
(일본어판 비밀번호 목록은 이 패치에서 쓸 수 없습니다)

{passwords}


[ 알려진 사항 ]

■ 이름 입력 자판은 칸 수 때문에 쓸 수 있는 음절이 정해져 있습니다.
■ 오프닝 영상의 제목 로고와 제작진 명단은 원문 그대로입니다.
■ 예전 판의 세이브스테이트를 불러오면 글자가 어긋나 보일 수 있습니다.
"""

BAT = r"""@echo off
setlocal
set NAME={name}
set PATCH={patch}
set SRCMD5={src}
set DSTMD5={dst}

echo.
echo  ==============================================
echo    Cid to Chocobo no Fushigi na Dungeon DS+ ^(NDS JP^) Korean Patch {ver}
echo  ==============================================
echo.

if not exist "%NAME%" (
  echo  [!] "%NAME%" 파일이 이 폴더에 없습니다.
  echo      원본 .nds 와 같은 폴더에 두고 실행하세요.
  goto END
)
if not exist "%~dp0xdelta.exe" (
  echo  [!] xdelta.exe 가 없습니다. 패치 묶음을 그대로 풀고 실행하세요.
  goto END
)

echo  [1/3] 원본 검사 중...
set HASH=
for /f "skip=1 tokens=* delims=" %%H in ('certutil -hashfile "%NAME%" MD5') do (
  if not defined HASH set HASH=%%H
)
set HASH=%HASH: =%

if /I "%HASH%"=="%DSTMD5%" (
  echo.
  echo  [!] 이미 이 버전의 한글 패치가 적용된 파일입니다.
  goto END
)
if /I not "%HASH%"=="%SRCMD5%" (
  echo.
  echo  [!] 원본 MD5 가 다릅니다. 패치하지 않고 중단합니다.
  echo      필요 : %SRCMD5%
  echo      현재 : %HASH%
  goto END
)

echo  [2/3] 패치 적용 중...
"%~dp0xdelta.exe" -d -f -s "%NAME%" "%~dp0%PATCH%" "%NAME%.kr"
if errorlevel 1 (
  echo  [!] 패치에 실패했습니다.
  if exist "%NAME%.kr" del "%NAME%.kr"
  goto END
)

echo  [3/3] 결과 검사 중...
set HASH2=
for /f "skip=1 tokens=* delims=" %%H in ('certutil -hashfile "%NAME%.kr" MD5') do (
  if not defined HASH2 set HASH2=%%H
)
set HASH2=%HASH2: =%

if /I not "%HASH2%"=="%DSTMD5%" (
  echo  [!] 결과 MD5 가 다릅니다. 원본은 그대로 두고 중단합니다.
  del "%NAME%.kr"
  goto END
)

move /y "%NAME%" "%NAME%.bak" >nul
move /y "%NAME%.kr" "%NAME%" >nul
echo.
echo  [OK] 한글 패치 완료. 원본은 "%NAME%.bak" 으로 남겨 두었습니다.

:END
echo.
pause
endlocal
"""


def write_cp949(path, text):
    data = text.replace('\r\n', '\n').replace('\n', '\r\n').encode('cp949')   # 인코딩 먼저(실패해도 파일을 안 비운다)
    with open(path, 'wb') as f:
        f.write(data)


def passwords():
    rows = [(ln.rstrip('\n').split('\t') + ['', ''])[:4] for ln in open(os.path.join(ROOT, 'work', 'password_plan.tsv'), encoding='utf-8')
            if not ln.startswith('#') and ln.strip()]
    letter = [r for r in rows if r[3]]
    dist = [r for r in rows if not r[3]]
    out = ['● 편지로 알 수 있는 것 (%d)' % len(letter)]
    out += ['  %2s. %s' % (r[0], r[2]) for r in letter]
    out += ['', '● 배포용 (%d)' % len(dist)]
    out += ['  %2s. %s' % (r[0], r[2]) for r in dist]
    return '\n'.join(out)


def main():
    src = build.ORIG
    if len(sys.argv) > 1:
        out = sys.argv[1]
    else:
        cands = glob.glob(os.path.join(ROOT, 'work', 'chocods_ko_t*.nds'))
        out = max(cands, key=lambda p: int(re.search(r'_t(\d+)\.nds$', p).group(1)))
    src_md5, dst_md5 = md5(src), md5(out)
    assert src_md5 == build.ORIG_MD5, src_md5
    os.makedirs(DIST, exist_ok=True)
    patch = os.path.join(DIST, PATCH)
    subprocess.run([XDELTA, '-e', '-9', '-f', '-s', src, out, patch], check=True)
    shutil.copyfile(XDELTA, os.path.join(DIST, 'xdelta.exe'))
    chk = os.path.join(ROOT, 'work', 'dist_check.nds')          # 되짚기: 원본에 패치를 적용해 패치본과 같은지
    subprocess.run([XDELTA, '-d', '-f', '-s', src, patch, chk], check=True)
    ok = md5(chk) == dst_md5
    os.remove(chk)
    if not ok:
        raise SystemExit('⛔ xdelta 되짚기 결과가 패치본과 다르다')
    v = dict(ver=VER, name=NAME, patch=PATCH, src=src_md5, dst=dst_md5)
    write_cp949(os.path.join(DIST, 'readme.txt'),
                README.format(**dict(v, src=src_md5.upper(), dst=dst_md5.upper(), passwords=passwords())))
    write_cp949(os.path.join(DIST, '패치적용.bat'), BAT.format(**v))
    print('✅ %s\n   패치본 %s\n   xdelta %d B · 원본md5 %s · 패치md5 %s · 되짚기 일치'
          % (DIST, os.path.basename(out), os.path.getsize(patch), src_md5.upper(), dst_md5.upper()))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
