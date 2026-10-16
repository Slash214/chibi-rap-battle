import os, json, math, pathlib, subprocess, urllib.request, urllib.parse, uuid, time, sys
R=pathlib.Path(__file__).resolve().parents[1]
P=R/'episodes/suno-chibi'; V=P/'mv-v2'; V.mkdir(exist_ok=True)
BASE=os.environ.get('COMFYUI_URL','http://127.0.0.1:8188').rstrip('/'); FPS=24; W=1216; H=672
def req(path,data=None):
 b=json.dumps(data).encode() if data is not None else None
 return json.load(urllib.request.urlopen(urllib.request.Request(BASE+path,data=b,headers={'Content-Type':'application/json'}),timeout=120))
def upload(path):
 boundary=uuid.uuid4().hex
 data=(f'--{boundary}\r\nContent-Disposition: form-data; name="subfolder"\r\n\r\nancient-rap-battle/suno-chibi\r\n--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{path.name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()+path.read_bytes()+f'\r\n--{boundary}--\r\n'.encode())
 q=json.load(urllib.request.urlopen(urllib.request.Request(BASE+'/upload/image',data=data,headers={'Content-Type':f'multipart/form-data; boundary={boundary}'}),timeout=120))
 return q['subfolder']+'/'+q['name']
def ff(args):subprocess.run(['ffmpeg','-y','-v','error']+args,check=True)
def prepare():
 plan=json.loads((V/'plan.json').read_text(encoding='utf-8'))['shots']
 if not (P/'song.wav').exists():
  ff(['-i',str(P/'赤壁借风.m4a'),'-ar','48000','-ac','2','-c:a','pcm_s24le',str(P/'song.wav')])
 assert (P/'vocals.wav').exists(), 'Include supplied vocal stem or separate the Suno song first'
 for spec in plan:
  d=V/spec['id'];d.mkdir(exist_ok=True)
  n=spec['timeline_frames'];lead=spec['lead_frames'];length=spec['generation_frames']
  for source,out in [('vocals.wav','drive.wav'),('song.wav','mix.wav')]:
   af=f'afade=t=in:d=0.004,afade=t=out:st={max(0,n/FPS-.006)}:d=0.006,adelay={lead/FPS*1000}:all=1,apad'
   ff(['-ss',str(spec['source_start_frame']/FPS),'-t',str(n/FPS),'-i',str(P/source),'-af',af,'-t',str(length/FPS),'-ar','48000',str(d/out)])
 print('Prepared existing authoritative plan; no video submitted',flush=True)
def run():
 plan=json.loads((V/'plan.json').read_text(encoding='utf-8'))['shots']
 selected=sys.argv[2:] if len(sys.argv)>2 else []
 for spec in plan:
  sid=spec['id']
  if selected and sid not in selected:continue
  d=V/sid
  if (d/'video.mp4').exists():print('EXISTS',sid,flush=True);continue
  if (d/'task.json').exists():tid=json.loads((d/'task.json').read_text())['prompt_id']
  else:
   assert not (V/'PAUSED.txt').exists(), 'Awaiting user settings confirmation'
   q=req('/queue')
   assert not q['queue_running'] and not q['queue_pending'],'GPU queue occupied; resume later'
   g=json.loads((R/'workflows/h3-base.api.json').read_text(encoding='utf-8'))
   g['1']['inputs']['unet_name']='minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors'
   g['30']={'class_type':'LoraLoaderModelOnly','inputs':{'model':['1',0],'lora_name':'minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors','strength_model':1.0}}
   g['31']={'class_type':'LoraLoaderModelOnly','inputs':{'model':['30',0],'lora_name':'h3-realism-people-t2v-i2v-r2v.safetensors','strength_model':1.0}}
   g['13']['inputs']['model']=['31',0]
   g['16']['inputs'].update(model=['31',0],steps=8)
   g['10']['inputs']['image']=upload(V/(spec['reference']+'.png'))
   g['11']['inputs']['audio']=upload(d/'drive.wav')
   g['21']['inputs']['audio']=upload(d/'mix.wav')
   g['12']['inputs'].update(width=W,height=H,length=spec['generation_frames'],prompt=spec['prompt'])
   g['14']['inputs']['noise_seed']=20261016+plan.index(spec)
   g['20']['inputs']['filename_prefix']='ancient-rap-battle/suno-chibi/mv-v2/'+sid
   (d/'request.json').write_text(json.dumps(g,ensure_ascii=False,indent=2),encoding='utf-8')
   result=req('/prompt',{'prompt':g,'client_id':'suno-chibi-mv-v2'})
   (d/'task.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
   tid=result['prompt_id'];print('SUBMITTED',sid,tid,flush=True)
  start=time.time()
  while True:
   h=req('/history/'+tid)
   if tid in h:
    h=h[tid];(d/'history.json').write_text(json.dumps(h,ensure_ascii=False,indent=2),encoding='utf-8')
    assert h.get('status',{}).get('status_str')=='success',str(h.get('status'))
    for out in h.get('outputs',{}).values():
     for key in ['images','gifs','videos']:
      for f in out.get(key,[]):
       if f.get('filename','').endswith('.mp4'):
        url=BASE+'/view?'+urllib.parse.urlencode({k:f[k] for k in ['filename','subfolder','type']})
        (d/'video.mp4').write_bytes(urllib.request.urlopen(url,timeout=120).read())
    assert (d/'video.mp4').exists(),'No video returned'
    print('DONE',sid,'wait_seconds',round(time.time()-start,1),flush=True);break
   if time.time()-start>1800:raise TimeoutError('Retained task '+tid)
   time.sleep(5)
if __name__=='__main__':
 if sys.argv[1]=='prepare':prepare()
 elif sys.argv[1]=='run':run()
