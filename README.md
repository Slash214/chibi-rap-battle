# 赤壁借风｜周瑜对诸葛亮 · 导演交接包

这是供 Claude 做导演审查和改进的独立项目。当前版本已经有完整视频，但用户评价“效果一般”，尚未通过创作验收。

## 先看这些

1. [当前成片](episodes/suno-chibi/赤壁借风-周瑜对诸葛亮-成片-v2.mp4)
2. [镜头总览](episodes/suno-chibi/mv-v2/成片总览.jpg)
3. [分镜表](episodes/suno-chibi/mv-v2/分镜表.md)、[剪辑单](episodes/suno-chibi/mv-v2/剪辑单.md)
4. [实际时间线](episodes/suno-chibi/mv-v2/plan.json)、[视频提示词](episodes/suno-chibi/mv-v2/视频提示词.md)
5. [原项目分镜模板](reference/shot-template.md)、[踩坑记录](reference/pitfalls.md)
6. [给 Claude 的接手说明](CLAUDE.md)

## 音乐以此为准

唯一指定主音轨是用户从 Suno 下载的 **赤壁借风.m4a**，原文件来自 F:/download/赤壁借风.m4a。
项目内同名文件与用户下载文件按 SHA-256 校验一致，见 provenance.json。
扩展名虽然是 m4a，ffprobe 检测内部音频为 Opus，48 kHz 双声道，约 42.3265 秒。

- 赤壁借风.m4a：保留的原下载文件。
- song.wav：原歌解码得到的完整混音，成片最终挂此音轨，包含人声和伴奏。
- vocals.wav：从同一首 Suno 歌中分离的人声，仅用于驱动口型。
- 不包含、不使用旧 ACE-Step 试听歌曲。
- 未额外变调、加欢呼或替换人声。用户未授权换歌。

## 当前规格

成片 42.333 秒、24 fps、1216×672，13 个剪辑镜头，八句歌词。
实际使用的模型参数见 parameter-audit.json：
- UNet: minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors
- LoRA: minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors，1.0
- LoRA: h3-realism-people-t2v-i2v-r2v.safetensors，1.0
- 8 步；res_multistep / simple；Ref2VA，lock_source。

原生本地 ComfyUI，不依赖 Claude Code 或云端 MiniMax API。模型权重、Python 环境不包含在包内。

## 目录

- episodes/suno-chibi/：原歌曲、完整混音、人声与当前成片。
- episodes/suno-chibi/mv-v2/：参考图、导演资料、字幕、逐镜素材。
- 每个镜头目录：video.mp4、drive.wav、mix.wav、spec.json、request.json；records 是历史任务证据，不用于新机器恢复任务。
- scripts/generate.py：从 plan.json 准备音频并通过本机 ComfyUI 生成；会串行排队并保存任务 ID。
- scripts/render.py：按 plan.json 拼接逐镜素材，叠加字幕、名字卡、片头片尾并挂完整原歌曲。
- workflows/h3-base.api.json：生成器使用的基础 API 图；实际完整请求以各镜头 request.json 为准。
- reference/：原仓库 Skill、分镜规则和 MIT 许可，作为导演参考。

最后一镜采用 END02B。旧 END02 没有实现拉远，未纳入本交接包；不要按旧条目恢复它。
原始提示词文档保留历史说明，当前使用镜序和实际 prompt 以 plan.json 及每镜 spec.json 为准。

## 在本地重剪（无需 GPU）

安装 Python、FFmpeg/ffprobe，并执行：

    python -m pip install -r requirements.txt
    python scripts/render.py

默认从脚本位置寻找项目目录，不依赖 D 盘原路径。
Windows 默认用微软雅黑；其他系统设置 CJK_FONT 为可用中文字体文件路径。
输出覆盖本包中的同名成片，修改前可另存一个版本。已在当前 Windows 环境验证重剪脚本。

## 如果以后确认重新生成

先由导演给出修改方案，得到用户要求开始制作后，再建立新版本目录，保留当前素材。
依赖本机已安装对应 H3 节点、UNet、CLIP、VAE、两个 LoRA。用 COMFYUI_URL 环境变量更改地址，默认 http://127.0.0.1:8188。

    python scripts/generate.py prepare
    python scripts/generate.py run A01

prepare 只按现有 plan.json 重建音频片段；run 才提交视频任务。已有 video.mp4 会跳过。
演唱素材包含 6 帧（0.25 秒）前导静音，渲染时必须按 lead_frames 裁掉，不能原样拼接。
不要把历史 records/task.json 拷回活动 task.json 来恢复另一台机器的任务。

## GitHub 上传

这个目录本身就是仓库根目录，可用 GitHub Desktop 添加为本地仓库后发布，也可用 Git 上传全部文件。
不需要上传同级 ZIP、模型、虚拟环境或缓存。本包没有创建远程仓库，也没有自动发布。
如果 Claude 无法直接播放 GitHub 内的视频，请把成片或对应镜头另行提供给它；仅看提示词和截图不足以审查口型。

## 来源

借鉴 https://github.com/10291124jcjc-dotcom/ancient-rap-battle 的制作流程和分镜规则。
原仓库基线 e5e40fa3612777133a141c8448122dd0fd45e4cc，原代码许可保留于 reference/upstream-LICENSE。
该许可不替代 Suno 音频、生成素材的各自使用条款。

## v3 完整视频

[播放/下载 v3](episodes/suno-chibi/赤壁借风-周瑜对诸葛亮-成片-v3.mp4) · [逐镜检查与已知差异](episodes/suno-chibi/mv-v3/交付验收.md) · [剪辑单](episodes/suno-chibi/mv-v3/剪辑单.md)

42.33 秒，1216×672，24fps，8 步，原 Suno 音轨。技术检查通过；完整口型观感待创作者验收。
