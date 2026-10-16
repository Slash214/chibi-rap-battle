"""赤壁借风 mv-v3：按 episodes/suno-chibi/mv-v3/plan.json 准备、生成、重剪。

    python scripts/v3.py check                 # 检查参考图/素材缺口，不提交任何任务
    python scripts/v3.py prepare               # 建立 clips/ 目录、切音频、拷贝复用素材
    python scripts/v3.py run A01               # 提交单条（先测这一条）
    python scripts/v3.py run                   # 依次提交全部 new 素材（已有 video.mp4 跳过）
    python scripts/v3.py run B01 --retake      # 旧 take 移到 takes/，换种子重抽
    python scripts/v3.py render                # 按 timeline 拼接、叠字幕、挂原歌曲

锁定参数（不得擅自修改）：Hybrid UNet、FL2V turbo 8step LoRA 1.0、realism people LoRA 1.0、8 步、1216x672。
mv-v2 目录和 v2 成片完全不动。
"""
import os, sys, json, shutil, pathlib, subprocess, urllib.request, urllib.parse, uuid, time
R = pathlib.Path(__file__).resolve().parents[1]
P = R / 'episodes/suno-chibi'; V2 = P / 'mv-v2'; V = P / 'mv-v3'; C = V / 'clips'
BASE = os.environ.get('COMFYUI_URL', 'http://127.0.0.1:8188').rstrip('/')
plan = json.loads((V / 'plan.json').read_text(encoding='utf-8'))
FPS, W, H = plan['fps'], plan['width'], plan['height']
CLIPS = {c['id']: c for c in plan['clips']}

def ff(a): subprocess.run(['ffmpeg', '-y', '-v', 'error'] + [str(x) for x in a], check=True)

def ref_path(name):
    for p in [V / 'refs' / (name + '.png'), V2 / (name + '.png')]:
        if p.exists(): return p
    return None

def nframes(path):
    out = subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v',
                                   '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', str(path)])
    return int(out.strip())

# ---------------- check ----------------
def check():
    missing = sorted({c['reference'] for c in plan['clips'] if c['status'] == 'new' and not ref_path(c['reference'])})
    print('缺参考图（放进 episodes/suno-chibi/mv-v3/refs/）:', missing or '无')
    for c in plan['clips']:
        v = C / c['id'] / 'video.mp4'
        print(f"{c['id']:9s} {c['status']:6s} ref={c.get('reference', c.get('reuse_from')):14s} video={'有' if v.exists() else '—'}")
    print('timeline 总帧数', sum(t['frames'] for t in plan['timeline']), '/ 应为', plan['total_frames'])

# ---------------- prepare ----------------
def prepare(ids):
    for c in plan['clips']:
        if ids and c['id'] not in ids: continue
        d = C / c['id']; d.mkdir(parents=True, exist_ok=True)
        (d / 'spec.json').write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding='utf-8')
        if c['status'] == 'reuse':
            if not (d / 'video.mp4').exists(): shutil.copy2(V2 / c['reuse_from'] / 'video.mp4', d / 'video.mp4')
            print('REUSE', c['id'], '<- mv-v2/' + c['reuse_from'], flush=True); continue
        n = c['source_end_frame'] - c['source_start_frame']; lead = c['lead_frames']; L = c['generation_frames']
        assert lead + n <= L, c['id']
        ss, dur, total = c['source_start_frame'] / FPS, n / FPS, L / FPS
        af = f'afade=t=in:d=0.004,afade=t=out:st={max(0, dur - .006)}:d=0.006,adelay={lead / FPS * 1000}:all=1,apad'
        if c['drive'] == 'vocals':
            ff(['-ss', ss, '-t', dur, '-i', P / 'vocals.wav', '-af', af, '-t', total, '-ar', '48000', d / 'drive.wav'])
        else:  # 反应镜头：静音驱动，防止听的人对着别人的歌词动嘴
            ff(['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-t', total, d / 'drive.wav'])
        ff(['-ss', ss, '-t', dur, '-i', P / 'song.wav', '-af', af, '-t', total, '-ar', '48000', d / 'mix.wav'])
        print('PREPARED', c['id'], c['drive'], flush=True)

# ---------------- run ----------------
def req(path, data=None):
    b = json.dumps(data).encode() if data is not None else None
    return json.load(urllib.request.urlopen(urllib.request.Request(BASE + path, data=b, headers={'Content-Type': 'application/json'}), timeout=120))

