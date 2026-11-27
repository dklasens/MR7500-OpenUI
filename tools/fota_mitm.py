"""FOTA capture honeypot (plan-v2 vector 2.2, MITM variant).

OPTION A (USB->WAN): flip the MR7500's ethusb to WAN so it uses the host-USB link
as its upstream, then run this as ADMIN on the host. It:
  - (optional) sets the host USB interface to a static IP   (--setip)
  - DHCP server (:67)  -> leases the device a WAN IP, gateway/DNS = this host
  - DNS   server (:53) -> answers EVERY name with this host  => logs the FOTA HOSTNAME
  - HTTP  server (:80) -> logs method / Host / path / headers => the .cwe URL path
  - TLS   SNI    (:443)-> parses the ClientHello (no cert)    => the FOTA HOSTNAME
It does NOT forward upstream, so the device's check fails AFTER we capture where it
was going. That hostname/path is what we then use to fetch the stock .cwe.

Because the USB link becomes the device's WAN, the host loses its 10.0.1.1
management path -- manage the device (flip ethusb mode, trigger the check, revert)
over WiFi from a phone/laptop.

Usage (ADMIN PowerShell):
  py tools/fota_mitm.py --setip                 # self=192.168.7.1, offer=192.168.7.2
  py tools/fota_mitm.py --self 192.168.7.1 --offer 192.168.7.2 --iface "SDX75 USB Tethering" --setip
Revert the host iface afterwards:
  netsh interface ip set address "SDX75 USB Tethering" dhcp
"""
import socket, struct, threading, argparse, datetime, subprocess, sys

LOG = None


def log(msg):
    line = "%s  %s" % (datetime.datetime.now().strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    if LOG:
        try:
            open(LOG, "a", encoding="utf-8").write(line + "\n")
        except Exception:
            pass


# ---------------- DHCP (lease the device a WAN IP) ----------------
def dhcp_opt(opts, want):
    i = 0
    while i < len(opts):
        o = opts[i]
        if o == 255 or o == 0:
            break
        ln = opts[i + 1]
        if o == want:
            return opts[i + 2:i + 2 + ln]
        i += 2 + ln
    return None


def dhcp_reply(xid, chaddr, yiaddr, selfip, mask, msgtype, flags):
    pkt = struct.pack(">BBBB", 2, 1, 6, 0) + xid + struct.pack(">HH", 0, flags)
    pkt += socket.inet_aton("0.0.0.0") + socket.inet_aton(yiaddr) + socket.inet_aton(selfip) + socket.inet_aton("0.0.0.0")
    pkt += chaddr + b"\x00" * (16 - len(chaddr)) + b"\x00" * 64 + b"\x00" * 128
    pkt += struct.pack(">I", 0x63825363)
    pkt += bytes([53, 1, msgtype])
    pkt += bytes([54, 4]) + socket.inet_aton(selfip)
    pkt += bytes([51, 4]) + struct.pack(">I", 3600)
    pkt += bytes([1, 4]) + socket.inet_aton(mask)
    pkt += bytes([3, 4]) + socket.inet_aton(selfip)
    pkt += bytes([6, 4]) + socket.inet_aton(selfip)
    pkt += bytes([255])
    return pkt


def dhcp_server(selfip, offer, mask="255.255.255.0"):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        s.bind(("0.0.0.0", 67))
    except Exception as e:
        log("[DHCP] bind :67 failed (%r) -- admin? another DHCP running?" % e); return
    log("[DHCP] :67 up -> offering %s (gw/dns=%s)" % (offer, selfip))
    while True:
        try:
            data, addr = s.recvfrom(2048)
            if len(data) < 240 or data[0] != 1:
                continue
            xid = data[4:8]; flags = struct.unpack(">H", data[10:12])[0]
            chaddr = data[28:34]
            mt = dhcp_opt(data[240:], 53)
            if not mt:
                continue
            mt = mt[0]
            rt = 2 if mt == 1 else (5 if mt == 3 else None)  # DISCOVER->OFFER, REQUEST->ACK
            if rt is None:
                continue
            reply = dhcp_reply(xid, chaddr, offer, selfip, mask, rt, flags)
            s.sendto(reply, ("255.255.255.255", 68))
            log("[DHCP] %s -> %s %s" % ("DISCOVER" if mt == 1 else "REQUEST", "OFFER" if rt == 2 else "ACK", offer))
        except Exception as e:
            log("[DHCP] err %r" % e)


# ---------------- DNS ----------------
def dns_name(data, off):
    out = []
    while True:
        ln = data[off]
        if ln == 0:
            off += 1; break
        if ln & 0xC0:
            off += 2; break
        out.append(data[off + 1:off + 1 + ln].decode("latin1")); off += 1 + ln
    return ".".join(out), off


def dns_server(answer_ip):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", 53))
    except Exception as e:
        log("[DNS] bind :53 failed (%r) -- admin?" % e); return
    log("[DNS] :53 up -> A=%s for everything" % answer_ip)
    while True:
        try:
            data, addr = s.recvfrom(2048)
            qname, qend = dns_name(data, 12)
            log("[DNS] *** %s asked for %s ***" % (addr[0], qname))
            resp = data[:2] + b"\x81\x80" + struct.pack(">HHHH", 1, 1, 0, 0) + data[12:qend + 4]
            resp += b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, 60, 4) + socket.inet_aton(answer_ip)
            s.sendto(resp, addr)
        except Exception as e:
            log("[DNS] err %r" % e)


