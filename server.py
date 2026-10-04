from flask import Flask,request,jsonify
import os,subprocess,tempfile,pathlib,shlex
app=Flask(__name__)
MAX=2_000_000

def safe(p): return p and not p.startswith('/') and '..' not in pathlib.PurePosixPath(p).parts

def work(files):
 d=tempfile.TemporaryDirectory(); root=pathlib.Path(d.name)
 total=0
 for n,v in (files or {}).items():
  if not safe(n): continue
  b=str(v); total+=len(b.encode())
  if total>MAX: raise ValueError('Project too large')
  q=root/n; q.parent.mkdir(parents=True,exist_ok=True); q.write_text(b)
 return d,root

def run(cmd,cwd,timeout=45):
 p=subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,timeout=timeout)
 return p.returncode,(p.stdout or '')+(p.stderr or '')

def langcmd(cur):
 q=shlex.quote(cur)
 if cur.endswith('.c'): return ['bash','-lc',f'gcc {q} -O2 -o /tmp/mcs.out && /tmp/mcs.out']
 if cur.endswith(('.cc','.cpp','.cxx')): return ['bash','-lc',f'g++ {q} -O2 -std=c++17 -o /tmp/mcs.out && /tmp/mcs.out']
 if cur.endswith('.rs'): return ['bash','-lc',f'rustc {q} -O -o /tmp/mcs.out && /tmp/mcs.out']
 if cur.endswith('.java'):
  cls=pathlib.Path(cur).stem; return ['bash','-lc',f'javac {q} && java -cp {shlex.quote(str(pathlib.Path(cur).parent or pathlib.Path(".")))} {shlex.quote(cls)}']
 if cur.endswith('.kt'): return ['bash','-lc',f'kotlinc {q} -include-runtime -d /tmp/mcs.jar && java -jar /tmp/mcs.jar']
 if cur.endswith('.js'): return ['node',cur]
 if cur.endswith('.py'): return ['python3',cur]
 return None

@app.post('/')
def api():
 x=request.get_json(force=True,silent=True) or {}; action=x.get('action','run'); files=x.get('files') or {}; cur=x.get('current') or ''
 try:
  td,root=work(files)
  with td:
   if action=='run':
    cmd=langcmd(cur)
    if not cmd:return jsonify(error='Unsupported file type'),400
    rc,o=run(cmd,root); return jsonify(output=o,exit_code=rc), (200 if rc==0 else 400)
   if action=='command':
    # local/private runner only: arbitrary shell is intentionally disabled by default
    allowed={'python3 --version','node --version','gcc --version','g++ --version','java -version','rustc --version','cargo --version','git --version','kotlinc -version'}
    c=(x.get('command') or '').strip()
    if c not in allowed:return jsonify(error='Command not allowed by runner policy'),403
    rc,o=run(['bash','-lc',c],root);return jsonify(output=o,exit_code=rc),(200 if rc==0 else 400)
   if action=='git':
    args=shlex.split(x.get('command') or '')
    if not args or args[0] not in {'status','init','add','log','diff','branch'}:return jsonify(error='Git command not allowed by runner policy'),403
    rc,o=run(['git']+args,root);return jsonify(output=o,exit_code=rc),(200 if rc==0 else 400)
   if action=='android-build':
    if not (root/'gradlew').exists():return jsonify(error='gradlew not found in project'),400
    os.chmod(root/'gradlew',0o755);rc,o=run(['./gradlew','assembleDebug'],root,300);return jsonify(output=o,exit_code=rc),(200 if rc==0 else 400)
   return jsonify(error='Unknown action'),400
 except subprocess.TimeoutExpired:return jsonify(error='Execution timed out'),408
 except Exception as e:return jsonify(error=str(e)),400

@app.get('/health')
def health(): return jsonify(ok=True)
app.run(host='0.0.0.0',port=int(os.environ.get('PORT','8080')))
