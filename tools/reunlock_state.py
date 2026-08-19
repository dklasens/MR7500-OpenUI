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
    return buf.decode(errors="replace")

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(8); s.connect((HOST, PORT))
time.sleep(0.6); print("[banner]", drain(s, 0.8).strip())

def send(cmd, wait=1.0):
    s.sendall((cmd + "\r").encode()); time.sleep(wait); r = drain(s, wait)
    print(">> " + cmd); print(r); return r

# engineer unlock
r = send("AT!OPENLOCK?", 1.2)
ch = re.search(r"([0-9A-F]{16})", r).group(1)
resp = kg.keygen.run(GEN, ch, 0)
send('AT!OPENLOCK="' + resp + '"', 1.2)

print("== state ==")
send("AT!CUSTOM?", 1.0)
send("AT!UDPID?", 1.0)
s.close()
