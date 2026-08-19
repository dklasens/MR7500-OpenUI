import usb.core, usb.backend.libusb1, sys, time

DLL = r"C:\Users\david\AppData\Roaming\Python\Python314\site-packages\libusb\_platform\windows\x86_64\libusb-1.0.dll"
VID, PID = 0x18d1, 0xd00d
be = usb.backend.libusb1.get_backend(find_library=lambda x: DLL)
dev = usb.core.find(idVendor=VID, idProduct=PID, backend=be)
if dev is None:
    print("device not found"); raise SystemExit(1)

cfg = dev.get_active_configuration()
intf = cfg[(0, 0)]
ep_out = [e for e in intf if usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT][0]
ep_in = [e for e in intf if usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN][0]
print("endpoints: out=0x%02x in=0x%02x" % (ep_out.bEndpointAddress, ep_in.bEndpointAddress))

try:
    dev.set_configuration()
except Exception as e:
    print("set_configuration:", repr(e))
try:
    usb.util.claim_interface(dev, intf.bInterfaceNumber)
except Exception as e:
    print("claim:", repr(e))

def cmd(c, timeout=3000):
    ep_out.write(c.encode(), timeout)
    out = []
    while True:
        data = ep_in.read(ep_in.wMaxPacketSize, timeout).tobytes().decode(errors="replace")
        out.append(data)
        if not data.startswith("INFO"):
            break
    return out

for c in ["getvar:version", "getvar:product", "getvar:max-download-size"]:
    try:
        r = cmd(c)
        print(c, "->", r)
    except Exception as e:
        print(c, "ERR", repr(e))