# ---------------- HTTP ----------------
def http_server():
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", 80)); s.listen(16)
    except Exception as e:
        log("[HTTP] bind :80 failed (%r)" % e); return
    log("[HTTP] :80 up")
    while True:
        try:
            c, addr = s.accept()
            threading.Thread(target=_http, args=(c, addr), daemon=True).start()
        except Exception:
            pass


def _http(c, addr):
    try:
        c.settimeout(5)
        req = c.recv(8192).decode("latin1", "replace")
        first = req.split("\r\n")[0]
        host = next((l.split(":", 1)[1].strip() for l in req.split("\r\n") if l.lower().startswith("host:")), "")
        log("[HTTP] *** %s  %s  Host=%s ***" % (addr[0], first, host))
        log("[HTTP]   head: " + req[:500].replace("\r\n", " | "))
        c.sendall(b"HTTP/1.1 302 Found\r\nLocation: /\r\nContent-Length: 0\r\n\r\n")
    except Exception:
        pass
    finally:
        try: c.close()
        except Exception: pass


# ---------------- TLS SNI ----------------
def sni_of(h):
    try:
        if h[0] != 0x16:
            return None
        hs = h[5:]
        if hs[0] != 0x01:
            return None
        p = 1 + 3 + 2 + 32
        p += 1 + hs[p]                                   # session id
        p += 2 + struct.unpack(">H", hs[p:p + 2])[0]     # cipher suites
        p += 1 + hs[p]                                   # compression
        p += 2                                           # ext total len
        while p + 4 <= len(hs):
            et, el = struct.unpack(">HH", hs[p:p + 4]); p += 4
            if et == 0:
                nlen = struct.unpack(">H", hs[p + 3:p + 5])[0]
                return hs[p + 5:p + 5 + nlen].decode("latin1")
            p += el
    except Exception:
        return None


def tls_server():
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", 443)); s.listen(16)
    except Exception as e:
        log("[TLS] bind :443 failed (%r)" % e); return
    log("[TLS] :443 up (SNI capture)")
    while True:
        try:
            c, addr = s.accept(); c.settimeout(5)
            sni = sni_of(c.recv(4096)); c.close()
            log("[TLS] *** %s SNI=%s ***" % (addr[0], sni))
        except Exception:
            pass


def set_iface(iface, ip, mask):
    try:
        r = subprocess.run(["netsh", "interface", "ip", "set", "address",
                            "name=%s" % iface, "static", ip, mask],
                           capture_output=True, text=True)
        log("[iface] set %s -> %s (%s)" % (iface, ip, (r.stdout + r.stderr).strip() or "ok"))
    except Exception as e:
        log("[iface] netsh err %r (run as admin?)" % e)


def main():
    global LOG
    ap = argparse.ArgumentParser()
    ap.add_argument("--self", dest="selfip", default="192.168.7.1")
    ap.add_argument("--offer", default="192.168.7.2")
    ap.add_argument("--mask", default="255.255.255.0")
    ap.add_argument("--iface", default="SDX75 USB Tethering")
    ap.add_argument("--setip", action="store_true", help="set the host iface to --self via netsh (admin)")
    ap.add_argument("--no-dhcp", action="store_true", help="device WAN is static; skip DHCP")
    ap.add_argument("--log", default="fota_mitm.log")
    a = ap.parse_args()
    LOG = a.log
    log("=== fota_mitm (Option A) start  self=%s offer=%s iface=%r ===" % (a.selfip, a.offer, a.iface))
    if a.setip:
        set_iface(a.iface, a.selfip, a.mask)
    threads = [threading.Thread(target=dns_server, args=(a.selfip,), daemon=True),
               threading.Thread(target=http_server, daemon=True),
               threading.Thread(target=tls_server, daemon=True)]
    if not a.no_dhcp:
        threads.insert(0, threading.Thread(target=dhcp_server, args=(a.selfip, a.offer, a.mask), daemon=True))
    for t in threads:
        t.start()
    log(">>> Now (over WiFi) set the device's ethusb/LAN1 to WAN and trigger the firmware check.")
    log(">>> Watch for lines marked *** -- that's the FOTA hostname/URL. Ctrl+C to stop.")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        log("stopped")


if __name__ == "__main__":
    main()
