import os, pathlib, shlex, subprocess, tempfile
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app=FastAPI(title='My Coding Studio Runner')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_credentials=False,allow_methods=['*'],allow_headers=['*'])
MAX=2_000_000

def safe(p): return bool(p) and not p.startswith('/') and '..' not in pathlib.PurePosixPath(p).parts

def work(files):
 d=tempfile.TemporaryDirectory(); root=pathlib.Path(d.name); total=0
 for n,v in (files or {}).items():
  if not safe(n): continue
  b=str(v).encode(); total+=len(b)
  if total>MAX: d.cleanup(); raise ValueError('Project too large')
  q=root/n; q.parent.mkdir(parents=True,exist_ok=True); q.write_bytes(b)
 return d,root

def run(cmd,cwd,timeout=60):
 p=subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,timeout=timeout)
 return p.returncode,(p.stdout or '')+(p.stderr or '')

def langcmd(cur):
 q=shlex.quote(cur)
 if cur.endswith('.c'): return ['bash','-lc',f'gcc {q} -O2 -o ./mcs.out && ./mcs.out']
 if cur.endswith(('.cc','.cpp','.cxx')): return ['bash','-lc',f'g++ {q} -O2 -std=c++17 -o ./mcs.out && ./mcs.out']
 if cur.endswith('.rs'): return ['bash','-lc',f'rustc {q} -O -o ./mcs.out && ./mcs.out']
 if cur.endswith('.java'):
  cls=pathlib.Path(cur).stem; parent=shlex.quote(str(pathlib.Path(cur).parent or pathlib.Path('.')))
  return ['bash','-lc',f'javac {q} && java -cp {parent} {shlex.quote(cls)}']
 if cur.endswith('.kt'): return ['bash','-lc',f'kotlinc {q} -include-runtime -d ./mcs.jar && java -jar ./mcs.jar']
 if cur.endswith('.js'): return ['node',cur]
 if cur.endswith('.py'): return ['python3',cur]
 return None

@app.get('/')
async def home(): return {'ok':True,'service':'My Coding Studio Runner','status':'ready'}
@app.get('/health')
async def health(): return {'ok':True}

@app.post('/')
async def api(request:Request):
 try:
  x=await request.json(); action=x.get('action','run'); files=x.get('files') or {}; cur=x.get('current') or ''
  td,root=work(files)
  try:
   if action=='run':
    cmd=langcmd(cur)
    if not cmd:return JSONResponse({'error':'Unsupported file type'},400)
    rc,o=run(cmd,root);return JSONResponse({'output':o,'exit_code':rc},200 if rc==0 else 400)
   if action=='command':
    allowed={'python3 --version','node --version','gcc --version','g++ --version','java -version','rustc --version','cargo --version','git --version','kotlinc -version'}
    c=(x.get('command') or '').strip()
    if c not in allowed:return JSONResponse({'error':'Command not allowed by runner policy'},403)
    rc,o=run(['bash','-lc',c],root);return JSONResponse({'output':o,'exit_code':rc},200 if rc==0 else 400)
   if action=='git':
    args=shlex.split(x.get('command') or '')
    if not args or args[0] not in {'status','init','add','log','diff','branch'}:return JSONResponse({'error':'Git command not allowed by runner policy'},403)
    rc,o=run(['git']+args,root);return JSONResponse({'output':o,'exit_code':rc},200 if rc==0 else 400)
   if action=='android-build':
    if not (root/'gradlew').exists():return JSONResponse({'error':'gradlew not found in project'},400)
    os.chmod(root/'gradlew',0o755);rc,o=run(['./gradlew','assembleDebug'],root,300);return JSONResponse({'output':o,'exit_code':rc},200 if rc==0 else 400)
   return JSONResponse({'error':'Unknown action'},400)
  finally: td.cleanup()
 except subprocess.TimeoutExpired:return JSONResponse({'error':'Execution timed out'},408)
 except Exception as e:return JSONResponse({'error':str(e)},400)
