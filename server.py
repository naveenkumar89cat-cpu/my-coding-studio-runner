import json
import os
import pathlib
import shlex
import subprocess
import tempfile
import urllib.error
import urllib.request

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="My Coding Studio Runner")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://hidden-frog-951e.naveenkumar89cat.workers.dev"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

MAX_SIZE = 2_000_000
RUN_ENV = os.environ.copy()
RUN_ENV["PATH"] = "/opt/kotlin/bin:/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:/opt/android-sdk/build-tools/35.0.0:" + RUN_ENV.get("PATH", "")


def safe_path(p):
    return bool(p) and not p.startswith("/") and ".." not in pathlib.PurePosixPath(p).parts


def make_project(files):
    temp = tempfile.TemporaryDirectory()
    root = pathlib.Path(temp.name)
    total = 0
    for name, content in (files or {}).items():
        if not safe_path(name):
            continue
        data = str(content).encode()
        total += len(data)
        if total > MAX_SIZE:
            temp.cleanup()
            raise ValueError("Project too large")
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return temp, root


def run_command(cmd, cwd, timeout=60):
    p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout, env=RUN_ENV)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def language_command(current):
    q = shlex.quote(current)
    if current.endswith(".c"):
        return ["bash", "-lc", f"gcc {q} -O2 -o ./mcs.out && ./mcs.out"]
    if current.endswith((".cc", ".cpp", ".cxx")):
        return ["bash", "-lc", f"g++ {q} -O2 -std=c++17 -o ./mcs.out && ./mcs.out"]
    if current.endswith(".rs"):
        return ["bash", "-lc", f"rustc {q} -O -o ./mcs.out && ./mcs.out"]
    if current.endswith(".java"):
        cls = pathlib.Path(current).stem
        parent = shlex.quote(str(pathlib.Path(current).parent or pathlib.Path(".")))
        return ["bash", "-lc", f"javac {q} && java -cp {parent} {shlex.quote(cls)}"]
    if current.endswith(".kt"):
        return ["bash", "-lc", f"kotlinc {q} -include-runtime -d ./mcs.jar && java -jar ./mcs.jar"]
    if current.endswith(".js"):
        return ["node", current]
    if current.endswith(".py"):
        return ["python3", current]
    return None


def ai_request(prompt, files, current):
    api_url = os.environ.get("AI_API_URL", "").strip()
    api_key = os.environ.get("AI_API_KEY", "").strip()
    model = os.environ.get("AI_MODEL", "").strip()
    if not api_url or not api_key:
        raise ValueError("AI_API_URL / AI_API_KEY not configured on Render")

    system = (
        "You are the coding agent for My Coding Studio. Return ONLY valid JSON with keys "
        "message (string) and files (object mapping relative paths to complete file contents). "
        "Never use absolute paths or .. paths. Preserve files that do not need changes."
    )
    payload = {
        "model": model or "gpt-4.1-mini",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps({"prompt": prompt, "current": current, "files": files})},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:1500]
        raise ValueError(f"AI provider error {e.code}: {detail}")
    content = raw["choices"][0]["message"]["content"]
    result = json.loads(content)
    clean = {}
    for name, value in (result.get("files") or {}).items():
        if safe_path(name):
            clean[name] = str(value)
    return {"message": str(result.get("message") or "AI changes applied"), "files": clean}


@app.get("/")
async def home():
    return {"ok": True, "service": "My Coding Studio Runner", "status": "ready"}


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/ai")
async def ai(request: Request):
    try:
        x = await request.json()
        return JSONResponse(ai_request(x.get("prompt") or "", x.get("files") or {}, x.get("current") or ""))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/")
async def api(request: Request):
    try:
        x = await request.json()
        action = x.get("action", "run")
        files = x.get("files") or {}
        current = x.get("current") or ""
        td, root = make_project(files)
        try:
            if action == "run":
                cmd = language_command(current)
                if not cmd:
                    return JSONResponse({"error": "Unsupported file type"}, status_code=400)
                rc, output = run_command(cmd, root)
                return JSONResponse({"output": output, "exit_code": rc}, status_code=200 if rc == 0 else 400)

            if action == "command":
                allowed = {
                    "python3 --version", "node --version", "gcc --version", "g++ --version",
                    "java -version", "javac -version", "kotlinc -version", "rustc --version",
                    "cargo --version", "git --version", "sdkmanager --version", "adb --version",
                }
                command = (x.get("command") or "").strip()
                if command not in allowed:
                    return JSONResponse({"error": "Command not allowed by runner policy"}, status_code=403)
                rc, output = run_command(["bash", "-lc", command], root)
                return JSONResponse({"output": output, "exit_code": rc}, status_code=200 if rc == 0 else 400)

            if action == "git":
                args = shlex.split(x.get("command") or "")
                if not args or args[0] not in {"status", "init", "add", "log", "diff", "branch"}:
                    return JSONResponse({"error": "Git command not allowed by runner policy"}, status_code=403)
                rc, output = run_command(["git"] + args, root)
                return JSONResponse({"output": output, "exit_code": rc}, status_code=200 if rc == 0 else 400)

            if action == "android-build":
                gradlew = root / "gradlew"
                if not gradlew.exists():
                    return JSONResponse({"error": "gradlew not found in project"}, status_code=400)
                os.chmod(gradlew, 0o755)
                rc, output = run_command(["./gradlew", "assembleDebug", "--no-daemon"], root, timeout=600)
                apks = [str(p.relative_to(root)) for p in root.rglob("*.apk")]
                return JSONResponse({"output": output, "exit_code": rc, "apks": apks}, status_code=200 if rc == 0 else 400)

            return JSONResponse({"error": "Unknown action"}, status_code=400)
        finally:
            td.cleanup()
    except subprocess.TimeoutExpired:
        return JSONResponse({"error": "Execution timed out"}, status_code=408)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
