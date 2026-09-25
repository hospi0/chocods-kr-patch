import sys; sys.path.insert(0,'tools')
import ndspy.rom, lz11, fbc, ncer, chaptitle
from PIL import Image
rom=ndspy.rom.NintendoDSRom.fromFile(r'C:\claude\roms\nds\Cid to Chocobo no Fushigi na Dungeon - Toki Wasure no Meikyuu DS+ (Japan).nds')
F={l.split('\t')[1]:int(l.split('\t')[0]) for l in open('work/files.tsv',encoding='utf-8')}
rows=[]
for k in range(1,7):
    d=bytes(lz11.decompress(bytes(rom.files[F['romdata/EVT_DAT/evt_dat%d.FBC.z'%(1199+k)]]))); ents=dict(fbc.walk(d))
    base='@fbc/evt_title_%02d.FBC/evt_title_%02d'%(k,k)
    ce,cb=ents[base+'.NCER'],ents[base+'.NCBR']; pl=ncer.nclr(ents[base+'.NCLR'])
    h,t=chaptitle.TITLES[k]
    nce,ncb,_=chaptitle.build(ce,cb,h,t)
    for e,b in ((ce,cb),(nce,ncb)):
        o,sz=ncer.ncgr_data(b); data=b[o:o+sz]; cells=ncer.cells(e)
        can,cov,x0,y0=ncer.cell_canvas(cells[0],lambda ob: ncer.obj_pixels_bitmap(data,ob,32))
        im=Image.new('RGB',(256,len(can)))
        off=128+x0
        for y,r in enumerate(can):
            for x,v in enumerate(r):
                if 0<=off+x<256: im.putpixel((off+x,y),pl[v])
        rows.append(im)
o=Image.new('RGB',(256*2+10,sum(max(rows[i].height,rows[i+1].height)+4 for i in range(0,12,2)))); y=0
for i in range(0,12,2):
    o.paste(rows[i],(0,y)); o.paste(rows[i+1],(266,y)); y+=max(rows[i].height,rows[i+1].height)+4
o.resize((o.width*2,o.height*2),Image.NEAREST).save('work/gfx/_chap.png'); print(o.size)