def upload(path):
    boundary = uuid.uuid4().hex
    data = (f'--{boundary}\r\nContent-Disposition: form-data; name="subfolder"\r\n\r\nancient-rap-battle/suno-chibi-v3\r\n--{boundary}\r\n'
            f'Content-Disposition: form-data; name="image"; filename="{path.name}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode() \
           + path.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
    q = json.load(urllib.request.urlopen(urllib.request.Request(BASE + '/upload/image', data=data,
                  headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}), timeout=120))
    return q['subfolder'] + '/' + q['name']

def run(ids, retake):
    order = [c for c in plan['clips'] if c['status'] == 'new']
    for idx, c in enumerate(order):
        sid = c['id']
        if ids and sid not in ids: continue
        d = C / sid
        assert (d / 'drive.wav').exists(), f'先运行 prepare（{sid} 缺 drive.wav）'
        takes = d / 'takes'
        if retake and (d / 'video.mp4').exists():
            takes.mkdir(exist_ok=True); k = len(list(takes.glob('video_take*.mp4'))) + 1
            (d / 'video.mp4').rename(takes / f'video_take{k}.mp4')
            for f in ['task.json', 'history.json']:
                if (d / f).exists(): (d / f).rename(takes / f'{f[:-5]}_take{k}.json')
        if (d / 'video.mp4').exists(): print('EXISTS', sid, flush=True); continue
        take = len(list(takes.glob('video_take*.mp4'))) if takes.exists() else 0
        if (d / 'task.json').exists():
            tid = json.loads((d / 'task.json').read_text())['prompt_id']
        else:
            assert not (V / 'PAUSED.txt').exists(), 'mv-v3/PAUSED.txt 存在：等待用户确认'
            ref = ref_path(c['reference']); assert ref, f'缺参考图 {c["reference"]}.png'
            q = req('/queue'); assert not q['queue_running'] and not q['queue_pending'], 'GPU 队列被占用，稍后再试'
            g = json.loads((R / 'workflows/h3-base.api.json').read_text(encoding='utf-8'))
            g['1']['inputs']['unet_name'] = 'minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors'
            g['30'] = {'class_type': 'LoraLoaderModelOnly', 'inputs': {'model': ['1', 0], 'lora_name': 'minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors', 'strength_model': 1.0}}
            g['31'] = {'class_type': 'LoraLoaderModelOnly', 'inputs': {'model': ['30', 0], 'lora_name': 'h3-realism-people-t2v-i2v-r2v.safetensors', 'strength_model': 1.0}}
            g['13']['inputs']['model'] = ['31', 0]
            g['16']['inputs'].update(model=['31', 0], steps=8)
            g['10']['inputs']['image'] = upload(ref)
            g['11']['inputs']['audio'] = upload(d / 'drive.wav')
            g['21']['inputs']['audio'] = upload(d / 'mix.wav')
            g['12']['inputs'].update(width=W, height=H, length=c['generation_frames'], prompt=c['prompt'])
            g['14']['inputs']['noise_seed'] = 20261116 + idx + 1000 * take
            g['20']['inputs']['filename_prefix'] = 'ancient-rap-battle/suno-chibi/mv-v3/' + sid
            (d / 'request.json').write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding='utf-8')
            result = req('/prompt', {'prompt': g, 'client_id': 'suno-chibi-mv-v3'})
            (d / 'task.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            tid = result['prompt_id']; print('SUBMITTED', sid, 'take', take + 1, tid, flush=True)
        start = time.time()
        while True:
            h = req('/history/' + tid)
            if tid in h:
                h = h[tid]; (d / 'history.json').write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding='utf-8')
                assert h.get('status', {}).get('status_str') == 'success', str(h.get('status'))
                for out in h.get('outputs', {}).values():
                    for key in ['images', 'gifs', 'videos']:
                        for f in out.get(key, []):
                            if f.get('filename', '').endswith('.mp4'):
                                url = BASE + '/view?' + urllib.parse.urlencode({k: f[k] for k in ['filename', 'subfolder', 'type']})
                                (d / 'video.mp4').write_bytes(urllib.request.urlopen(url, timeout=120).read())
                assert (d / 'video.mp4').exists(), 'No video returned'
                (d / 'task.json').unlink()
                ff(['-ss', '1', '-i', d / 'video.mp4', '-frames:v', '1', d / 'preview.jpg'])
                print('DONE', sid, 'wait_seconds', round(time.time() - start, 1), flush=True); break
            if time.time() - start > 1800: raise TimeoutError('Retained task ' + tid)
            time.sleep(5)

