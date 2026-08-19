import re
c = open(r"C:\Users\david\AppData\Local\Temp\opencode\_static_js_script_js", encoding="utf-8", errors="replace").read()
i = c.find('profile.ipaddr')
print("=== profile submit context ===")
print(c[max(0, i-1000):i+260])
print()
print("=== action: values ===")
vals = set(re.findall(r'action:\s*"([a-zA-Z]+)"', c))
print(sorted(vals))
print()
print("=== 'add' profile flow ===")
for m in re.finditer(r'action"\]?"?\s*[:=]\s*"add"', c):
    j = m.start(); print("..." + c[max(0, j-150):j+120].replace("\n", " ") + "...")
