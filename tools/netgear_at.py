import socket, sys, time, argparse

HOST = "192.168.1.1"

def scan(ports):
    open_ports = []
    for p in ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.2)
        try:
            if s.connect_ex((HOST, p)) == 0:
                open_ports.append(p)
        except Exception:
            pass
        finally:
            s.close()
    return open_ports

def at_session(port, commands, banner_wait=1.0, read_wait=0.8):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(6)
    s.connect((HOST, port))
    out = []
    def drain(t=read_wait):
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
        return buf
    time.sleep(banner_wait)
    banner = drain(1.0)
    if banner:
        out.append(("__BANNER__", banner.decode(errors="replace")))
    for cmd in commands:
        s.sendall((cmd + "\r").encode())
        time.sleep(read_wait)
        resp = drain(read_wait)
        out.append((cmd, resp.decode(errors="replace")))
    s.close()
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--port", type=int, default=5510)
    ap.add_argument("--cmd", action="append", default=[])
    ap.add_argument("--readwait", type=float, default=0.8)
    a = ap.parse_args()

    if a.scan:
        ports = [21,22,23,53,80,443,5510,8080,8443,9008,2323,5037,5555,49152]
        op = scan(ports)
        print("OPEN PORTS:", op if op else "none")
        sys.exit(0)

    cmds = a.cmd if a.cmd else ["ATI", "AT!GSTATUS?"]
    try:
        res = at_session(a.port, cmds, read_wait=a.readwait)
        for c, r in res:
            print("=" * 50)
            print(">> " + c)
            print(r)
    except Exception as e:
        print("ERROR:", repr(e))
