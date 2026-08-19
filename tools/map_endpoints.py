import re
base = r"C:\Users\david\AppData\Local\Temp\opencode"
c = open(base + r"\_static_js_script_js", encoding="utf-8", errors="replace").read()
print("len", len(c))
paths = set(re.findall(r'["\'](/(?:Forms|api|goform|cgi-bin|dav|Fs)[A-Za-z0-9_/.?=&%-]*)["\']', c))
print("ENDPOINTS:")
for p in sorted(paths):
    print("  ", p)
print()
# also find any "/Forms/..." occurrences raw
fm = set(re.findall(r'/Forms/[A-Za-z0-9_/-]+', c))
print("Forms paths:", sorted(fm))
ap = set(re.findall(r'/api/[A-Za-z0-9_/.-]+', c))
print("api paths:", sorted(ap))
print()
for kw in ["ping", "diagnostic", "Diagnostic", "packet", "capture"]:
    idxs = [m.start() for m in re.finditer(kw, c)]
    print("=== %s (%d) ===" % (kw, len(idxs)))
    for i in idxs[:4]:
        print("  ..." + c[max(0, i-60):i+100].replace("\n", " ") + "...")
