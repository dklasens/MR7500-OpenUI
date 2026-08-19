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

def send(cmd, wait=0.9):
    s.sendall((cmd + "\r").encode()); time.sleep(wait); r = drain(s, wait)
    print(">> " + cmd); print(r)
    return r

for cmd in [
    'AT!CUSTOM="ADBENABLE",1',
    'AT!CUSTOM="TELNETENABLE",1',
    'AT!CUSTOM="ADBENABLE"?',
    'AT!CUSTOM="TELNETENABLE"?',
    'AT!CUSTOM?',
]:
    send(cmd)
s.close()
