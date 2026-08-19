import requests, json, re, sys

BASE = "http://192.168.1.1"
import os
PASSWORD = os.environ.get("MR7500_ADMIN_PASSWORD", "")
s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0"

def login():
    r = s.get(BASE + "/model.json", timeout=12)
    sec = r.json()["session"]["secToken"]
    r = s.post(BASE + "/Forms/config", data={
        "token": sec, "err_redirect": "/index.html?loginfailed",
        "ok_redirect": "/model.json", "session.password": PASSWORD}, timeout=12, allow_redirects=True)
    sec = s.get(BASE + "/model.json", timeout=12).json()["session"]["secToken"]
    return sec

sec = login()
print("[*] logged in, secToken:", sec)

cfg = open(r"C:\Users\david\AppData\Local\Temp\opencode\export.cfg", "r").read()

# modifications
mods = []
if "general.factoryTest=" not in cfg:
    cfg = cfg.replace("#general.factoryTest\n", "#general.factoryTest\ngeneral.factoryTest=true\n")
    mods.append("general.factoryTest=true")
print("[*] mods:", mods)

open(r"C:\Users\david\AppData\Local\Temp\opencode\export_mod.cfg", "w").write(cfg)

files = {"config": ("export.cfg", cfg.encode(), "application/octet-stream")}
data = {"token": sec, "ok_redirect": "/index.html?import=success", "err_redirect": "/index.html?import=failed"}
r = s.post(BASE + "/Forms/Import", data=data, files=files, timeout=60, allow_redirects=False)
print("[*] import status:", r.status_code)
print("[*] location:", r.headers.get("Location"))
print("[*] body head:", r.text[:300])
