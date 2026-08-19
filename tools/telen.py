import sys, socket, time, re
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
time.sleep(0.8); print("[banner]", drain(s, 1.0).strip())

def send(cmd, wait=1.0):
    s.sendall((cmd + "\r").encode()); time.sleep(wait); r = drain(s, wait)
    print(">> " + cmd); print(r); return r

print("== confirm engineer unlock still active ==")
send('AT!UDPID?', 1.0)
print("== telnet state + enable (no CND) ==")
send('AT!TELEN?', 1.0)
send('AT!TELEN=1', 1.0)
send('AT!TELEN?', 1.0)
s.close()
