import re
base = r"C:\Users\david\AppData\Local\Temp\opencode"
js = open(base + r"\_static_js_script_js", encoding="utf-8", errors="replace").read()
html = open(base + r"\index_body.html", encoding="utf-8", errors="replace").read()

def ctx(blob, kw, n=6, w=140, label=""):
    idxs = [m.start() for m in re.finditer(re.escape(kw), blob)]
    print("=== %s in %s (%d) ===" % (kw, label, len(idxs)))
    for i in idxs[:n]:
        print("  ..." + blob[max(0, i-70):i+w].replace("\n", " ") + "...")
    print()

ctx(js, "/Forms/Import", 6, 160, "js")
ctx(html, "Import", 6, 160, "html")
ctx(html, "multipart", 4, 120, "html")
ctx(html, "enctype", 6, 160, "html")
ctx(js, "testmode", 4, 120, "js")
ctx(js, "/Forms/profile", 6, 160, "js")
