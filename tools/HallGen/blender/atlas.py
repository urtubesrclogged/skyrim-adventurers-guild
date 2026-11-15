import sys,os
from PIL import Image, ImageDraw
import numpy as np
from scipy import ndimage
T,out=sys.argv[1],sys.argv[2]
for n in ['swindow01.dds','swindow03.dds','sdoor01.dds','sdoor02.dds','snail01.dds']:
    im=Image.open(os.path.join(T,n)).convert('RGB'); a=np.asarray(im).astype(int)
    bg=a[5:40,-40:-5].reshape(-1,3).mean(0) if n!='snail01.dds' else np.array([0,0,0])
    diff=np.abs(a-bg).sum(2)>40
    diff=ndimage.binary_opening(diff,iterations=3)
    lab,k=ndimage.label(diff)
    boxes=[s for s in ndimage.find_objects(lab) if (s[0].stop-s[0].start)*(s[1].stop-s[1].start)>a.shape[0]*a.shape[1]*0.003]
    W,H=im.size
    print('##',n,W,H,'bg',bg.round())
    d=ImageDraw.Draw(im)
    for i,s in enumerate(sorted(boxes,key=lambda s:(s[0].start//200,s[1].start))):
        y0,y1,x0,x1=s[0].start,s[0].stop,s[1].start,s[1].stop
        print(f"  {i}: u {x0/W:.3f}-{x1/W:.3f}  v {y0/H:.3f}-{y1/H:.3f}  px {x1-x0}x{y1-y0}")
        d.rectangle([x0,y0,x1,y1],outline=(255,0,0),width=6); d.text((x0+10,y0+10),str(i),fill=(255,255,0))
    im.resize((768,768)).save(os.path.join(out,'atlas_'+n.replace('.dds','.png')))
