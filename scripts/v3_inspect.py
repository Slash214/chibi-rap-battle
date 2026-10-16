"""Technical checks and timed contact sheets; not perceptual acceptance."""
import json, pathlib, subprocess
from PIL import Image, ImageDraw
R=pathlib.Path(__file__).resolve().parents[1]
V=R/'episodes/suno-chibi/mv-v3'
plan=json.loads((V/'plan.json').read_text(encoding='utf-8'))
rows=json.loads((V/'technical-checks.json').read_text()) if (V/'technical-checks.json').exists() else []
for c in plan['clips']:
 d=V/'clips'/c['id']; f=d/'video.mp4'
 if not f.exists(): continue
 if (d/'review-full.jpg').exists() and (d/'review-full.jpg').stat().st_mtime>=f.stat().st_mtime:continue
 rows=[x for x in rows if x['clip']!=c['id']]
 subprocess.run(['ffmpeg','-v','error','-i',str(f),'-f','null','-'],check=True)
 info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(f)]))
 stream=next(x for x in info['streams'] if x['codec_type']=='video')
 count=int(stream['nb_frames']); assert (stream['width'],stream['height'],stream['r_frame_rate'])==(1216,672,'24/1')
 for cut in plan['timeline']:
  if cut['clip']==c['id']:assert cut['in_frame']+cut['frames']<=count
 indices=list(range(0,count,6))
 sheet=Image.new('RGB',(4*456,((len(indices)+3)//4)*276))
 import io
 for i,n in enumerate(indices):
  png=subprocess.check_output(['ffmpeg','-v','error','-i',str(f),'-vf',f"select='eq(n,{n})',scale=456:252",'-frames:v','1','-f','image2pipe','-vcodec','png','-'])
  im=Image.open(io.BytesIO(png));x=(i%4)*456;y=(i//4)*276;sheet.paste(im,(x,y))
  ImageDraw.Draw(sheet).text((x+5,y+254),f"{c['id']} frame {n} / {n/24:.3f}s",fill='white')
 sheet.save(d/'review-full.jpg')
 rows.append({'clip':c['id'],'frames':count,'decode':'passed','review':'requires visual and audio playback review'})
 print('CHECKED',c['id'],count,flush=True)
(V/'technical-checks.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
