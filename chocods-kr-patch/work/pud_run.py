# 사용: python work/pud_run.py <이름> <경로>  — work/pud_specs.json 의 설정으로 미리보기
import sys,json,subprocess
S=json.load(open('work/pud_specs.json',encoding='utf-8'))
path,_,narc=sys.argv[2].partition('@')   # 'NARC경로@번호' = NARC 안 파일
subprocess.run([sys.executable,'work/pud_preview.py',path,sys.argv[1],json.dumps(S[sys.argv[2]],ensure_ascii=False)]+([narc] if narc else []),check=True)
