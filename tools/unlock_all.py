"""Combined Sierra unlock chain for the MR7500 (SDX75): OPENLOCK + OPENMEP +
OPENCND + ENTERCND, via the bundled sierrakeygen challenge/response.

SDX75 keygen id-types: run(chal,0)=OPENLOCK, run(chal,1)=OPENMEP, run(chal,2)=OPENCND.
sierrakeygen only imports Exscript for a telnet transport we don't use, so we stub it.

After unlocking it optionally sends follow-on AT commands you pass with --cmd
(repeatable), e.g. your persistence/reset sequence:
  --cmd 'AT!CUSTOM="CFUNPERSISTEN",1' --cmd 'AT&W' --cmd 'AT!GRESET'
By default (no --cmd) it just unlocks and then PROBES whether the Netgear shell
setters accept after the full chain (read-only intent -- it does not persist or
reset, so nothing is made live).

Usage:
  py tools/unlock_all.py                       # unlock chain + setter probe
  py tools/unlock_all.py --cmd 'AT...' --cmd 'AT...'
"""
import sys, types, socket, time, re, os, argparse

# stub Exscript.protocols.telnetlib (sierrakeygen imports Telnet but we don't use it)
_e = types.ModuleType("Exscript"); _p = types.ModuleType("Exscript.protocols")
_t = types.ModuleType("Exscript.protocols.telnetlib"); _t.Telnet = object
_e.protocols = _p; _p.telnetlib = _t
sys.modules.update({"Exscript": _e, "Exscript.protocols": _p, "Exscript.protocols.telnetlib": _t})
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import sierrakeygen as sk

GEN = "SDX75"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="10.0.1.1")
    ap.add_argument("--port", type=int, default=5510)
    ap.add_argument("--cnd", default="A710")
    ap.add_argument("--cmd", action="append", default=[], help="AT command to send after unlock (repeatable)")
    ap.add_argument("--probe", action="store_true", default=None, help="probe Netgear setters after unlock (default if no --cmd)")
    a = ap.parse_args()

    s = socket.socket(); s.settimeout(8); s.connect((a.host, a.port)); time.sleep(0.5)

    def drain(t=1.2):
        s.settimeout(t); b = b""
        try:
            while True:
                x = s.recv(4096)
                if not x:
                    break
                b += x
        except Exception:
            pass
        return b.decode(errors="replace")

    drain(0.6)

    def send(cmd, wait=1.3):
        s.sendall((cmd + "\r").encode()); time.sleep(wait); r = drain(wait)
        print(">> %s\n%s\n" % (cmd, r.strip()))
        return r

    kg = sk.SierraKeygen(None, GEN)

    def unlock(name, itype):
        r = send("AT!%s?" % name)
        m = re.search(r"([0-9A-Fa-f]{16})", r)
        if not m:
            print("[=] %s: no challenge (already unlocked / not applicable)\n" % name); return
        resp = kg.keygen.run(GEN, m.group(1).upper(), itype)
        rr = send('AT!%s="%s"' % (name, resp))
        print("[%s] %s\n" % ("OK" if "OK" in rr and "ERROR" not in rr else "??", name))

    print("===== UNLOCK CHAIN =====")
    unlock("OPENLOCK", 0)
    unlock("OPENMEP", 1)
    unlock("OPENCND", 2)
    send('AT!ENTERCND="%s"' % a.cnd)

    if a.cmd:
        print("===== FOLLOW-ON COMMANDS =====")
        for c in a.cmd:
            send(c)
    else:
        print("===== SETTER PROBE (does the full chain unlock them? read-only, no persist/reset) =====")
        for q in ['AT!CUSTOM="RDENABLE"?', 'AT!CUSTOM="TELNETENABLE"?', 'AT!CUSTOM="ADBENABLE"?',
                  "AT!TELEN?", "AT!UDPID?", "AT!USBCOMP?"]:
            send(q, 1.0)

    s.close()
    print("DONE")


if __name__ == "__main__":
    main()
