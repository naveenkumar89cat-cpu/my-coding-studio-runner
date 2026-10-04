import os
import pathlib
import shlex
import subprocess
import tempfile

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="My Coding Studio Runner")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://hidden-frog-951e.naveenkumar89cat.workers.dev"
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

MAX_SIZE = 2_000_000

RUN_ENV = os.environ.copy()
RUN_ENV["PATH"] = (
    "/opt/kotlin/bin:"
    "/opt/kotlinc/bin:"
    + RUN_ENV.get("PATH", "")
)


def safe_path(path):
    return (
        bool(path)
        and not path.startswith("/")
        and ".." not in pathlib.PurePosixPath(path).parts
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

        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    return temp, root


def run_command(cmd, cwd, timeout=60):
    process = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=RUN_ENV,
    )

    output = (process.stdout or "") + (process.stderr or "")
    return process.returncode, output


def language_command(current):
    q = shlex.quote(current)

    if current.endswith(".c"):
        return [
            "bash", "-lc",
            f"gcc {q} -O2 -o ./mcs.out && ./mcs.out"
        ]

    if current.endswith((".cc", ".cpp", ".cxx")):
        return [
            "bash", "-lc",
            f"g++ {q} -O2 -std=c++17 -o ./mcs.out && ./mcs.out"
        ]

    if current.endswith(".rs"):
        return [
            "bash", "-lc",
            f"rustc {q} -O -o ./mcs.out && ./mcs.out"
        ]

    if current.endswith(".java"):
        cls = pathlib.Path(current).stem
        parent = shlex.quote(
            str(pathlib.Path(current).parent or pathlib.Path("."))
        )
        return [
            "bash", "-lc",
            f"javac {q} && java -cp {parent} {shlex.quote(cls)}"
        ]

    if current.endswith(".kt"):
        return [
            "bash", "-lc",
            f"/opt/kotlin/bin/kotlinc {q} "
            "-include-runtime -d ./mcs.jar && "
            "java -jar ./mcs.jar"
        ]

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
        "status": "ready",
    }


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/")
async def api(request: Request):
    try:
        data = await request.json()

        action = data.get("action", "run")
        files = data.get("files") or {}
        current = data.get("current") or ""

        temp, root = make_project(files)

        try:
            if action == "run":
                cmd = language_command(current)

                if not cmd:
                    return JSONResponse(
                        {"error": "Unsupported file type"},
                        status_code=400,
                    )

                rc, output = run_command(cmd, root)

                return JSONResponse(
                    {
                        "output": output,
                        "exit_code": rc,
                    },
                    status_code=200 if rc == 0 else 400,
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
                    "git --version",
                    "kotlinc -version",
                }

                command = (data.get("command") or "").strip()

                if command not in allowed:
                    return JSONResponse(
                        {
                            "error":
                            "Command not allowed by runner policy"
                        },
                        status_code=403,
                    )

                if command == "kotlinc -version":
                    cmd = [
                        "/opt/kotlin/bin/kotlinc",
                        "-version",
                    ]
                else:
                    cmd = ["bash", "-lc", command]

                rc, output = run_command(cmd, root)

                return JSONResponse(
                    {
                        "output": output,
                        "exit_code": rc,
                    },
                    status_code=200 if rc == 0 else 400,
                )

            if action == "git":
                args = shlex.split(
                    data.get("command") or ""
                )

                allowed_git = {
                    "status",
                    "init",
                    "add",
                    "log",
                    "diff",
                    "branch",
                }

                if not args or args[0] not in allowed_git:
                    return JSONResponse(
                        {
                            "error":
                            "Git command not allowed by runner policy"
                        },
                        status_code=403,
                    )

                rc, output = run_command(
                    ["git"] + args,
                    root,
                )

                return JSONResponse(
                    {
                        "output": output,
                        "exit_code": rc,
                    },
                    status_code=200 if rc == 0 else 400,
                )

            if action == "android-build":
                gradlew = root / "gradlew"

                if not gradlew.exists():
                    return JSONResponse(
                        {
                            "error":
                            "gradlew not found in project"
                        },
                        status_code=400,
                    )

                os.chmod(gradlew, 0o755)

                rc, output = run_command(
                    ["./gradlew", "assembleDebug"],
                    root,
                    timeout=300,
                )

                return JSONResponse(
                    {
                        "output": output,
                        "exit_code": rc,
                    },
                    status_code=200 if rc == 0 else 400,
                )

            return JSONResponse(
                {"error": "Unknown action"},
                status_code=400,
            )

        finally:
            temp.cleanup()

    except subprocess.TimeoutExpired:
        return JSONResponse(
            {"error": "Execution timed out"},
            status_code=408,
        )

    except Exception as error:
        return JSONResponse(
            {"error": str(error)},
            status_code=400,
        )
