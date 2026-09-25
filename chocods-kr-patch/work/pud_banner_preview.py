import sys; sys.path.insert(0,'tools')
import ndspy.rom, ndspy.narc, ndspy.lz10, lz11, pudlabel, ncer, pudbanner
from PIL import Image
rom=ndspy.rom.NintendoDSRom.fromFile(r'C:\claude\roms\nds\Cid to Chocobo no Fushigi na Dungeon - Toki Wasure no Meikyuu DS+ (Japan).nds')
F={l.split('\t')[1]:int(l.split('\t')[0]) for l in open('work/files.tsv',encoding='utf-8')}
raw=bytes(ndspy.narc.NARC(bytes(rom.files[F['romdata/PUD/pub/pubtopmenu/pubtopmenu_ja_.narc']])).files[3])
d=bytes(ndspy.lz10.decompress(raw)) if raw[0]==0x10 else bytes(lz11.decompress(raw))
B=pudlabel.blocks(d); pal=ncer.nclr(B['RLCN'][1])
g=pudbanner.build(B['RECN'][1],B['RGCN'][1],pal)
s0=pudlabel.Sprites(B['RECN'][1],B['RGCN'][1]); s1=pudlabel.Sprites(B['RECN'][1],g)
assert s0.canvas(0)[0]==s1.canvas(0)[0], 'Wi-Fi 배너가 바뀜'
def img(s,c):
    can,_,_,_=s.canvas(c); im=Image.new('RGB',(len(can[0]),len(can)),(40,40,60))
    for y,r in enumerate(can):
        for x,v in enumerate(r):
            if v: im.putpixel((x,y),pal[v])
    return im
rows=[(img(s0,c),img(s1,c)) for c in range(1,7)]
W=rows[0][0].width; o=Image.new('RGB',(W*2+10,sum(a.height+4 for a,_ in rows))); y=0
for a,b in rows: o.paste(a,(0,y)); o.paste(b,(W+10,y)); y+=a.height+4
o.resize((o.width*2,o.height*2),Image.NEAREST).save('work/gfx/pud_top3.png')
