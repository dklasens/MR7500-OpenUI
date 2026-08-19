import socket, time
HOST = "192.168.1.1"; PORT = 5510

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

def send(cmd, wait=1.5):
    try:
        s.sendall((cmd + "\r").encode())
    except Exception as e:
        print(">> " + cmd + "  [send failed: " + repr(e) + "]"); return ""
    time.sleep(wait)
    try:
        r = drain(s, wait)
    except Exception as e:
        print(">> " + cmd + "  [read failed: " + repr(e) + "]"); return ""
    print(">> " + cmd); print(r); return r

send("AT!UDPID?", 1.0)
print("== switching to 68E2 (ADB composite) ==")
send("AT!UDPID=68E2", 2.5)
time.sleep(1)
send("AT!UDPID?", 1.5)
s.close()
