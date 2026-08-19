import usb.core, usb.backend.libusb1, sys

DLL = r"C:\Users\david\AppData\Roaming\Python\Python314\site-packages\libusb\_platform\windows\x86_64\libusb-1.0.dll"
VID, PID = 0x18d1, 0xd00d
be = usb.backend.libusb1.get_backend(find_library=lambda x: DLL)
dev = usb.core.find(idVendor=VID, idProduct=PID, backend=be)
cfg = dev.get_active_configuration(); intf = cfg[(0,0)]
ep_out = [e for e in intf if usb.util.endpoint_direction(e.bEndpointAddress)==usb.util.ENDPOINT_OUT][0]
ep_in  = [e for e in intf if usb.util.endpoint_direction(e.bEndpointAddress)==usb.util.ENDPOINT_IN][0]
try: dev.set_configuration()
except Exception: pass
try: usb.util.claim_interface(dev, intf.bInterfaceNumber)
except Exception: pass

def cmd(c, timeout=5000):
    ep_out.write(c.encode(), timeout)
    out=[]
    while True:
        d = ep_in.read(ep_in.wMaxPacketSize, timeout).tobytes().decode(errors="replace")
        out.append(d)
        if not d.startswith("INFO"): break
    return out

for c in sys.argv[1:]:
    print("== " + c + " ==")
    try:
        for line in cmd(c): print("  " + line)
    except Exception as e:
        print("  ERR", repr(e))
