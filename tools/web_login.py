import urllib.request, urllib.parse, http.cookiejar, json, re, sys

BASE = "http://192.168.1.1"
import os
PASSWORD = os.environ.get("MR7500_ADMIN_PASSWORD", "")

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.addheaders = [("User-Agent", "Mozilla/5.0")]

def get(path):
    r = op.open(BASE + path, timeout=12)
    return r.read().decode(errors="replace"), r.geturl()

def post(path, data):
    enc = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(BASE + path, data=enc, method="POST")
    r = op.open(req, timeout=12)
    return r.read().decode(errors="replace"), r.geturl()

def cookies():
    return {c.name: c.value for c in cj}

# 1. bootstrap session + secToken
body, url = get("/model.json")
try:
    sec = json.loads(body)["session"]["secToken"]
except Exception:
    m = re.search(r'"secToken"\s*:\s*"([^"]+)"', body)
    sec = m.group(1) if m else None
print("[*] bootstrap url:", url)
print("[*] secToken:", sec)
print("[*] cookies:", cookies())

# 2. login
data = {
    "token": sec,
    "err_redirect": "/index.html?loginfailed",
    "ok_redirect": "/model.json",
    "session.password": PASSWORD,
}
body, url = post("/Forms/config", data)
print("[*] login POST -> url:", url)
print("[*] cookies after login:", cookies())

# 3. re-read model.json to see role + new token
body, url = get("/model.json")
try:
    j = json.loads(body)
    print("[*] session after login:", json.dumps(j.get("session", {}), indent=1)[:400])
    print("[*] general:", json.dumps(j.get("general", {}), indent=1)[:400])
    sec2 = j.get("session", {}).get("secToken")
except Exception as e:
    print("[!] model.json parse fail:", e); print(body[:500]); sec2 = sec

# 4. probe internal api
for p in ["/api/model.json?internalapi=1"]:
    try:
        body, url = get(p)
        print("\n[*] GET", p, "->", len(body), "bytes")
        print(body[:1500])
    except Exception as e:
        print("[!] GET", p, "failed:", repr(e))
