import socket, time, sys
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

if len(sys.argv) > 1 and sys.argv[1] == "reset":
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(5); s.connect((HOST, PORT))
    time.sleep(0.5); drain(s, 0.8)
    s.sendall(b"AT!RESET\r")
    time.sleep(0.8)
    try:
        print("[reset] sent AT!RESET:", drain(s, 1.5).strip())
    except Exception as e:
        print("[reset] connection dropped as expected:", repr(e))
    s.close()
    sys.exit(0)

# poll mode: wait for port 5510 to answer ATI
deadline = time.time() + 240
up = False
while time.time() < deadline:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(3)
        if s.connect_ex((HOST, PORT)) == 0:
            time.sleep(0.6); drain(s, 0.8)
            s.sendall(b"ATI\r"); time.sleep(1.0)
            r = drain(s, 1.2)
            if "MR7500" in r or "Revision" in r:
                print("[poll] device back online:\n" + r)
                up = True; s.close(); break
        s.close()
    except Exception:
        pass
    time.sleep(4)
print("[poll] online" if up else "[poll] NOT back within timeout")
