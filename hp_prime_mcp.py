"""hp-prime-mcp: a Model Context Protocol server for the HP Prime graphing calculator.

Lets an AI assistant (Claude Code, Claude Desktop, or any MCP client) see what an HP Prime G2
is showing, send it programs, and read its variables and programs back.

Standard library only. Speaks MCP over stdio (JSON-RPC 2.0, one message per line).

It builds on hp-prime-kit (https://github.com/JordiRigau/hp-prime-kit, MIT) for the USB and
file-format work, and on HP's Connectivity Kit for reading data back. Set HP_PRIME_KIT to the
path of hp-prime-kit's hpprime.py (see README).

It cannot press the calculator's keys or tap its screen: on the firmware it was tested on
(G2, build 15751) remote key presses have no effect.
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import time

VERSION = "0.1.0"
HOME = os.path.expanduser("~")
KIT = os.environ.get("HP_PRIME_KIT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "hp-prime-kit", "hpprime.py"))
CK_DIR = os.environ.get("HP_CK_DIR", os.path.join(HOME, "Documents", "HP Connectivity Kit"))
CK_EXE = os.environ.get("HP_CK_EXE", r"C:\Program Files\HP\HP Connectivity Kit\ConnectivityKit.exe")
VIRTUAL_DIR = os.environ.get("HP_VIRTUAL_DIR", os.path.join(HOME, "Documents", "HP Prime", "Calculators"))
HPDEV = os.environ.get("HPDEV", "")
OUT = os.environ.get("HP_PRIME_MCP_OUT", os.path.join(os.getcwd(), "hp-prime-mcp-out"))
PY = sys.executable


# ------------------------------------------------------------------ helpers

def run(args, timeout=120, cwd=None):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout + p.stderr).strip()


def kit(*args, timeout=120, cwd=None):
    if not os.path.exists(KIT):
        return 1, f"hp-prime-kit not found at {KIT}. Set HP_PRIME_KIT to the path of its hpprime.py."
    return run([PY, KIT, *args], timeout, cwd)


def kit_on(cmd, f, *rest, timeout=120):
    """run an hp-prime-kit command on file f from f's own folder (its linter needs a relative path)"""
    f = os.path.abspath(f)
    return kit(cmd, os.path.basename(f), *rest, timeout=timeout, cwd=os.path.dirname(f))


def ck_running():
    if os.name != "nt":
        return False
    _, out = run(["tasklist", "/FI", "IMAGENAME eq ConnectivityKit.exe", "/NH"], 20)
    return "ConnectivityKit.exe" in out


def ck_stop():
    run(["taskkill", "/IM", "ConnectivityKit.exe", "/F"], 20)
    time.sleep(3)


def ck_start():
    if os.path.exists(CK_EXE):
        subprocess.Popen([CK_EXE])


def text(s):
    return {"content": [{"type": "text", "text": s}]}


def err(s):
    return {"content": [{"type": "text", "text": s}], "isError": True}


def calc_dirs():
    """Folders where the Connectivity Kit mirrors each connected calculator, plus the Virtual Calculator's."""
    out = []
    base = os.path.join(CK_DIR, "Calculators")
    if os.path.isdir(base):
        out += [("kit", d, os.path.join(base, d)) for d in sorted(os.listdir(base))]
    if os.path.isdir(VIRTUAL_DIR):
        out += [("virtual", d, os.path.join(VIRTUAL_DIR, d)) for d in sorted(os.listdir(VIRTUAL_DIR))]
    return [x for x in out if os.path.isdir(x[2])]


def find_calc(name):
    dirs = calc_dirs()
    if not dirs:
        return None, "No calculator data found. Open the Connectivity Kit with the calculator plugged in, so it copies the calculator's files to the PC."
    if not name:
        return max(dirs, key=lambda x: os.path.getmtime(x[2])), ""
    for d in dirs:
        if d[1].lower() == name.lower():
            return d, ""
    return None, "No calculator called '" + name + "'. Known: " + ", ".join(d[1] for d in dirs)


def ensure_out():
    os.makedirs(OUT, exist_ok=True)
    return OUT


# ------------------------------------------------------------------ tools

def t_status(a):
    lines = [f"hp-prime-mcp {VERSION}",
             "hp-prime-kit: " + ("found" if os.path.exists(KIT) else f"NOT found at {KIT}"),
             "Connectivity Kit: " + ("running" if ck_running() else "not running")]
    for kind, name, path in calc_dirs():
        progs = sorted(f[:-7] for f in os.listdir(path) if f.lower().endswith(".hpprgm"))
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))
        lines.append(f"[{kind}] {name}: updated {when}; programs: {', '.join(progs) or '-'}")
    lines.append("Data shown is the copy on the PC: the Connectivity Kit refreshes it while it is open and the calculator is plugged in.")
    return text("\n".join(lines))


