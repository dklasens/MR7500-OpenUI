"""Capture AT-console output to captures/ (vectors 2.7 + README S4 open item 3).

Connects to the unauthenticated AT console (telnet :5510), runs a set of AT
commands, prints them, and archives the full transcript under captures/.

Presets:
  custom   -> AT!CUSTOM?  full flag inventory      -> captures/at_custom_flags.txt
  secboot  -> AT!SECBOOTCFG? / AT!SECBOOTPKHASH?   -> captures/at_secboot.txt

Usage:
  python tools/at_capture.py --preset custom
  python tools/at_capture.py --preset secboot
  python tools/at_capture.py --cmd "ATI" --cmd "AT!GSTATUS?" --out ../captures/at_misc.txt

Note: AT!SECBOOT* and some AT!CUSTOM reads may require an engineer unlock first
(run tools/unlock.py in a separate step, same session persists until reboot). If a
command returns ERROR, that is captured too -- it is itself a finding.

Env:
  MR7500_HOST   router IP (default 192.168.1.1)
"""
import os, sys, socket, time, argparse, datetime

HOST = os.environ.get("MR7500_HOST", "192.168.1.1")
PORT = int(os.environ.get("MR7500_AT_PORT", "5510"))
CAP_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "captures"))

PRESETS = {
    "custom": (["AT!CUSTOM?"], "at_custom_flags.txt"),
    "secboot": (["AT!SECBOOTCFG?", "AT!SECBOOTPKHASH?", "AT!SECBOOT?"], "at_secboot.txt"),
}


def drain(s, t=1.0):
    s.settimeout(t)
    buf = b""
    try:
        while True:
            d = s.recv(4096)
            if not d:
                break
            buf += d
    except socket.timeout:
        pass
    return buf.decode(errors="replace")


def run(commands, read_wait):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(8)
    s.connect((HOST, PORT))
    time.sleep(0.6)
    transcript = []
    banner = drain(s, 1.0).strip()
    if banner:
        transcript.append(("[banner]", banner))
        print("[banner]", banner)
    for cmd in commands:
        s.sendall((cmd + "\r").encode())
        time.sleep(read_wait)
        resp = drain(s, read_wait)
        transcript.append((cmd, resp))
        print(">> " + cmd)
        print(resp)
    s.close()
    return transcript


def main():
    ap = argparse.ArgumentParser(description="MR7500 AT-console capture")
    ap.add_argument("--preset", choices=list(PRESETS))
    ap.add_argument("--cmd", action="append", default=[], help="extra/explicit AT command (repeatable)")
    ap.add_argument("--out", help="output file (default: preset path, or captures/at_capture.txt)")
    ap.add_argument("--readwait", type=float, default=1.0)
    a = ap.parse_args()

    commands = []
    out = a.out
    if a.preset:
        pcmds, pout = PRESETS[a.preset]
        commands += pcmds
        if not out:
            out = os.path.join(CAP_DIR, pout)
    commands += a.cmd
    if not commands:
        print("nothing to do: pass --preset and/or --cmd"); return
    if not out:
        out = os.path.join(CAP_DIR, "at_capture.txt")

    try:
        transcript = run(commands, a.readwait)
    except Exception as e:
        print("ERROR:", repr(e)); return

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("# MR7500 AT capture  host=%s:%d  %s UTC\n" % (
            HOST, PORT, datetime.datetime.now(datetime.timezone.utc).isoformat()))
        if a.preset:
            f.write("# preset=%s\n" % a.preset)
        f.write("#\n")
        for cmd, resp in transcript:
            f.write("== %s ==\n%s\n" % (cmd, resp.rstrip("\n")))
    print("[*] archived ->", out)


if __name__ == "__main__":
    main()
