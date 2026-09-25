# 사용: python work/pud_sheet.py <경로> <출력.png> [narc 번호]  — 셀 전부를 번호와 함께 한 장에
import sys; sys.path.insert(0,'tools')
import ndspy.rom, ndspy.narc, ndspy.lz10, lz11, ncer, pudlabel
from PIL import Image, ImageDraw
rom=ndspy.rom.NintendoDSRom.fromFile(r'C:\claude\roms\nds\Cid to Chocobo no Fushigi na Dungeon - Toki Wasure no Meikyuu DS+ (Japan).nds')
F={l.split('\t')[1]:int(l.split('\t')[0]) for l in open('work/files.tsv',encoding='utf-8')}
raw=bytes(rom.files[F[sys.argv[1]]])
if len(sys.argv)>3: raw=bytes(ndspy.narc.NARC(raw).files[int(sys.argv[3])])
d=bytes(lz11.decompress(raw) if raw[0]==0x11 else ndspy.lz10.decompress(raw)) if raw[0] in (0x10,0x11) else raw
B=pudlabel.blocks(d)
if 'RLCN' in B: pal=ncer.nclr(B['RLCN'][1])
else:
    r2=bytes(rom.files[F['romdata/PUD/mgentryphase/ja/ep_sprite1.POBJ.z']]); d2=bytes(lz11.decompress(r2)) if r2[0]==0x11 else ndspy.lz10.decompress(r2); pal=ncer.nclr(pudlabel.blocks(bytes(d2))['RLCN'][1])   # 제목 그림은 팔레트가 없어 ep_sprite1 것을 쓴다
sp=pudlabel.Sprites(B['RECN'][1],B['RGCN'][1])
ims=[]
for c,objs in enumerate(sp.cells):
    if not objs: continue
    can,cov,x0,y0=sp.canvas(c); im=Image.new('RGB',(len(can[0]),len(can)),(40,40,60))
    for y,r in enumerate(can):
        for x,v in enumerate(r):
            if v:
                ob=[o for o in objs if o['x']-x0<=x<o['x']-x0+o['w'] and o['y']-y0<=y<o['y']-y0+o['h']][0]
                k=v if sp.bpp==8 else ob['pal']*16+v; im.putpixel((x,y),pal[k] if k<len(pal) else (255,0,255))
    ims.append((c,im))
W=1024; x=y=0; rowh=0; pos=[]
for c,im in ims:
    if x+im.width>W: x=0; y+=rowh+12; rowh=0
    pos.append((c,im,x,y+10)); x+=im.width+6; rowh=max(rowh,im.height)
o=Image.new('RGB',(W,y+rowh+14)); dr=ImageDraw.Draw(o)
for c,im,x,y in pos: o.paste(im,(x,y)); dr.text((x,y-10),'c%d'%c,fill=(255,255,0))
o.save(sys.argv[2]); print(o.size)