def t_screen(a):
    reopen = False
    if ck_running():
        if not a.get("close_kit"):
            return err("The Connectivity Kit is running and holds the USB connection. Call again with close_kit=true "
                       "to close it for the capture (it is reopened afterwards).")
        ck_stop()
        reopen = True
    path = os.path.join(ensure_out(), time.strftime("screen_%Y%m%d_%H%M%S.png"))
    code, out = kit("screen", "-o", path, timeout=30)
    if code != 0:
        time.sleep(2)
        code, out = kit("screen", "-o", path, timeout=30)
    if reopen:
        ck_start()
    if code != 0 or not os.path.exists(path):
        return err("Screen capture failed: " + out[-400:] + "\nIs the calculator switched on and on its USB cable?")
    return {"content": [
        {"type": "image", "data": base64.b64encode(open(path, "rb").read()).decode(), "mimeType": "image/png"},
        {"type": "text", "text": "Saved " + path}]}


def t_lint(a):
    f = a.get("file")
    if not f or not os.path.exists(f):
        return err("file: path to a PPL source (.txt) is required")
    code, out = kit_on("lint", f, timeout=60)
    res = out[-3000:]
    if HPDEV and os.path.exists(HPDEV):
        c2, o2 = run([HPDEV, "check", f], 60)
        res += "\n\nhpdev check:\n" + "\n".join(o2.splitlines()[-30:])
    return text(res)


def t_send(a):
    f = a.get("file")
    if not f or not os.path.exists(f):
        return err("file: path to a PPL source (.txt) or a built .hpprgm is required")
    name = a.get("name") or os.path.splitext(os.path.basename(f))[0]
    if f.lower().endswith(".hpprgm"):
        prg = f
    else:
        code, out = kit_on("lint", f, timeout=60)
        if " 0 error(s)" not in out:
            return err("Not sent: the linter found errors.\n" + out[-2000:])
        prg = os.path.join(ensure_out(), name + ".hpprgm")
        code, out = kit_on("write", f, "-o", os.path.abspath(prg), timeout=60)
        if code != 0:
            return err("Build failed:\n" + out[-800:])
    method = a.get("method", "kit")
    if method == "kit":
        content = os.path.join(CK_DIR, "Content")
        os.makedirs(content, exist_ok=True)
        dst = os.path.join(content, name + ".hpprgm")
        shutil.copy2(prg, dst)
        return text(f"Built {name}.hpprgm and put it in the Connectivity Kit's Content list ({dst}).\n"
                    "To install: in the Connectivity Kit, right-click it under Content and choose Send.")
    if method == "usb":
        reopen = ck_running()
        if reopen:
            ck_stop()
        args = ["send", prg, "--name", name]
        if a.get("any_build", True):
            args.append("--any-build")
        code, out = kit(*args, timeout=120)
        if reopen:
            ck_start()
        if code != 0:
            return err("USB send failed:\n" + out[-800:])
        return text("Sent over USB. The calculator acknowledges nothing: check with prime_screen, or run the program.\n" + out[-500:])
    return err("method must be 'kit' or 'usb'")


def t_list(a):
    c, msg = find_calc(a.get("calculator"))
    if not c:
        return err(msg)
    kind, name, path = c
    groups = {}
    for f in sorted(os.listdir(path)):
        ext = os.path.splitext(f)[1].lower()
        groups.setdefault(ext or "(folder)", []).append(f)
    lines = [f"[{kind}] {name}  ({path}), copy from {time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(path)))}"]
    labels = {".hpprgm": "programs", ".hpmat": "matrices", ".hplist": "lists", ".hpappdir": "apps", ".hpnote": "notes"}
    for ext, files in groups.items():
        lines.append(f"{labels.get(ext, ext)}: " + ", ".join(files))
    return text("\n".join(lines))


def t_read_matrix(a):
    c, msg = find_calc(a.get("calculator"))
    if not c:
        return err(msg)
    m = (a.get("name") or "M1").upper()
    f = os.path.join(c[2], m + ".hpmat")
    if not os.path.exists(f):
        return err(f"{m} not found in {c[2]}")
    code, out = kit("matrix", "read", f, timeout=60)
    return text(out[:30000]) if code == 0 else err(out[-800:])


