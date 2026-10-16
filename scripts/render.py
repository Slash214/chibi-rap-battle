from pathlib import Path
import os,json,subprocess,numpy as np
from PIL import Image,ImageDraw,ImageFont
P=Path(__file__).resolve().parents[1]/'episodes/suno-chibi';V=P/'mv-v2'
plan=json.loads((V/'plan.json').read_text(encoding='utf-8'));W,H=plan['width'],plan['height'];fps=plan['fps']
def ff(args):subprocess.run(['ffmpeg','-y','-v','error']+args,check=True)
def font(size,bold=True):
 candidates=[os.environ.get('CJK_FONT',''),r'C:\Windows\Fonts\msyhbd.ttc' if bold else r'C:\Windows\Fonts\msyh.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc','/System/Library/Fonts/PingFang.ttc']
 for f in candidates:
  if f and Path(f).is_file(): return ImageFont.truetype(f,size)
 raise FileNotFoundError('Set CJK_FONT to a Chinese font .ttf/.ttc file')
def center(d,text,y,size,color=(247,210,119,255)):
 f=font(size);box=d.textbbox((0,0),text,font=f);x=(W-(box[2]-box[0]))/2
 d.text((x,y),text,font=f,fill=color,stroke_width=2,stroke_fill=(16,12,8,230))
def overlay(s):
 im=Image.new('RGBA',(W,H));d=ImageDraw.Draw(im)
 for y in range(H-115,H):d.line((0,y,W,y),fill=(5,8,14,int(155*(y-H+115)/115)))
 d.text((W-225,24),'AI 生成 · 仅供娱乐',font=font(18,False),fill=(230,218,187,210),stroke_width=1,stroke_fill=(0,0,0,200))
 if s['lyric']:
  center(d,s['lyric'],H-76,36)
  name='周瑜' if s['id'].startswith('A') else '诸葛亮'
  d.rounded_rectangle((32,28,175 if name=='周瑜' else 210,82),radius=5,fill=(10,10,12,135))
  d.text((48,33),name,font=font(30),fill=(250,213,124,255),stroke_width=1,stroke_fill=(15,12,10,255))
 elif s['id']=='OPEN':
  center(d,'赤壁借风',H-195,62);center(d,'周瑜  ×  诸葛亮',H-110,26,(242,231,209,255))
 elif s['id']=='END02B':
  center(d,'赤壁借风',H-165,48);center(d,'周瑜  ×  诸葛亮',H-98,25,(242,231,209,255))
 im.save(V/s['id']/'overlay.png')
def main():
 render=V/'render';render.mkdir(exist_ok=True)
 md=['# 赤壁借风 · 剪辑单','',f'成片目标时长：42.33 秒；原生 {W} × {H}；24 fps。','声音：完整保留用户提供的 Suno 歌曲，不追加欢呼、不改变音高。','字幕：原定八句歌词，金色底部字幕；原音轨 ASR 只用于定位。','']
 checks=[]
 for s in plan['shots']:
  sid=s['id'];d=V/sid;v=d/'video.mp4';assert v.exists(),f'Missing {sid}'
  overlay(s)
  md.extend([f'## CUT-{sid}',f'- 来源：MOTION-{sid} · {v}',f"- 入点：{s['lead_frames']/fps:.6f} 秒",f"- 出点：{(s['lead_frames']+s['timeline_frames'])/fps:.6f} 秒",f"- 时长：{s['timeline_frames']/fps:.6f} 秒",f"- 字幕：{s['lyric'] or '无'}",'- 声音：舍弃逐镜音轨，最终统一挂原歌曲，避免接缝。',''])
 (V/'剪辑单.md').write_text('\n'.join(md),encoding='utf-8')
 for s in plan['shots']:
  sid=s['id'];d=V/sid;v=d/'video.mp4';out=render/(sid+'.mp4')
  ff(['-i',str(v),'-f','null','-'])
  filt=f"[0:v]trim=start_frame={s['lead_frames']}:end_frame={s['lead_frames']+s['timeline_frames']},setpts=PTS-STARTPTS,setsar=1[base];[base][1:v]overlay=0:0:shortest=1,format=yuv420p[v]"
  if sid=='END02B':
   filt=filt.replace(',format=yuv420p[v]',f",fade=t=out:st={s['timeline_frames']/fps-.5}:d=0.5,format=yuv420p[v]")
  ff(['-i',str(v),'-loop','1','-i',str(d/'overlay.png'),'-filter_complex',filt,'-map','[v]','-an','-frames:v',str(s['timeline_frames']),'-r',str(fps),'-c:v','libx264','-preset','medium','-crf','18',str(out)])
  ff(['-ss',str(max(0,s['timeline_frames']/fps/2)),'-i',str(out),'-frames:v','1',str(d/'preview.jpg')])
  print('RENDERED',sid,flush=True)
 (render/'concat.txt').write_text('\n'.join("file '"+s['id']+".mp4'" for s in plan['shots']),encoding='utf-8')
 final=P/'赤壁借风-周瑜对诸葛亮-成片-v2.mp4'
 ff(['-f','concat','-safe','0','-i',str(render/'concat.txt'),'-i',str(P/'song.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-af','apad','-t',str(sum(s['timeline_frames'] for s in plan['shots'])/fps),'-c:a','aac','-b:a','320k','-movflags','+faststart',str(final)])
 ff(['-i',str(final),'-f','null','-'])
 info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(final)]))
 def pcm(path):return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-ac','1','-ar','48000','-f','f32le','-']),np.float32)
 a,b=pcm(final),pcm(P/'song.wav');n=min(len(a),len(b));corr=float(np.corrcoef(a[:n],b[:n])[0,1])
 report={'file':str(final),'duration':info['format']['duration'],'bytes':final.stat().st_size,'audio_correlation_to_suno':corr,'full_decode':'passed','native_size':[W,H],'frames_expected':sum(s['timeline_frames'] for s in plan['shots']),'shots':len(plan['shots']),'lyrics':8,'perceptual_lip_sync':'requires human playback review','streams':info['streams']}
 (V/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 thumbs=Image.new('RGB',(W//3*3,(H//3+30)*5),(20,20,22));td=ImageDraw.Draw(thumbs)
 for i,s in enumerate(plan['shots']):
  im=Image.open(V/s['id']/'preview.jpg');im.thumbnail((W//3,H//3));x=(i%3)*(W//3);y=(i//3)*(H//3+30)
  thumbs.paste(im,(x,y));td.text((x+5,y+H//3+2),s['id'],font=font(17),fill='white')
 thumbs.save(V/'成片总览.jpg')
 print(json.dumps({k:v for k,v in report.items() if k!='streams'},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
