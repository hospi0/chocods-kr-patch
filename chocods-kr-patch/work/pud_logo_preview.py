import sys; sys.path.insert(0,'tools')
import importlib, ndspy.rom, ndspy.narc, ndspy.lz10, lz11, pudlabel, ncer, pudlogo
from PIL import Image
rom=ndspy.rom.NintendoDSRom.fromFile(r'C:\claude\roms\nds\Cid to Chocobo no Fushigi na Dungeon - Toki Wasure no Meikyuu DS+ (Japan).nds')
F={l.split('\t')[1]:int(l.split('\t')[0]) for l in open('work/files.tsv',encoding='utf-8')}
raw=bytes(ndspy.narc.NARC(bytes(rom.files[F['romdata/PUD/pub/pubtopmenu/pubtopmenu_ja_.narc']])).files[4])
d=bytes(ndspy.lz10.decompress(raw)) if raw[0]==0x10 else bytes(lz11.decompress(raw))
B=pudlabel.blocks(d); pal=ncer.nclr(B['RLCN'][1])
g=pudlogo.build(B['RECN'][1],B['RGCN'][1],pal)
out=[]
for gb in (B['RGCN'][1],g):
    sp=pudlabel.Sprites(B['RECN'][1],gb); can,_,_,_=sp.canvas(0)
    im=Image.new('RGB',(len(can[0]),len(can)),(40,40,60))
    for y,r in enumerate(can):
        for x,v in enumerate(r):
            if v: im.putpixel((x,y),pal[v])
    out.append(im)
o=Image.new('RGB',(out[0].width*2+10,out[0].height)); o.paste(out[0],(0,0)); o.paste(out[1],(out[0].width+10,0))
o.resize((o.width*2,o.height*2),Image.NEAREST).save('work/gfx/pud_logo.png')
