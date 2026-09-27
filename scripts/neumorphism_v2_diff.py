"""Lossless screenshot juxtaposition and numerical pixel differences, no retouching."""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

parser=argparse.ArgumentParser()
parser.add_argument('old',choices=['original','previous'])
parser.add_argument('new',choices=['previous','revised'])
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]/'docs/images/neumorphism-v2'
out=root/f'{args.old}-vs-{args.new}'
out.mkdir(parents=True,exist_ok=True)
rows=[]
font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',24)
for source in sorted((root/args.old).glob('0*.png')):
    target=root/args.new/source.name
    if not target.exists():continue
    old,new=Image.open(source).convert('RGB'),Image.open(target).convert('RGB')
    assert old.size==new.size==(1440,900)
    pair=Image.new('RGB',(2880,948),'#183954')
    draw=ImageDraw.Draw(pair)
    draw.text((24,8),f'OLD | {args.old}',fill='white',font=font)
    draw.text((1464,8),f'NEW | {args.new}',fill='white',font=font)
    pair.paste(old,(0,48));pair.paste(new,(1440,48))
    pair.save(out/source.name)
    pair.resize((1440,474),Image.Resampling.LANCZOS).save(out/f'{source.stem}-50pct.png')
    delta=np.abs(np.array(old,dtype=np.int16)-np.array(new,dtype=np.int16)).max(axis=2)
    mask=delta>16
    diff=np.full((900,1440,3),245,dtype=np.uint8)
    diff[mask]=[24,93,168]
    Image.fromarray(diff).save(out/f'{source.stem}-diff.png')
    # Also compare coarse tiles, to show distribution rather than one global background change.
    tile=mask.reshape(9,100,12,120).mean(axis=(1,3))
    edges=(np.array(old.convert('L').filter(ImageFilter.FIND_EDGES))>32)|(np.array(new.convert('L').filter(ImageFilter.FIND_EDGES))>32)
    rows.append({'page':source.stem,'threshold_rgb':16,'changed_area_percent':round(float(mask.mean()*100),2),
                 'changed_tiles_over_10pct':int((tile>.1).sum()),'total_tiles':108,
                 'changed_edges_percent':round(float(mask[edges].mean()*100),2),
                 'mean_channel_max_difference':round(float(delta.mean()),2)})
(out/'pixel-diff.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
print(json.dumps(rows,indent=2))
