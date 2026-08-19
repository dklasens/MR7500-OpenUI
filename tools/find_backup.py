import re
base = r"C:\Users\david\AppData\Local\Temp\opencode"
js = open(base + r"\_static_js_script_js", encoding="utf-8", errors="replace").read()
html = open(base + r"\index_body.html", encoding="utf-8", errors="replace").read()

def ctx(blob, kw, n=5, w=150, label=""):
    idxs = [m.start() for m in re.finditer(kw, blob, re.I)]
    print("=== %s in %s (%d) ===" % (kw, label, len(idxs)))
    for i in idxs[:n]:
        print("  ..." + blob[max(0, i-70):i+w].replace("\n", " ") + "...")
    print()

for kw in ["backup", "restore", "export", "download", "\\.cfg", "\\.bin", "config\\.tar", "saveconfig"]:
    ctx(js, kw, 4, 140, "js")

# import form full context
i = js.find("/Forms/Import")
print("=== /Forms/Import wide context ===")
print(js[max(0, i-500):i+400])
