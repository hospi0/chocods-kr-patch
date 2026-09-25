# 사용: python work/pud_dump.py <경로> <셀> <글자> [rect json]
import sys,json; sys.path.insert(0,'tools')
import ndspy.rom, lz11, ndspy.lz10, ncer, pudlabel
rom=ndspy.rom.NintendoDSRom.fromFile(r'C:\claude\roms\nds\Cid to Chocobo no Fushigi na Dungeon - Toki Wasure no Meikyuu DS+ (Japan).nds')
F={l.split('\t')[1]:int(l.split('\t')[0]) for l in open('work/files.tsv',encoding='utf-8')}
raw=bytes(rom.files[F[sys.argv[1]]])
d=bytes(lz11.decompress(raw) if raw[0]==0x11 else ndspy.lz10.decompress(raw))
B=pudlabel.blocks(d); pal=ncer.nclr(B['RLCN'][1])
sp=pudlabel.Sprites(B['RECN'][1],B['RGCN'][1]); c=int(sys.argv[2])
A=sys.argv+[None]*3
pudlabel.relabel(sp,c,A[3],rect=tuple(json.loads(A[4])) if A[4] else None,font=A[5],erase_to=A[6],pal=pal)
can,cov,x0,y0=sp.canvas(c)
for r in can: print(''.join('.' if v==0 else '%x'%(v%16) for v in r))
