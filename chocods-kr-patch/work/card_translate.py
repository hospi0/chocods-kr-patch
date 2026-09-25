# 카드 문구 번역 적용 → work/card_ko.tsv (pool, jp, ko) + 줄 폭 검사
import sys,re; sys.path.insert(0,'tools'); sys.path.insert(0,'work')
import cardbin, cardfit
from card_lines_ko import LINES
from card_words_ko import NAMES, SKILLS, DESC_EXTRA
PFX=re.compile(r'^(┌┐|└┘|┏┓|┗┛|├┬|┴┤|　　|　)')
def jong(w): c=ord(w[-1]); return 0xAC00<=c<=0xD7A3 and (c-0xAC00)%28!=0
def skill(s):
    kai = s.endswith('･改') or s.endswith('・改')
    b = s[:-2] if kai else s
    return SKILLS[b] + ('·개' if kai else '')
def abil_line(l):
    e=cardbin.esc(l); m=PFX.match(e); pre=m.group(1) if m else ''; body=e[len(pre):]
    nums=re.findall(r'[０-９]+',body); body=re.sub(r'[０-９]+','#',body)
    icons=re.findall(r'(?:\{C1B\}\{C0.\})+',body); body=re.sub(r'(?:\{C1B\}\{C0.\})+','◆',body)
    key=body.replace('{C1C}{C04}','«').replace('{C1C}{C01}','»')
    alts=LINES[key]; alts=alts if isinstance(alts,list) else [alts]
    for ko in alts:
        for n in nums: ko=ko.replace('#',n,1)
        for ic in icons: ko=ko.replace('◆',ic,1)
        ko=cardbin.unesc(pre+ko.replace('«','{C1C}{C04}').replace('»','{C1C}{C01}'))
        if cardfit.line_w(ko)<=max(108,cardfit.line_w(l)): break
    return ko
LIM={'name':70,'skill':90,'desc':95,'abil':108}
rows=[l.rstrip('\n').split('\t') for l in open('work/card_src.tsv',encoding='utf-8')][1:]
out=[]; bad=0
for pool,jp in rows:
    s=cardbin.unesc(jp)
    if pool=='name': ko=NAMES[s]
    elif pool=='skill': ko=skill(s)
    elif pool=='desc':
        if s in DESC_EXTRA: ko=DESC_EXTRA[s]
        elif s.endswith('は\nようすをみている。'):
            n=NAMES[s[:-len('は\nようすをみている。')]]; ko=n+('은' if jong(n) else '는')+'\n상황을 살피고 있다.'
        elif '\n' in s and s.split('\n')[0].endswith('の'):
            a,b=s.split('\n'); ko=NAMES[a[:-1]]+'의\n'+skill(b)
        else: ko=skill(s)
    else:
        ko='\n'.join(abil_line(l) for l in s.split('\n'))
    ko=re.sub(r'([,.!?:;]) +',r'\1',ko)                      # 부호 뒤 공백 삭제(전프로젝트 규칙)
    jl=s.split(chr(10))
    for k,l in enumerate(ko.split(chr(10))):                 # 원문 같은 줄과 1:1 비교(아이콘 폭은 양쪽 같음)
        w=cardfit.line_w(l); ow=cardfit.line_w(jl[k]) if k<len(jl) else 0
        if w>max(LIM[pool],ow): bad+=1; print('넘침',pool,w,'원문',ow,cardbin.esc(l))
    out.append((pool,jp,cardbin.esc(ko)))
with open('work/card_ko.tsv','w',encoding='utf-8') as f:
    f.write('pool\tjp\tko\n')
    for r in out: f.write('\t'.join(r)+'\n')
print('rows',len(out),'overflow',bad)