# ---------------- render ----------------
def font(size, bold=True):
    from PIL import ImageFont
    for f in [os.environ.get('CJK_FONT', ''), r'C:\Windows\Fonts\msyhbd.ttc' if bold else r'C:\Windows\Fonts\msyh.ttc',
              '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', '/System/Library/Fonts/PingFang.ttc']:
        if f and pathlib.Path(f).is_file(): return ImageFont.truetype(f, size)
    raise FileNotFoundError('Set CJK_FONT to a Chinese font .ttf/.ttc file')

def overlay(t, path):
    from PIL import Image, ImageDraw
    im = Image.new('RGBA', (W, H)); d = ImageDraw.Draw(im)
    def center(text, y, size, color=(247, 210, 119, 255)):
        f = font(size); box = d.textbbox((0, 0), text, font=f); x = (W - (box[2] - box[0])) / 2
        d.text((x, y), text, font=f, fill=color, stroke_width=2, stroke_fill=(16, 12, 8, 230))
    for y in range(H - 115, H): d.line((0, y, W, y), fill=(5, 8, 14, int(155 * (y - H + 115) / 115)))
    d.text((W - 225, 24), 'AI 生成 · 仅供娱乐', font=font(18, False), fill=(230, 218, 187, 210), stroke_width=1, stroke_fill=(0, 0, 0, 200))
    if t['lyric']: center(t['lyric'], H - 76, 36)
    if t['name_card']:
        n = t['name_card']; d.rounded_rectangle((32, 28, 175 if n == '周瑜' else 210, 82), radius=5, fill=(10, 10, 12, 135))
        d.text((48, 33), n, font=font(30), fill=(250, 213, 124, 255), stroke_width=1, stroke_fill=(15, 12, 10, 255))
    if t['overlay'] == 'title':
        center('赤壁借风', H - 195, 62); center('周瑜  ×  诸葛亮', H - 110, 26, (242, 231, 209, 255))
    if t['overlay'] == 'end_title':
        center('赤壁借风', H - 165, 48); center('周瑜  ×  诸葛亮', H - 98, 25, (242, 231, 209, 255))
    im.save(path)

def render():
    out_dir = V / 'render'; out_dir.mkdir(exist_ok=True)
    for t in plan['timeline']:
        v = C / t['clip'] / 'video.mp4'; assert v.exists(), f"缺 {t['clip']}/video.mp4"
        assert nframes(v) >= t['in_frame'] + t['frames'], f"{t['clip']} 帧数不足 {t['in_frame']}+{t['frames']}"
        ov = out_dir / (t['cut'] + '_overlay.png'); overlay(t, ov); out = out_dir / (t['cut'] + '.mp4')
        filt = f"[0:v]trim=start_frame={t['in_frame']}:end_frame={t['in_frame'] + t['frames']},setpts=PTS-STARTPTS,scale={W}:{H},setsar=1[base];[base][1:v]overlay=0:0:shortest=1"
        if t['overlay'] == 'end_title': filt += f",fade=t=out:st={t['frames'] / FPS - .5}:d=0.5"
        filt += ',format=yuv420p[v]'
        ff(['-i', v, '-loop', '1', '-i', ov, '-filter_complex', filt, '-map', '[v]', '-an', '-frames:v', t['frames'], '-r', FPS,
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', out])
        print('CUT', t['cut'], t['clip'], f"{t['timeline_start_frame'] / FPS:.2f}s +{t['frames'] / FPS:.2f}s", flush=True)
    (out_dir / 'concat.txt').write_text('\n'.join(f"file '{t['cut']}.mp4'" for t in plan['timeline']), encoding='utf-8')
    final = P / '赤壁借风-周瑜对诸葛亮-成片-v3.mp4'; total = sum(t['frames'] for t in plan['timeline'])
    ff(['-f', 'concat', '-safe', '0', '-i', out_dir / 'concat.txt', '-i', P / 'song.wav', '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy',
        '-af', 'apad', '-t', total / FPS, '-c:a', 'aac', '-b:a', '320k', '-movflags', '+faststart', final])
    # 审片用：每 1/3 秒一帧带时间码的总览
    ff(['-i', final, '-vf', "fps=1,scale=380:-1,tile=6x8", '-frames:v', '1', V / '成片总览-v3.jpg'])
    print('FINAL', final, 'frames', total, flush=True)

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'check'
    args = [a for a in sys.argv[2:] if not a.startswith('--')]
    if cmd == 'check': check()
    elif cmd == 'prepare': prepare(args)
    elif cmd == 'run': run(args, '--retake' in sys.argv)
    elif cmd == 'render': render()
    else: print(__doc__)
