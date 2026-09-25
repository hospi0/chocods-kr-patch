# 사용: python work/pud_cell.py <경로> <셀> [x0 x1]  — pud_specs.json 을 적용한 뒤 셀 화소를 찍는다
import sys,json; sys.path.insert(0,'tools')
import ndspy.rom, ndspy.lz10, lz11, ncer, pudlabel
rom=ndspy.rom.NintendoDSRom.fromFile(r'C:\claude\roms\nds\Cid to Chocobo no Fushigi na Dungeon - Toki Wasure no Meikyuu DS+ (Japan).nds')
F={l.split('\t')[1]:int(l.split('\t')[0]) for l in open('work/files.tsv',encoding='utf-8')}
path=sys.argv[1]; S=json.load(open('work/pud_specs.json',encoding='utf-8'))[path]
raw=bytes(rom.files[F[path]]); d=bytes(lz11.decompress(raw) if raw[0]==0x11 else ndspy.lz10.decompress(raw))
B=pudlabel.blocks(d)
if 'RLCN' not in B:
    r2=bytes(rom.files[F['romdata/PUD/mgentryphase/ja/ep_sprite1.POBJ.z']]); d2=bytes(lz11.decompress(r2)) if r2[0]==0x11 else bytes(ndspy.lz10.decompress(r2)); B['RLCN']=pudlabel.blocks(d2)['RLCN']   # 그림책 제목은 팔레트가 없어 ep_sprite1 것
pal=ncer.nclr(B['RLCN'][1]); sp=pudlabel.Sprites(B['RECN'][1],B['RGCN'][1]); sp0=pudlabel.Sprites(B['RECN'][1],B['RGCN'][1])
for c,t in S.items():
    t=(t+[None]*7)[:8] if isinstance(t,list) else [t]+[None]*7
    if not t[0]: continue
    if isinstance(t[4],str) and t[4].startswith('grad:'): t[4]=pudlabel.ramp(sp0,int(t[4][5:]),pal)
    if t[3]=='seg': pudlabel.rewrap_seg(sp,int(c.split('#')[0]),t[0],pal,seg=tuple(t[1]) if t[1] else None,font=t[2] or 'Galmuri11',fill=t[4] or 'hgrad'); continue
    if t[3]=='ttf': pudlabel.ttf_cell(sp,int(c.split('#')[0]),t[0],pal,order=t[4] or 'lumr'); continue
    if t[3]=='glyph': pudlabel.glyph_cell(sp,int(c.split('#')[0]),t[0],pal,font=t[2] or 'Galmuri7',fill=t[4]); continue
    if t[3]=='rewrap': pudlabel.rewrap(sp,int(c.split('#')[0]),t[0],font=t[2] or 'Galmuri9',fill=t[4] or 'grad',pal=pal); continue
    pudlabel.relabel(sp,int(c.split('#')[0]),t[0],rect=tuple(t[1]) if t[1] else None,font=t[2],erase_to=t[3],fill=t[4],align=t[5] or 'center',ring=bool(t[6]),edge_c=t[7],pal=pal)
can,_,_,_=sp.canvas(int(sys.argv[2])); a=int(sys.argv[3]) if len(sys.argv)>3 else 0; b=int(sys.argv[4]) if len(sys.argv)>4 else 999
for r in can: print(''.join('.' if v==0 else '%x'%(v%16) for v in r[a:b]))
