# 사용: python work/mov_sheet.py <이름>  — MODS 영상 1초마다 한 장씩 YCgCo→RGB 로 모아 work/mov/<이름>_sheet.png
import sys,subprocess,numpy as np
from PIL import Image, ImageDraw
FF=r'C:\claude\utils\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe'
n=sys.argv[1]; step=int(sys.argv[2]) if len(sys.argv)>2 else 12
raw=subprocess.run([FF,'-v','error','-i','work/mov/%s.mods'%n,'-f','rawvideo','-pix_fmt','yuv420p','-'],capture_output=True).stdout
W,H=256,192; fs=W*H*3//2; nf=len(raw)//fs
ims=[]
for k in range(0,nf,step):
    b=np.frombuffer(raw[k*fs:(k+1)*fs],np.uint8)
    Y=b[:W*H].reshape(H,W).astype(int); U=b[W*H:W*H+W*H//4].reshape(H//2,W//2).repeat(2,0).repeat(2,1).astype(int)-128
    V=b[W*H+W*H//4:].reshape(H//2,W//2).repeat(2,0).repeat(2,1).astype(int)-128
    Cg,Co=U,V; t=Y-Cg; G=Y+Cg; R=t+Co; B=t-Co
    rgb=np.clip(np.stack([R,G,B],-1),0,255).astype(np.uint8); ims.append((k,Image.fromarray(rgb)))
cols=6; rows=(len(ims)+cols-1)//cols
o=Image.new('RGB',(cols*W//2,rows*(H//2+10))); d=ImageDraw.Draw(o)
for i,(k,im) in enumerate(ims):
    x,y=(i%cols)*W//2,(i//cols)*(H//2+10); o.paste(im.resize((W//2,H//2)),(x,y+10)); d.text((x,y),'%d'%(k//12),fill=(255,255,0))
o.save('work/mov/%s_sheet.png'%n); print(n,nf,'frames',len(ims),'shots',o.size)
