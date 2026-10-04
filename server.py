import os
import pathlib
import shlex
import subprocess
import tempfile

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="My Coding Studio Runner")

MAX_SIZE = 2_000_000


def safe_path(p):
    return (
        bool(p)
        and not p.startswith("/")
        and ".." not in pathlib.PurePosixPath(p).parts
    )


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

        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    return temp, root


def run_command(cmd, cwd, timeout=45):
    p = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout
    )

    output = (p.stdout or "") + (p.stderr or "")
    return p.returncode, output


def language_command(current):
    q = shlex.quote(current)

    if current.endswith(".c"):
        return ["bash", "-lc", f"gcc {q} -O2 -o /tmp/mcs.out && /tmp/mcs.out"]

    if current.endswith(".cc") or current.endswith(".cpp"):
        return ["bash", "-lc", f"g++ {q} -O2 -std=c++17 -o /tmp/mcs.out && /tmp/mcs.out"]

    if current.endswith(".rs"):
        return ["bash", "-lc", f"rustc {q} -o /tmp/mcs.out && /tmp/mcs.out"]

    if current.endswith(".java"):
        parent = shlex.quote(str(pathlib.Path(current).parent or pathlib.Path(".")))
        cls = pathlib.Path(current).stem
        return ["bash", "-lc", f"javac {q} && java -cp {parent} {shlex.quote(cls)}"]

    if current.endswith(".js"):
        return ["node", current]

    if current.endswith(".py"):
        return ["python3", current]

    return None


@app.get("/")
async def home():
    return {
        "ok": True,
        "service": "My Coding Studio Runner",
        "status": "ready"
    }


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/")
async def api(request: Request):
    try:
        x = await request.json()
        action = x.get("action", "run")
        files = x.get("files") or {}
        current = x.get("current") or ""

        temp, root = make_project(files)

        try:
            if action == "run":
                cmd = language_command(current)

                if not cmd:
                    return JSONResponse(
                        {"error": "Unsupported file type"},
                        status_code=400
                    )

                rc, output = run_command(cmd, root)

                return JSONResponse(
                    {
                        "output": output,
                        "exit_code": rc
                    },
                    status_code=200 if rc == 0 else 400
                )

            if action == "command":
                allowed = {
                    "python3 --version",
                    "node --version",
                    "gcc --version",
                    "g++ --version",
                    "java -version",
                    "rustc --version",
                    "cargo --version",
                    "git --version"
                }

                command = (x.get("command") or "").strip()

                if command not in allowed:
                    return JSONResponse(
                        {"error": "Command not allowed by runner policy"},
                        status_code=403
                    )

                rc, output = run_command(
                    ["bash", "-lc", command],
                    root
                )

                return JSONResponse(
                    {
                        "output": output,
                        "exit_code": rc
                    },
                    status_code=200 if rc == 0 else 400
                )

            return JSONResponse(
                {"error": "Unknown action"},
                status_code=400
            )

        finally:
            temp.cleanup()

    except subprocess.TimeoutExpired:
        return JSONResponse(
            {"error": "Execution timed out"},
            status_code=408
        )

    except Exception as e:
        return JSONResponse(
            {"error": str(e)},
            status_code=400
         )