def t_read_program(a):
    c, msg = find_calc(a.get("calculator"))
    if not c:
        return err(msg)
    n = a.get("name")
    if not n:
        return err("name: the program's name is required")
    f = os.path.join(c[2], n + ".hpprgm")
    if not os.path.exists(f):
        return err(f"{n}.hpprgm not found in {c[2]}")
    out_txt = os.path.join(ensure_out(), n + "_from_calc.txt")
    code, out = kit("read", f, "-o", out_txt, timeout=60)
    if code != 0 or not os.path.exists(out_txt):
        return err(out[-800:])
    body = open(out_txt, encoding="utf-8", errors="replace").read()
    return text(f"Saved {out_txt}\n\n" + body[:30000])


def t_preview(a):
    if not HPDEV or not os.path.exists(HPDEV):
        return err("Set HPDEV to the hpdev executable (github.com/golba98/hp-prime-development-toolkit) to render screens on the PC.")
    f = a.get("file")
    if not f or not os.path.exists(f):
        return err("file: path to a PPL source is required")
    png = os.path.join(ensure_out(), time.strftime("preview_%H%M%S.png"))
    args = [HPDEV, "preview", f, "--angle", a.get("angle", "deg"), "--keys", a.get("keys", "-1"), "--png", png, "-q"]
    if a.get("entry"):
        args[3:3] = ["-e", a["entry"]]
    code, out = run(args, 60)
    if not os.path.exists(png):
        return err(out[-800:])
    return {"content": [
        {"type": "image", "data": base64.b64encode(open(png, "rb").read()).decode(), "mimeType": "image/png"},
        {"type": "text", "text": "Rendered on the PC (not the calculator). Key codes: digits 0-9 = 47,42,43,44,37,38,39,32,33,34; "
                                 "Enter 30; Esc 4; Up 2; Down 12. Touch is not emulated."}]}


TOOLS = [
    ("prime_status", t_status, "Which calculators the PC has data for, their programs, and whether the Connectivity Kit is running.", {}),
    ("prime_screen", t_screen, "Picture of what the HP Prime on the USB cable is showing now. The Connectivity Kit must be closed: "
                               "close_kit=true closes it for the capture and reopens it.", {"close_kit": {"type": "boolean"}}),
    ("prime_lint", t_lint, "Check a PPL source file for errors the Prime's compiler won't explain (hp-prime-kit lint, plus hpdev check if HPDEV is set).",
     {"file": {"type": "string"}}),
    ("prime_send_program", t_send, "Lint, build and install a PPL program. method 'kit' (default) puts it in the Connectivity Kit's send list "
                                   "for a right-click Send; 'usb' sends it straight over the cable, replacing any program of that name without asking.",
     {"file": {"type": "string"}, "name": {"type": "string"}, "method": {"type": "string", "enum": ["kit", "usb"]}}),
    ("prime_list", t_list, "List the programs, matrices, lists, apps and notes the PC holds for a calculator (default: the most recently updated).",
     {"calculator": {"type": "string"}}),
    ("prime_read_matrix", t_read_matrix, "Read a matrix variable (M0..M9) as rows of numbers.",
     {"name": {"type": "string"}, "calculator": {"type": "string"}}),
    ("prime_read_program", t_read_program, "Read a program's source code back off the calculator.",
     {"name": {"type": "string"}, "calculator": {"type": "string"}}),
    ("prime_preview", t_preview, "Run PPL on the PC and render the screen it draws (needs hpdev). entry = function to run, keys = comma-separated key codes.",
     {"file": {"type": "string"}, "entry": {"type": "string"}, "keys": {"type": "string"}, "angle": {"type": "string"}}),
]


# ------------------------------------------------------------------ MCP over stdio

def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main():
    by_name = {n: f for n, f, _, _ in TOOLS}
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        mid, method = req.get("id"), req.get("method")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": (req.get("params") or {}).get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "hp-prime-mcp", "version": VERSION}}})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": [
                {"name": n, "description": d, "inputSchema": {"type": "object", "properties": p}} for n, _, d, p in TOOLS]}})
        elif method == "tools/call":
            p = req.get("params") or {}
            fn = by_name.get(p.get("name"))
            try:
                result = fn(p.get("arguments") or {}) if fn else err("Unknown tool")
            except Exception as e:
                result = err(f"{type(e).__name__}: {e}")
            send({"jsonrpc": "2.0", "id": mid, "result": result})
        elif method == "ping":
            send({"jsonrpc": "2.0", "id": mid, "result": {}})
        elif mid is not None:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "Method not found"}})


if __name__ == "__main__":
    main()
