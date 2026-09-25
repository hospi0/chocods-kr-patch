# 사용: python work/pud_bleed.py <경로> <빼 볼 키> <확인할 셀들...> — 그 키를 빼고 돌렸을 때 다른 셀 화소가 같은지(공유 타일 번짐 검사)
import json,subprocess,sys
k,drop,cells=sys.argv[1],sys.argv[2],sys.argv[3:]
S=json.load(open('work/pud_specs.json',encoding='utf-8')); bak=json.dumps(S,ensure_ascii=False,indent=1)
full={c:subprocess.run([sys.executable,'work/pud_cell.py',k,c],capture_output=True,text=True).stdout for c in cells}
del S[k][drop]; open('work/pud_specs.json','w',encoding='utf-8').write(json.dumps(S,ensure_ascii=False,indent=1))
try:
    part={c:subprocess.run([sys.executable,'work/pud_cell.py',k,c],capture_output=True,text=True).stdout for c in cells}
finally:
    open('work/pud_specs.json','w',encoding='utf-8').write(bak)
for c in cells: print(' 셀',c,'영향 없음' if full[c]==part[c] and full[c] else '⚠️ 달라짐')
