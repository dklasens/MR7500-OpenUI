"""Full TCP/UDP port scan of the MR7500 (vector 2.5).

netgear_at.py --scan only checks 14 known ports. This sweeps all 65535 TCP ports
(threaded connect scan) and probes the live UDP services (SSDP 1900, mDNS 5353),
optionally over IPv6 link-local. The point is to find undocumented listeners such
as the NETGEAR Insight agent.

Usage:
  python tools/full_scan.py                       # full TCP 1-65535 + UDP 1900/5353
  python tools/full_scan.py --ports 1-10000       # narrower TCP range
  python tools/full_scan.py --workers 400
  python tools/full_scan.py --no-udp
  python tools/full_scan.py --ipv6 "fe80::1%15"   # IPv6 link-local (addr%zone/scope-id)
  python tools/full_scan.py --save ../captures/portscan.txt

Env:
  MR7500_HOST   router IP (default 192.168.1.1)
"""
import os, sys, socket, argparse, struct
from concurrent.futures import ThreadPoolExecutor, as_completed

HOST = os.environ.get("MR7500_HOST", "192.168.1.1")


def parse_ports(spec):
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


def tcp_probe(host, port, timeout, family=socket.AF_INET):
    s = socket.socket(family, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        return port if s.connect_ex((host, port)) == 0 else None
    except Exception:
        return None
    finally:
        s.close()


def scan_tcp(host, ports, workers, timeout, family=socket.AF_INET):
    found = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(tcp_probe, host, p, timeout, family): p for p in ports}
        done = 0
        for f in as_completed(futs):
            done += 1
            r = f.result()
            if r is not None:
                found.append(r)
                print("  TCP %d OPEN" % r)
            if done % 5000 == 0:
                print("  ...%d/%d probed" % (done, len(ports)), file=sys.stderr)
    return sorted(found)


SSDP = (
    "M-SEARCH * HTTP/1.1\r\n"
    "HOST: %s:1900\r\n"
    'MAN: "ssdp:discover"\r\n'
    "MX: 2\r\nST: ssdp:all\r\n\r\n"
)
# minimal mDNS query for _services._dns-sd._udp.local (PTR)
MDNS = struct.pack(">HHHHHH", 0, 0, 0, 1, 0, 0) + b"".join(
    bytes([len(x)]) + x.encode() for x in ["_services", "_dns-sd", "_udp", "local"]
) + b"\x00" + struct.pack(">HH", 12, 1)


def udp_probe(host, port, payload, timeout=2.5, family=socket.AF_INET):
    s = socket.socket(family, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(payload if isinstance(payload, bytes) else payload.encode(), (host, port))
        data, addr = s.recvfrom(65535)
        return data
    except socket.timeout:
        return None
    except Exception as e:
        return ("ERR", repr(e))
    finally:
        s.close()


def scan_udp(host, family=socket.AF_INET):
    print("[*] UDP service probes")
    r = udp_probe(host, 1900, SSDP % host, family=family)
    if isinstance(r, bytes):
        print("  UDP 1900 (SSDP) responded %d bytes:" % len(r))
        print("    " + r.decode(errors="replace").strip().replace("\n", "\n    "))
    else:
        print("  UDP 1900 (SSDP): no reply", "" if r is None else r)
    r = udp_probe(host, 5353, MDNS, family=family)
    if isinstance(r, bytes):
        print("  UDP 5353 (mDNS) responded %d bytes (hex head): %s" % (len(r), r[:48].hex()))
    else:
        print("  UDP 5353 (mDNS): no reply", "" if r is None else r)


def main():
    ap = argparse.ArgumentParser(description="MR7500 full port scan")
    ap.add_argument("--ports", default="1-65535", help="TCP port spec, e.g. 1-65535 or 1-1024,5555")
    ap.add_argument("--workers", type=int, default=300)
    ap.add_argument("--timeout", type=float, default=1.0)
    ap.add_argument("--no-udp", action="store_true")
    ap.add_argument("--no-tcp", action="store_true")
    ap.add_argument("--ipv6", metavar="ADDR%ZONE", help="also scan this IPv6 link-local address")
    ap.add_argument("--save", help="write a summary to this file")
    a = ap.parse_args()

    ports = parse_ports(a.ports)
    lines = ["# MR7500 full_scan.py  host=%s  tcp_ports=%s" % (HOST, a.ports)]
    print("[*] TCP scan %s (%d ports) workers=%d timeout=%.1fs" % (HOST, len(ports), a.workers, a.timeout))

    tcp_open = []
    if not a.no_tcp:
        tcp_open = scan_tcp(HOST, ports, a.workers, a.timeout)
        print("[*] TCP open:", tcp_open if tcp_open else "none")
        lines.append("TCP open: " + (", ".join(map(str, tcp_open)) if tcp_open else "none"))

    if not a.no_udp:
        scan_udp(HOST)
        lines.append("UDP: probed 1900/5353 (see stdout for payloads)")

    if a.ipv6:
        addr = a.ipv6
        zone = None
        if "%" in addr:
            addr, zone = addr.split("%", 1)
        # getaddrinfo resolves the scope-id for link-local
        try:
            info = socket.getaddrinfo(a.ipv6 if zone else addr, None, socket.AF_INET6, socket.SOCK_STREAM)
            v6host = info[0][4][0] if not zone else a.ipv6
        except Exception:
            v6host = a.ipv6
        print("[*] IPv6 TCP scan %s (%d ports)" % (a.ipv6, len(ports)))
        try:
            v6open = scan_tcp(a.ipv6, ports, a.workers, a.timeout, family=socket.AF_INET6)
            print("[*] IPv6 TCP open:", v6open if v6open else "none")
            lines.append("IPv6 %s TCP open: %s" % (a.ipv6, ", ".join(map(str, v6open)) if v6open else "none"))
        except Exception as e:
            print("[!] IPv6 scan failed:", repr(e))

    if a.save:
        os.makedirs(os.path.dirname(os.path.abspath(a.save)), exist_ok=True)
        open(a.save, "w").write("\n".join(lines) + "\n")
        print("[*] saved summary ->", a.save)


if __name__ == "__main__":
    main()
