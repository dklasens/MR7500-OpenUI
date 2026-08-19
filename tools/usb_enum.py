import usb.core, usb.backend.libusb1, ctypes

DLL = r"C:\Users\david\AppData\Roaming\Python\Python314\site-packages\libusb\_platform\windows\x86_64\libusb-1.0.dll"
be = usb.backend.libusb1.get_backend(find_library=lambda x: DLL)
if be is None:
    print("backend None"); raise SystemExit(1)
devs = list(usb.core.find(find_all=True, backend=be))
print("num devices:", len(devs))
for d in devs:
    print(hex(d.idVendor), hex(d.idProduct))
