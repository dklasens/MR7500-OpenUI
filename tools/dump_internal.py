import urllib.request, urllib.parse, http.cookiejar, json, re, sys

BASE = "http://192.168.1.1"
import os
PASSWORD = os.environ.get("MR7500_ADMIN_PASSWORD", "")
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.addheaders = [("User-Agent", "Mozilla/5.0")]

def get(path):
    r = op.open(BASE + path, timeout=12); return r.read().decode(errors="replace"), r.geturl()

def post(path, data):
    enc = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(BASE + path, data=enc, method="POST")
    r = op.open(req, timeout=12); return r.read().decode(errors="replace"), r.geturl()

body,_ = get("/model.json")
sec = json.loads(body)["session"]["secToken"]
post("/Forms/config", {"token":sec,"err_redirect":"/index.html?loginfailed","ok_redirect":"/model.json","session.password":PASSWORD})
body,_ = get("/model.json")
sec = json.loads(body)["session"]["secToken"]

full,_ = get("/api/model.json?internalapi=1")
open(r"C:\Users\david\AppData\Local\Temp\opencode\internal_api.json","w").write(full)
print("[*] saved internal_api.json", len(full), "bytes; secToken:", sec)

# top-level keys
try:
    j = json.loads(full)
    print("[*] top-level keys:", list(j.keys()))
except Exception as e:
    print("[!] not strict json:", e)
