import sys; sys.path.insert(0,'tools'); sys.path.insert(0,'work')
import ndspy.rom, ndspy.lz10, lz11, ncer, cardbin, cardname
from card_words_ko import NAMES, SKILLS, GFX_SHORT
from PIL import Image, ImageDraw
rom=ndspy.rom.NintendoDSRom.fromFile(r'C:\claude\roms\nds\Cid to Chocobo no Fushigi na Dungeon - Toki Wasure no Meikyuu DS+ (Japan).nds')
F={l.split('\t')[1]:int(l.split('\t')[0]) for l in open('work/files.tsv',encoding='utf-8')}
ids={}
for f in ('work/romdata_PUD_card_card.bin.z.bin','work/romdata_PUD_card_ja_card.bin.z.bin'):
    h,recs,pools=cardbin.parse(open(f,'rb').read())
    ids.update({'%04d'%r[0]:(pools['name'].get(r[2]),pools['skill'].get(r[3])) for r in recs})
def sk(s):
    kai=s.endswith('･改') or s.endswith('・改'); b=s[:-2] if kai else s
    return SKILLS[b]+('·개' if kai else '')
files=[l.split('\t')[1] for l in open('work/files.tsv',encoding='utf-8') if 'card/ja/name_' in l]
tiles=[]; errs=[]
for p in files:
    n=p[-11:-7]; nm,s=ids[n]
    raw=bytes(rom.files[F[p]]); g=bytes(lz11.decompress(raw)) if raw[0]==0x11 else bytes(ndspy.lz10.decompress(raw))
    try: g2=cardname.render(g,NAMES[nm],GFX_SHORT.get(sk(s),sk(s)))
    except AssertionError as e: errs.append(str(e)); continue
    for gg in (g,g2):
        o,sz=ncer.ncgr_data(gg); data=gg[o:o+sz]
        im=Image.new('L',(64,32))
        for y in range(32):
            for x in range(64):
                v=data[((y//8)*8+x//8)*64+(y%8)*8+x%8]; im.putpixel((x,y),(v-224)*17 if v>=224 else 128)
        tiles.append((n,im))
print('errors',errs, 'tiles',len(tiles))
for part in range(4):
    sub=tiles[part*80:(part+1)*80]
    o=Image.new('L',(8*140,10*76)); d=ImageDraw.Draw(o)
    for k,(n,im) in enumerate(sub):
        x,y=(k%8)*140,(k//8)*76; o.paste(im.resize((128,64),Image.NEAREST),(x,y+10)); d.text((x,y),n,fill=255)
    o.save('work/gfx/_cn%d.png'%part)
