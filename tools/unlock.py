import sys, socket, time, re
sys.path.insert(0, r"C:\Users\david\AppData\Local\Temp\opencode")
import sierrakeygen as sk

HOST = "192.168.1.1"
PORT = 5510
GEN = "SDX75"

kg = sk.SierraKeygen(None, GEN)

def drain(s, t=1.0):
    s.settimeout(t)
    buf = b""
    try:
        while True:
            d = s.recv(4096)
            if not d:
                break
            buf += d
    except socket.timeout:
        pass
    return buf.decode(errors="replace")

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(8)
s.connect((HOST, PORT))
time.sleep(0.8)
banner = drain(s, 1.0)
print("[banner]", banner.strip())

def send(cmd, wait=1.0):
    s.sendall((cmd + "\r").encode())
    time.sleep(wait)
    r = drain(s, wait)
    print(">> " + cmd)
    print(r)
    return r

# 1. get fresh challenge
r = send("AT!OPENLOCK?", 1.2)
m = re.search(r"([0-9A-F]{16})", r)
if not m:
    print("FAILED to parse challenge"); sys.exit(1)
challenge = m.group(1)
print("[challenge]", challenge)

# 2. compute response
resp = kg.keygen.run(GEN, challenge, 0)
print("[response]", resp)

# 3. send response
r = send('AT!OPENLOCK="' + resp + '"', 1.2)

# 4. verify unlock with privileged commands
print("\n===== VERIFY (privileged) =====")
send("AT!OPENLOCK?", 1.0)
send("AT!GSTATUS?", 1.2)
send("AT!UDPID?", 1.0)
send("AT!USBCOMP?", 1.0)
s.close()
