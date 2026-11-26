"""Minimal libusb/WinUSB fastboot client for the MR7500 (VID_18D1&PID_D00D).

Stock fastboot.exe does not enumerate this device; this talks the fastboot
protocol directly over the bulk endpoints.

Modes:
  # raw commands (default, back-compatible with the old positional form)
  python fb_cmd.py getvar:all "oem device-info"

  # vector 2.1 - download an image to RAM and jump to it (no flash, reversible)
  python fb_cmd.py --boot boot_patched.img
  python fb_cmd.py --download payload.img        # download only, don't boot

  # vector 2.4 - fuzz the OEM/flashing command handler
  python fb_cmd.py --fuzz-oem                     # read-only probes only
  python fb_cmd.py --fuzz-oem --aggressive        # also send state-changing cmds

Env:
  LIBUSB_DLL   override path to libusb-1.0.dll
"""
import usb.core, usb.backend.libusb1, sys, os, argparse, time

def _resolve_dll():
    """Locate a libusb-1.0.dll: env override, then the pip `libusb` package's
    arch-appropriate copy (handles x86_64 / arm64 / x86), then a legacy path."""
    env = os.environ.get("LIBUSB_DLL")
    if env and os.path.exists(env):
        return env
    try:
        import libusb, platform
        base = os.path.join(os.path.dirname(libusb.__file__), "_platform", "windows")
        sub = {"arm64": "arm64", "aarch64": "arm64", "amd64": "x86_64",
               "x86_64": "x86_64", "x86": "x86"}.get(platform.machine().lower(), "x86_64")
        p = os.path.join(base, sub, "libusb-1.0.dll")
        if os.path.exists(p):
            return p
    except Exception:
        pass
    legacy = r"C:\Users\david\AppData\Roaming\Python\Python314\site-packages\libusb\_platform\windows\x86_64\libusb-1.0.dll"
    return legacy if os.path.exists(legacy) else None


DLL = _resolve_dll()
# Default = the AT!RECOVERYHOLD fastboot (Google VID). The AT!BOOTHOLD download
# mode enumerates as 0846:68E0 ("MSMPHONE", also fastboot-class FF/42/03) and can
# be targeted with --vid 0x0846 --pid 0x68E0 (or FB_VID/FB_PID env).
VID = int(os.environ.get("FB_VID", "0x18D1"), 16)
PID = int(os.environ.get("FB_PID", "0xD00D"), 16)

ep_out = ep_in = None


def connect():
    global ep_out, ep_in
    be = usb.backend.libusb1.get_backend(find_library=lambda x: DLL) if DLL else None
    dev = usb.core.find(idVendor=VID, idProduct=PID, backend=be)
    if dev is None:
        print("device not found (looking for %04X:%04X — is it in fastboot/download mode with a WinUSB driver bound?)" % (VID, PID))
        raise SystemExit(1)
    cfg = dev.get_active_configuration()
    intf = cfg[(0, 0)]
    ep_out = [e for e in intf if usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT][0]
    ep_in = [e for e in intf if usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN][0]
    try:
        dev.set_configuration()
    except Exception:
        pass
    try:
        usb.util.claim_interface(dev, intf.bInterfaceNumber)
    except Exception:
        pass
    return dev


def read_pkt(timeout=5000):
    return ep_in.read(ep_in.wMaxPacketSize, timeout).tobytes().decode(errors="replace")


def cmd(c, timeout=5000):
    """Send one fastboot command; collect INFO lines until the final status."""
    ep_out.write(c.encode(), timeout)
    out = []
    while True:
        d = read_pkt(timeout)
        out.append(d)
        if not d.startswith("INFO"):
            break
    return out


def download(data, timeout=30000):
    """fastboot 'download:' phase. Returns (ok, log_lines)."""
    log = []
    ep_out.write(("download:%08x" % len(data)).encode(), timeout)
    resp = read_pkt(timeout)
    log.append(resp)
    if not resp.startswith("DATA"):
        return False, log  # handler rejected the size / command
    chunk = 128 * 1024
    for i in range(0, len(data), chunk):
        ep_out.write(data[i:i + chunk], timeout)
    while True:
        d = read_pkt(timeout)
        log.append(d)
        if not d.startswith("INFO"):
            break
    return log[-1].startswith("OKAY"), log


