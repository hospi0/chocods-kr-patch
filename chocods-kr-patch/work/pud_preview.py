# 사용: python work/pud_preview.py <롬 경로> <이름> '{셀: 글자}' [narc 번호]
import sys,struct,json; sys.path.insert(0,'tools')
import ndspy.rom, ndspy.narc, lz11, ndspy.lz10, ncer, pudlabel
from PIL import Image, ImageDraw
rom=ndspy.rom.NintendoDSRom.fromFile(r'C:\claude\roms\nds\Cid to Chocobo no Fushigi na Dungeon - Toki Wasure no Meikyuu DS+ (Japan).nds')
F={l.split('\t')[1]:int(l.split('\t')[0]) for l in open('work/files.tsv',encoding='utf-8')}
path,name,spec=sys.argv[1],sys.argv[2],json.loads(sys.argv[3])
spec={k:((v+[None]*7)[:8] if isinstance(v,list) else [v,None,None,None,None,None,None,None]) for k,v in spec.items()}
narc=int(sys.argv[4]) if len(sys.argv)>4 else None
raw=bytes(rom.files[F[path]])
if narc is not None: raw=bytes(ndspy.narc.NARC(raw).files[narc])
d=bytes(lz11.decompress(raw) if raw[0]==0x11 else ndspy.lz10.decompress(raw)) if raw[0] in (0x10,0x11) else raw
B=pudlabel.blocks(d)
if 'RLCN' not in B:
    r2=bytes(rom.files[F['romdata/PUD/mgentryphase/ja/ep_sprite1.POBJ.z']]); d2=bytes(lz11.decompress(r2)) if r2[0]==0x11 else bytes(ndspy.lz10.decompress(r2)); B['RLCN']=pudlabel.blocks(d2)['RLCN']   # 그림책 제목은 팔레트가 없어 ep_sprite1 것
palb=B.get('RLCN'); pal=ncer.nclr(palb[1]) if palb else None
sp=pudlabel.Sprites(B['RECN'][1],B['RGCN'][1]); sp0=pudlabel.Sprites(B['RECN'][1],B['RGCN'][1])
errs=[]
for k,t in spec.items():
    if isinstance(t[4],str) and t[4].startswith('grad:'): t[4]=pudlabel.ramp(sp0,int(t[4][5:]),pal)
for c,t in spec.items():
    if not t[0]: continue
    try:
      if t[3]=='seg': pudlabel.rewrap_seg(sp,int(c.split('#')[0]),t[0],pal,seg=tuple(t[1]) if t[1] else None,font=t[2] or 'Galmuri11',fill=t[4] or 'hgrad'); continue
      if t[3]=='ttf': pudlabel.ttf_cell(sp,int(c.split('#')[0]),t[0],pal,order=t[4] or 'lumr'); continue
      if t[3]=='glyph': pudlabel.glyph_cell(sp,int(c.split('#')[0]),t[0],pal,font=t[2] or 'Galmuri7',fill=t[4]); continue
      if t[3]=='rewrap': pudlabel.rewrap(sp,int(c.split('#')[0]),t[0],font=t[2] or 'Galmuri9',fill=t[4] or 'grad',pal=pal); continue
      pudlabel.relabel(sp,int(c.split('#')[0]),t[0],rect=tuple(t[1]) if t[1] else None,font=t[2],erase_to=t[3],fill=t[4],align=t[5] or 'center',ring=bool(t[6]),edge_c=t[7],pal=pal)
    except AssertionError as e: errs.append(str(e))
def img(s,c):
    can,cov,x0,y0=s.canvas(c); im=Image.new('RGB',(len(can[0]),len(can)),(40,40,60))
    objs=s.cells[c]
    for y,r in enumerate(can):
        for x,v in enumerate(r):
            if v:
                k=v if s.bpp==8 else objs[0]['pal']*16+v
                im.putpixel((x,y),pal[k] if pal and k<len(pal) else (v*17%256,)*3)
    return im
rows=[]
for c in dict.fromkeys(k.split('#')[0] for k in spec):
    a,b=img(sp0,int(c)),img(sp,int(c)); rows.append((c,a,b))
S=2; W=max(a.width for _,a,_ in rows)*S*2+30; H=sum(max(a.height,12)*S+6 for _,a,_ in rows)
o=Image.new('RGB',(W,H)); d_=ImageDraw.Draw(o); y=0
for c,a,b in rows:
    o.paste(a.resize((a.width*S,a.height*S),Image.NEAREST),(0,y)); o.paste(b.resize((b.width*S,b.height*S),Image.NEAREST),(W//2,y)); d_.text((W//2-24,y),str(c),fill=(255,255,0)); y+=max(a.height,12)*S+6
o.save('work/gfx/pud_%s.png'%name); print(o.size,'errors',errs)
