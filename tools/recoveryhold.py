import sys, socket, time, re
sys.path.insert(0, r"C:\Users\david\AppData\Local\Temp\opencode")
import sierrakeygen as sk
HOST = "192.168.1.1"; PORT = 5510; GEN = "SDX75"
kg = sk.SierraKeygen(None, GEN)

def drain(s, t=1.0):
    s.settimeout(t); buf = b""
    try:
        while True:
            d = s.recv(4096)
            if not d: break
            buf += d
    except socket.timeout:
        pass
    except Exception as e:
        print("[drain exc]", repr(e))
    return buf.decode(errors="replace")

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(8); s.connect((HOST, PORT))
time.sleep(0.6); print("[banner]", drain(s, 0.8).strip())

def send(cmd, wait=1.0):
    try:
        s.sendall((cmd + "\r").encode())
    except Exception as e:
        print(">> " + cmd + " [send exc " + repr(e) + "]"); return ""
    time.sleep(wait)
    r = drain(s, wait)
    print(">> " + cmd); print(r); return r

# engineer unlock
r = send("AT!OPENLOCK?", 1.2)
m = re.search(r"([0-9A-F]{16})", r)
if m:
    resp = kg.keygen.run(GEN, m.group(1), 0)
    send('AT!OPENLOCK="' + resp + '"', 1.2)
else:
    print("[!] no challenge")

print("== triggering RECOVERYHOLD (device should drop into fastboot) ==")
try:
    s.sendall(b"AT!RECOVERYHOLD\r")
    time.sleep(1.5)
    print("[resp]", drain(s, 2.0))
except Exception as e:
    print("[expected drop]", repr(e))
s.close()
