"""FOTA update-check capture for the MR7500 (plan-v2 vector 2.2).

Logs into the web admin, reads fota.fwupdater, triggers a check
(fota.fwupdater.chknow via /Forms/config), and polls the internal API for the
resulting available-version / description / size / any URL. The firmware itself
downloads over cellular (not visible to the host), so we mine the device's own
API for the version + URL, then source the .cwe/.secc from that.

The admin password comes from $MR7500_ADMIN_PASSWORD, or is prompted for
(hidden) when run in an interactive terminal -- so it never lands in argv,
shell history, or logs. This only READS and triggers a check; with
fota.webupdater.autoUpdate=false it will not self-install. Do NOT accept/install
an update if you want to preserve the current firmware.

Usage:
  py tools/fota_capture.py                 # prompts for password, auto-detect host
  MR7500_ADMIN_PASSWORD=... py tools/fota_capture.py --host 10.0.1.1 --no-trigger
"""
import os, sys, json, time, argparse, getpass
import urllib.request, urllib.parse
from http.cookiejar import CookieJar


def mk_opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))


def get(op, url, t=12):
    return op.open(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=t).read().decode("utf-8", "replace")


def post(op, url, data, t=20):
    body = urllib.parse.urlencode(data).encode()
    return op.open(urllib.request.Request(url, data=body, headers={"User-Agent": "Mozilla/5.0"}), timeout=t).read().decode("utf-8", "replace")


def sec_of(op, base):
    return json.loads(get(op, base + "/model.json"))["session"]["secToken"]


def find_host(hosts):
    for h in hosts:
        try:
            sec_of(mk_opener(), "http://" + h); return h
        except Exception:
            continue
    return None


def fwupdater_of(blob):
    try:
        j = json.loads(blob)
    except Exception:
        return None

    def walk(o):
        if isinstance(o, dict):
            if "fwupdater" in o:
                return o["fwupdater"]
            for v in o.values():
                r = walk(v)
                if r is not None:
                    return r
        elif isinstance(o, list):
            for v in o:
                r = walk(v)
                if r is not None:
                    return r
        return None
    return walk(j)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host")
    ap.add_argument("--chkfield", default="fota.fwupdater.chknow")
    ap.add_argument("--chkval", default="1")
    ap.add_argument("--no-trigger", action="store_true", help="read state only; do NOT trigger a check")
    ap.add_argument("--polls", type=int, default=20)
    a = ap.parse_args()

    pw = os.environ.get("MR7500_ADMIN_PASSWORD", "")
    if not pw:
        if sys.stdin.isatty():
            pw = getpass.getpass("MR7500 admin password: ")
        else:
            print("[!] set MR7500_ADMIN_PASSWORD or run in an interactive terminal"); return
    if not pw:
        print("[!] no password"); return

    host = a.host or find_host(["10.0.1.1", "192.168.1.1"])
    if not host:
        print("[!] no web UI on 10.0.1.1 / 192.168.1.1 — is the device in NORMAL mode?"); return
    base = "http://" + host
    print("[*] host:", host)

    op = mk_opener()
    sec = sec_of(op, base)
    post(op, base + "/Forms/config", {"token": sec, "err_redirect": "/x",
         "ok_redirect": "/model.json", "session.password": pw})
    try:
        sec = sec_of(op, base)
    except Exception as e:
        print("[!] login failed:", e); return
    print("[*] logged in, secToken:", sec)

    internal = base + "/api/model.json?internalapi=1"
    before = fwupdater_of(get(op, internal))
    print("[*] fota.fwupdater BEFORE:", json.dumps(before) if before else "(not found — login ok?)")
    if a.no_trigger:
        print("[*] --no-trigger: not firing a check."); return

    print("[*] triggering check: %s=%s" % (a.chkfield, a.chkval))
    try:
        post(op, base + "/Forms/config", {"token": sec, a.chkfield: a.chkval,
             "err_redirect": "/x", "ok_redirect": "/model.json"})
    except Exception as e:
        print("    trigger err:", repr(e))

    base_state = before.get("state") if before else None
    for i in range(a.polls):
        time.sleep(3)
        try:
            f = fwupdater_of(get(op, internal))
        except Exception:
            continue
        if not f:
            continue
        print("  t+%2ds state=%s available=%s size=%s desc=%r" % (
            i * 3, f.get("state"), f.get("available"), f.get("dloadSize"), f.get("description")))
        if (f.get("state") not in ("Checking", "Initial", base_state)) or f.get("available"):
            print("[*] fota.fwupdater AFTER:", json.dumps(f))
            for k, v in f.items():
                if isinstance(v, str) and ("http" in v or ".cwe" in v or ".secc" in v):
                    print("    URL-ish %s = %s" % (k, v))
            break
    print("DONE  (do NOT accept/install if preserving current firmware)")


if __name__ == "__main__":
    main()
