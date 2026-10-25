"""Package tracked source, verified history and selected media, never local secrets.

Run after committing the handoff. Supply known credentials through environment
variables for value scanning; this script never prints their values.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--mission-file', required=True)
    parser.add_argument('--context-root', required=True)
    args = parser.parse_args()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    archive = out / 'PatchCourt-Handoff-0.3.2-20261025.zip'
    if archive.exists():
        raise ValueError('Preserve prior handoff; use a new output directory')
    def git(*argv):
        return subprocess.check_output(['git', *argv], cwd=ROOT)
    if git('status', '--porcelain').strip():
        raise ValueError('Commit tracked/untracked work before packaging')
    head = git('rev-parse', 'HEAD').decode().strip()
    branch = git('branch', '--show-current').decode().strip()
    secrets = [v.encode() for k, v in os.environ.items() if any(s in k.upper() for s in ('API_KEY', 'SECRET', 'PASSWORD', 'ACCESS_TOKEN')) and len(v) > 12]
    def scan(data, name):
        if any(value in data for value in secrets):
            raise ValueError('Configured credential found in ' + name + '; value suppressed')
        if re.search(rb'\b(?:sk-proj-|tvly-)[A-Za-z0-9_-]{20,}', data) or re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', data):
            raise ValueError('Credential-shaped content in ' + name + '; value suppressed')
    # Check decompressed Git blobs, not only compressed bundle bytes.
    objects = git('rev-list', '--objects', '--all').decode().splitlines()
    history = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    blobs = 0
    for item in objects:
        oid = item.split(' ', 1)[0]
        history.stdin.write((oid+'\n').encode()); history.stdin.flush()
        header = history.stdout.readline().decode().split()
        data = history.stdout.read(int(header[2])); history.stdout.read(1)
        if header[1] == 'blob':
            scan(data, 'history/'+oid); blobs += 1
    history.stdin.close()
    if history.wait() != 0:
        raise ValueError('Git history scan failed')
    bundle = out / 'repository.bundle'
    subprocess.run(['git', 'bundle', 'create', str(bundle), '--all'], cwd=ROOT, check=True)
    subprocess.run(['git', 'bundle', 'verify', str(bundle)], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    entries = {}
    def add(path, name):
        path = Path(path)
        if path.is_symlink() or not path.is_file() or '..' in PurePosixPath(name).parts:
            raise ValueError('Unsafe or missing package input: ' + name)
        if name in entries:
            raise ValueError('Duplicate package input: ' + name)
        entries[name] = path
    for name in git('ls-files', '-z').decode().split('\0'):
        if name:
            add(ROOT/name, 'project/'+name)
    add(bundle, 'repository.bundle')
    add(args.mission_file, 'context/ORIGINAL_MISSION.txt')
    context = Path(args.context_root)
    for source, target in [('import/agent-code-validator-main','original-acv'), ('import/agent-software-map-main','original-asm'), ('audit','initial-audit')]:
        base = context/source
        for path in sorted(base.rglob('*')):
            if path.is_file():
                if any(part in {'.git','.venv','__pycache__','.env','node_modules'} for part in path.relative_to(base).parts):
                    continue
                add(path, 'context/'+target+'/'+path.relative_to(base).as_posix())
    media = ROOT/'dist/live-video'
    capture = json.loads((media/'capture.json').read_text(encoding='utf-8'))
    for frame in capture['captures']:
        path = media/'frames'/frame['name']
        if hashlib.sha256(path.read_bytes()).hexdigest() != frame['sha256']:
            raise ValueError('Original capture differs: '+frame['name'])
        add(path, 'media/live-video/frames/'+frame['name'])
    for path in sorted(media.iterdir()):
        if path.is_file() and path.suffix in {'.json','.wav','.mp4','.srt','.log'}:
            add(path, 'media/live-video/'+path.name)
    # Browser profiles/cookies and machine-bound environments are excluded.
    instructions = '''# PatchCourt 完整开发交接包

1. 解压后先读 project/HANDOFF_ZH.md 和 project/FINISH_PLAN_ZH.md，再把 project/NEXT_AGENT_PROMPT.md 发给新 Agent。后者会要求持续推进到逐项验收，而不是只写计划。
2. project/ 是最新源码；repository.bundle 是完整 Git 历史；context/ 包含原任务、原始 ACV/ASM 快照和初审；media/ 是演示原始帧、配音和成片。
3. 推荐恢复 Git：git clone repository.bundle work --branch patchcourt/award-build-20261024
4. 修改远端：git -C work remote set-url origin https://github.com/karurukaruru/agent-code-validator.git
5. 进入 work（或 project），使用 Python 3.10+：python -m venv .venv，然后用该虚拟环境的 Python 执行 pip install -e . pytest==8.4.2。
6. python -m pytest -ra；python -m patchcourt demo --output outputs/check。不需 API 即可验证。
7. 要重剪视频，将 media/live-video/ 复制到 work/dist/live-video/；录制脚本的 Chrome/ffmpeg 路径需要匹配新电脑。

密钥、私人凭证文件、浏览器配置/会话、旧机器虚拟环境和依赖缓存不包含在包内。真实 API 需要重新安全配置；用户仅授权 glm-5.3-flash，禁止恢复 NVIDIA 调用或替换成 FlashX。完整约束和未完成项见交接文档。

0.3.2 是本地交接修订，尚未推送。0.3.1 的历史 CI 不能当作此版 CI。不要丢弃本地领先提交。
MANIFEST.json 含每个文件 SHA-256；外部 .sha256 文件校验整个 ZIP。校验和证明传输完整性，不证明竞赛资格或研究结论。
'''
    records = []
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        for name, path in sorted(entries.items()):
            data = path.read_bytes(); scan(data, name)
            if path.suffix in {'.whl','.zip'}:
                with zipfile.ZipFile(path) as embedded:
                    for inner in embedded.namelist():
                        scan(embedded.read(inner), name+'!'+inner)
            records.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
            z.writestr(name, data, compress_type=zipfile.ZIP_STORED if path.suffix.lower() in {'.jpg','.png','.mp4','.whl','.zip','.bundle'} else zipfile.ZIP_DEFLATED)
        start = instructions.encode()
        z.writestr('START_HERE_中文.md', start)
        records.append({'path':'START_HERE_中文.md','bytes':len(start),'sha256':hashlib.sha256(start).hexdigest()})
        manifest = {'version':'0.3.2','head':head,'branch':branch,'files':records,'git_history_blobs_scanned':blobs,'known_credential_values_scanned':len(secrets),'secrets_included':False,'packaging_network_calls':0,'excluded':['credentials','.env','private launchers','browser profiles/cookies','virtual environments','dependency caches'],'note':'MANIFEST.json does not hash itself; verify whole archive using the adjacent SHA256 file. Development API usage is recorded separately in project/HANDOFF_ZH.md.'}
        z.writestr('MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode())
    with zipfile.ZipFile(archive) as z:
        for entry in records:
            if hashlib.sha256(z.read(entry['path'])).hexdigest() != entry['sha256']:
                raise ValueError('Archive verification failed: '+entry['path'])
        if z.testzip() is not None:
            raise ValueError('Archive CRC check failed')
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (out/(archive.name+'.sha256')).write_text(checksum+'  '+archive.name+'\n',encoding='ascii')
    result = {'status':'PASS','archive':str(archive),'bytes':archive.stat().st_size,'files':len(records)+1,'head':head,'sha256':checksum,'git_history_blobs_scanned':blobs,'original_video_frames':len(capture['captures']),'all_member_hashes_verified':True,'credential_scan':'PASS','browser_profiles_included':False}
    (out/'PACKAGE_VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (out/'START_HERE_中文.md').write_text(instructions,encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__ == '__main__':
    main()
