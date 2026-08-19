import urllib.request, urllib.parse, http.cookiejar, json

BASE = "http://192.168.1.1"
import os
PASSWORD = os.environ.get("MR7500_ADMIN_PASSWORD", "")
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.addheaders = [("User-Agent", "Mozilla/5.0")]

def get(path, raw=False):
    r = op.open(BASE + path, timeout=15)
    b = r.read()
    return (b if raw else b.decode(errors="replace")), r.geturl(), r.headers.get("Content-Type")

body,_,_ = get("/model.json")
sec = json.loads(body)["session"]["secToken"]
enc = urllib.parse.urlencode({"token":sec,"err_redirect":"/index.html?loginfailed","ok_redirect":"/model.json","session.password":PASSWORD}).encode()
op.open(urllib.request.Request(BASE+"/Forms/config", data=enc, method="POST"), timeout=15)

data, url, ct = get("/dui/export.cfg?save=export.cfg", raw=True)
print("[*] url:", url, "| content-type:", ct, "| bytes:", len(data))
out = r"C:\Users\david\AppData\Local\Temp\opencode\export.cfg"
open(out, "wb").write(data)
print("[*] saved to", out)
print("[*] head (repr):")
print(repr(data[:400]))
