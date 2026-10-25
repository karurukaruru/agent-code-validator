"""Encode verified live browser captures with local English narration/subtitles."""
import hashlib
import json
import re
import subprocess
import math
import wave
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dist/live-video'
FFMPEG=ROOT/'.video-deps/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def stamp(seconds):
    ms=round(seconds*1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
def main():
    manifest=json.loads((OUT/'capture.json').read_text(encoding='utf-8'))
    if manifest['status']!='CAPTURED' or manifest['report']['status']!='PASS' or not manifest['live_inference']:
        raise ValueError('Expected a verified live capture, not a static or mocked report')
    duration=manifest['duration_seconds']
    if not 0<duration<180: raise ValueError('Video must be under three minutes')
    for frame in manifest['captures']:
        if sha(OUT/'frames'/frame['name'])!=frame['sha256']: raise ValueError('Capture hash mismatch')
    # Remove only idle opening footage; preserve the entire live execution.
    narration=json.loads((ROOT/'scripts/live_video_narration.json').read_text(encoding='utf-8'))
    with wave.open(str(OUT/'intro.wav')) as audio:
        opening_voice=audio.getnframes()/audio.getframerate()
    old_opening=manifest['scenes'][0]['seconds']
    new_opening=min(old_opening,math.ceil(opening_voice+0.25))
    trim=old_opening-new_opening
    manifest['scenes'][0].update(text=narration[0]['text'],zh=narration[0]['zh'],voice_seconds=opening_voice,seconds=new_opening)
    for scene in manifest['scenes'][1:]: scene['start']-=trim
    duration-=trim
    english=[];chinese=[];count=0
    for scene in manifest['scenes']:
        words=scene['text'].split();chunks=[];chunk=[]
        for word in words:
            if len(' '.join(chunk+[word]))>115:
                chunks.append(' '.join(chunk));chunk=[]
            chunk.append(word)
        if chunk: chunks.append(' '.join(chunk))
        time=scene['start']
        for chunk in chunks:
            end=time+scene['voice_seconds']*len(chunk.split())/len(words)
            count+=1;english.append(f'{count}\n{stamp(time)} --> {stamp(end)}\n{chunk}\n');time=end
        chinese.append(f"{len(chinese)+1}\n{stamp(scene['start'])} --> {stamp(scene['start']+scene['seconds'])}\n{scene['zh']}\n")
    (OUT/'patchcourt-live.en.srt').write_text('\n'.join(english),encoding='utf-8')
    (OUT/'patchcourt-live.zh.srt').write_text('\n'.join(chinese),encoding='utf-8')
    command=[str(FFMPEG),'-hide_banner','-y','-framerate','8','-i','frames/frame-%05d.jpg']
    for scene in manifest['scenes']: command+=['-i',scene['scene']+'.wav']
    filters=[]
    for i,scene in enumerate(manifest['scenes'],1):
        filters.append(f'[{i}:a]adelay={round(scene["start"]*1000)}:all=1[a{i}]')
    filters.append(''.join(f'[a{i}]' for i in range(1,len(manifest['scenes'])+1))+f'amix=inputs={len(manifest["scenes"])}:normalize=0[audio]')
    opening_edit=f"select='not(between(n,{new_opening*8},{old_opening*8-1}))',setpts=N/(8*TB)," if trim else ''
    filters.append("[0:v]"+opening_edit+"pad=1600:900:0:0:color=0x142622,subtitles=patchcourt-live.en.srt:force_style='FontName=Arial,FontSize=10,PrimaryColour=&HFFFFFF,Outline=0,MarginV=10',fps=30[video]")
    movie=OUT/'patchcourt-glm-live-demo.mp4'
    command+=['-filter_complex',';'.join(filters),'-map','[video]','-map','[audio]','-t',str(duration),'-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart',movie.name]
    result=subprocess.run(command,cwd=OUT,capture_output=True,text=True,check=True)
    (OUT/'encode.log').write_text(result.stderr,encoding='utf-8')
    decoded=subprocess.run([str(FFMPEG),'-hide_banner','-i',str(movie),'-f','null','-'],capture_output=True,text=True,check=True)
    (OUT/'decode.log').write_text(decoded.stderr,encoding='utf-8')
    if '1600x900' not in decoded.stderr or 'Audio:' not in decoded.stderr: raise ValueError('Video or audio stream missing')
    evidence=ROOT/'evidence/live-video';evidence.mkdir(parents=True,exist_ok=True)
    for scene in manifest['scenes']:
        subprocess.run([str(FFMPEG),'-hide_banner','-loglevel','error','-y','-ss',str(scene['start']+2),'-i',str(movie),'-frames:v','1',str(evidence/(scene['scene']+'.png'))],check=True)
    result={'status':'ENCODED_AND_DECODED','visual_review':'PENDING','live_inference':True,'model':'glm-5.3-flash','duration_seconds':duration,'idle_opening_seconds_removed':trim,'source_capture_manifest_sha256':sha(OUT/'capture.json'),'audio':'Local Microsoft Zira synthesized English narration','sha256':sha(movie),'bytes':movie.stat().st_size,'report_created_at':manifest['report']['created_at']}
    (evidence/'video-manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
if __name__=='__main__': main()
