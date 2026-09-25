# 사용: python work/pud_relayout_preview.py <경로> <이름>  — pud_specs.json 의 "relayout:<경로>" 설정으로 재배치 후 비교 그림
import sys,json; sys.path.insert(0,'tools')
import ndspy.rom, ndspy.lz10, lz11, ncer, pudlabel
from PIL import Image, ImageDraw
rom=ndspy.rom.NintendoDSRom.fromFile(r'C:\claude\roms\nds\Cid to Chocobo no Fushigi na Dungeon - Toki Wasure no Meikyuu DS+ (Japan).nds')
F={l.split('\t')[1]:int(l.split('\t')[0]) for l in open('work/files.tsv',encoding='utf-8')}
path,name=sys.argv[1],sys.argv[2]
spec={int(k):v for k,v in json.load(open('work/pud_specs.json',encoding='utf-8'))['relayout:'+path].items()}
raw=bytes(rom.files[F[path]]); d=bytes(lz11.decompress(raw) if raw[0]==0x11 else ndspy.lz10.decompress(raw))
B=pudlabel.blocks(d); pal=ncer.nclr(B['RLCN'][1])
nb,gb=pudlabel.relayout(B['RECN'][1],B['RGCN'][1],spec,pal)
s0=pudlabel.Sprites(B['RECN'][1],B['RGCN'][1]); s1=pudlabel.Sprites(nb,gb)
for c in range(len(s0.cells)):                       # 대상 아닌 셀은 화소가 그대로여야 한다
    if c not in spec and s0.cells[c]: assert s0.canvas(c)[0]==s1.canvas(c)[0], '셀 %d 이 바뀜(번짐)'%c
def img(s,c):
    can,cov,x0,y0=s.canvas(c); im=Image.new('RGB',(len(can[0]),len(can)),(40,40,60))
    for y,r in enumerate(can):
        for x,v in enumerate(r):
            if v:
                ob=[o for o in s.cells[c] if o['x']-x0<=x<o['x']-x0+o['w'] and o['y']-y0<=y<o['y']-y0+o['h']][0]
                k=v if s.bpp==8 else ob['pal']*16+v; im.putpixel((x,y),pal[k])
    return im
rows=[(c,img(s0,c),img(s1,c)) for c in sorted(spec)]
S=2; W=max(max(a.width,b.width) for _,a,b in rows)*S*2+30; H=sum(max(a.height,b.height,12)*S+6 for _,a,b in rows)
o=Image.new('RGB',(W,H)); dr=ImageDraw.Draw(o); y=0
for c,a,b in rows:
    o.paste(a.resize((a.width*S,a.height*S),Image.NEAREST),(0,y)); o.paste(b.resize((b.width*S,b.height*S),Image.NEAREST),(W//2,y)); dr.text((W//2-24,y),str(c),fill=(255,255,0)); y+=max(a.height,b.height,12)*S+6
o.save('work/gfx/pud_%s.png'%name); print(o.size,'other cells unchanged')
