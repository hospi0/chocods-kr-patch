# pud_specs.json 전체: 셀 바깥 테두리(투명에 닿는 화소) 색이 바뀐 화소 수를 센다 — 판 테두리 지워짐 검사
import sys,json; sys.path.insert(0,'tools')
import ndspy.rom, ndspy.lz10, lz11, ncer, pudlabel
from collections import Counter
rom=ndspy.rom.NintendoDSRom.fromFile(r'C:\claude\roms\nds\Cid to Chocobo no Fushigi na Dungeon - Toki Wasure no Meikyuu DS+ (Japan).nds')
F={l.split('\t')[1]:int(l.split('\t')[0]) for l in open('work/files.tsv',encoding='utf-8')}
S=json.load(open('work/pud_specs.json',encoding='utf-8'))
for path,spec in S.items():
    if path.startswith('relayout:'): continue
    raw=bytes(rom.files[F[path]]); d=bytes(lz11.decompress(raw) if raw[0]==0x11 else ndspy.lz10.decompress(raw))
    B=pudlabel.blocks(d); pal=ncer.nclr(B['RLCN'][1]); sp=pudlabel.Sprites(B['RECN'][1],B['RGCN'][1]); sp0=pudlabel.Sprites(B['RECN'][1],B['RGCN'][1])
    for c,t in spec.items():
        t=(t+[None]*7)[:8] if isinstance(t,list) else [t]+[None]*7
        if not t[0]: continue
        if isinstance(t[4],str) and t[4].startswith('grad:'): t[4]=pudlabel.ramp(sp0,int(t[4][5:]),pal)
        if t[3]=='ttf': pudlabel.ttf_cell(sp,int(c.split('#')[0]),t[0],pal,order=t[4] or 'lumr'); continue
      if t[3]=='glyph': pudlabel.glyph_cell(sp,int(c.split('#')[0]),t[0],pal,font=t[2] or 'Galmuri7',fill=t[4]); continue
    if t[3]=='rewrap': pudlabel.rewrap(sp,int(c.split('#')[0]),t[0],font=t[2] or 'Galmuri9',fill=t[4] or 'grad',pal=pal); continue
        pudlabel.relabel(sp,int(c.split('#')[0]),t[0],rect=tuple(t[1]) if t[1] else None,font=t[2],erase_to=t[3],fill=t[4],align=t[5] or 'center',ring=bool(t[6]),edge_c=t[7],pal=pal)
    for c in sorted({int(k.split('#')[0]) for k,v in spec.items() if v}):
        a,_,_,_=sp0.canvas(c); b,_,_,_=sp.canvas(c); H,W=len(a),len(a[0])
        outer=[(x,y) for y in range(H) for x in range(W) if a[y][x] and any(not(0<=x+dx<W and 0<=y+dy<H) or a[y+dy][x+dx]==0 for dx,dy in((1,0),(-1,0),(0,1),(0,-1)))]
        bc=Counter(a[y][x] for x,y in outer).most_common(1)[0][0]
        border=[(x,y) for x,y in outer if a[y][x]==bc]
        lost=sum(1 for x,y in border if b[y][x]!=bc)
        if lost and len(border)>40 and lost/len(border)>0.03: print(path.split('/')[-1],c,'테두리 %d/%d 화소 바뀜'%(lost,len(border)))
print('검사 끝')