def do_boot(path):
    data = open(path, "rb").read()
    print("== download:%08x (%d bytes from %s) ==" % (len(data), len(data), path))
    ok, log = download(data)
    for l in log:
        print("  " + l.strip())
    if not ok:
        print("  download not accepted; NOT sending boot:")
        return
    print("== boot ==")
    try:
        for l in cmd("boot"):
            print("  " + l.strip())
    except Exception as e:
        print("  (USB dropped after 'boot' \u2014 expected if the image booted) " + repr(e))


def do_download(path):
    data = open(path, "rb").read()
    print("== download:%08x (%d bytes from %s) ==" % (len(data), len(data), path))
    ok, log = download(data)
    for l in log:
        print("  " + l.strip())
    print("  result:", "OKAY" if ok else "FAIL")


# (word, sends_raw, changes_state)
#   sends_raw=False -> prefixed with "oem "
#   changes_state=True -> only sent with --aggressive (reboots/EDL/flashing)
OEM_FUZZ = [
    ("device-info", False, False),
    ("edl", False, True),
    ("reboot-edl", False, True),
    ("console", False, False),
    ("uart", False, False),
    ("at", False, False),
    ("shell", False, False),
    ("adb", False, False),
    ("enable-adb", False, False),
    ("telnet", False, False),
    ("diag", False, False),
    ("env", False, False),
    ("nvdump", False, False),
    ("ramdump", False, False),
    ("dump", False, False),
    ("read", False, False),
    ("partinfo", False, False),
    ("get_unlock_data", False, False),
    ("select-display-panel", False, False),
    ("unlock", False, True),
    ("lock", False, True),
    # top-level (not oem-prefixed)
    ("flashing get_unlock_ability", True, False),
    ("flashing unlock", True, True),
    ("flashing lock", True, True),
    ("continue", True, True),
    ("reboot-bootloader", True, True),
]


def do_fuzz(aggressive=False):
    print("== OEM/flashing command fuzz (aggressive=%s) ==" % aggressive)
    for word, raw, state in OEM_FUZZ:
        full = word if raw else ("oem " + word)
        if state and not aggressive:
            print("-- skip (state-changing, use --aggressive): " + full)
            continue
        print("== " + full + " ==")
        try:
            for line in cmd(full):
                print("  " + line.strip())
        except Exception as e:
            # a device drop here is itself a signal (command was accepted and acted on)
            print("  ERR " + repr(e))
            if state:
                print("  (device likely rebooted/changed state \u2014 reconnect before continuing)")
                break


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="MR7500 libusb fastboot client")
    ap.add_argument("commands", nargs="*", help="raw fastboot commands, e.g. getvar:all 'oem device-info'")
    ap.add_argument("--boot", metavar="IMG", help="download IMG to RAM and jump to it (vector 2.1)")
    ap.add_argument("--download", metavar="IMG", help="download IMG only (no boot)")
    ap.add_argument("--fuzz-oem", action="store_true", help="enumerate the OEM command handler (vector 2.4)")
    ap.add_argument("--aggressive", action="store_true", help="with --fuzz-oem, also send state-changing commands")
    ap.add_argument("--timeout", type=int, default=5000, help="per-transfer timeout ms (default 5000)")
    ap.add_argument("--vid", help="USB VID override in hex (e.g. 0x0846 for the AT!BOOTHOLD download mode)")
    ap.add_argument("--pid", help="USB PID override in hex (e.g. 0x68E0)")
    a = ap.parse_args()

    if a.vid:
        VID = int(a.vid, 16)
    if a.pid:
        PID = int(a.pid, 16)
    connect()

    if a.boot:
        do_boot(a.boot)
    elif a.download:
        do_download(a.download)
    elif a.fuzz_oem:
        do_fuzz(a.aggressive)
    else:
        for c in (a.commands or ["getvar:all"]):
            print("== " + c + " ==")
            try:
                for line in cmd(c, a.timeout):
                    print("  " + line.strip())
            except Exception as e:
                print("  ERR " + repr(e))
