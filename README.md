# Netgear Nighthawk M7 Ultra (MR7500, Telstra) â€” Pentest / Root Access Notes

Personal security research on an **owned** device: Netgear Nighthawk M7 Ultra mobile
hotspot, Telstra (AU) variant. Goal: gain a **root shell / ADB** access.

### Gaining shell / ADB on the M7 Ultra — the short version

The M7 Ultra (SDX75) is a Sierra-Wireless-derived OpenWrt device. There are three
theoretical doors to a shell; Telstra has welded two of them shut in the running OS,
while the third (the bootloader) turns out to be wide open:

1. **Runtime AT / web enablers — BLOCKED.** The device exposes an unauthenticated AT
   console (`telnet :5510`) and a web admin API, and it can be engineer-unlocked
   (`AT!OPENLOCK` + Sierra keygen, §2.2). But every command that would actually spawn
   a shell or ADB is hardened off: the `AT!TELEN` (telnetd) and `AT!UDPID=68E2` (ADB
   composite) setters return `ERROR`, `AT!CUSTOM="ADBENABLE"/"TELNETENABLE"` are
   accepted but inert, and ADB is suppressed at the USB-composition level
   (`sys.usb.config` never initialises the ADB endpoints).
2. **Fastboot bootloader — OPEN (the win).** `AT!RECOVERYHOLD` drops the device into a
   fastboot mode reporting `unlocked:yes`, `secure:no` and `Device critical unlocked:
   true` — i.e. the partitions (incl. `system`/`boot`) are flashable (§2.4).
3. **Therefore the working route is flash-based:** unpack the `system` image, patch the
   rootfs so a root shell starts unconditionally (strip the `bsinfo -s -n` gate in
   `/etc/init.d/telnetd`, relax SELinux, and/or start `adbd` + add ADB to the USB
   composition), repack, and flash a **same-version** image over fastboot. Root telnet
   (`:23`) and/or ADB then come up on boot.

> Status (2026-08-19): **Bootloader is fastboot-UNLOCKED and fully flashable.**
> Runtime shell/ADB enablers are hardened off by Telstra; the remaining work is sourcing
> the NTGX75 firmware to patch and flash (it is not public, and fastboot cannot read
> partitions).

---

## 1. Target / device facts

| Field | Value |
|---|---|
| Model | MR7500 ("Nighthawk M7 Ultra") |
| SKU | `MR7500-1TLAUS` (Telstra AU) |
| Platform | Qualcomm SDX75 "Pinnacle" (`sdxpinn`, aarch64) |
| App FW | `NTGX75_10.04.43.00` (buildDate `43.00 sdx7`) |
| Modem FW | `MPSS.DE.5.0.c7-00227-PINNACLES_ALL_PACK-1.101410.2.129472.3` |
| HW rev | 1.0 |
| IMEI | REDACTED_IMEI |
| Serial (label/FSN) | `REDACTED_FSN` |
| Fastboot serialno | `REDACTED_SERIAL` |
| Web server | `httpd/2.7 (Netgear; D86)` |
| Mgmt IP | `192.168.1.1` (USB-C RNDIS tether; host = `192.168.1.4`) |
| USB (normal) | `VID_0846&PID_68E1` (Netgear, RNDIS-only) |
| USB (fastboot) | `VID_18D1&PID_D00D` (Google fastboot, `Class_FF&SubClass_42&Prot_03`) |
| Admin password | (known, user-supplied) |

US sibling = MR7400 (AT&T). Same Sierra-Wireless-derived "NTG" firmware lineage.

---

## 2. Access surfaces discovered

### 2.1 AT command console (telnet 5510) â€” unauthenticated
`telnet 192.168.1.1 5510` gives an AT console (works over the USB tether).
`ATI` â†’ model/FW/IMEI. This is the primary modem control surface.

### 2.2 Engineer + CND unlock (Sierra keygen)
- `AT!OPENLOCK?` â†’ 16-hex challenge.
- Compute response with `tools/sierrakeygen.py` (bkerler/edl) using `-d SDX75`:
  `AT!OPENLOCK="<resp>"` â†’ `OK` â†’ **engineer unlocked** (then `AT!UDPID?` works).
  - SDX75 openlock key idx 28 = `EEB8487EB1A2A9188E7B44CEE624CBF7`.
- `AT!ENTERCND?` **reveals the CND password `A710`**. `AT!ENTERCND="A710"` enters CND
  (but note: entering CND makes `AT!TELEN` unreadable; it persists until reboot).
- `AT!OPENCND?` â†’ challenge; keygen type-2 response â†’ `AT!OPENCND="<resp>"` â†’ OK.

### 2.3 Web UI (admin) + internal API
- Login: `POST /Forms/config` with `token=<secToken>`, `session.password=<admin>`,
  `ok_redirect`, `err_redirect`. `secToken` from `/model.json`.
- Internal API: `GET /api/model.json?internalapi=1` (admin) â†’ 26 sections
  (`cradle`, `custom`, `webd`, `router`, `fota`, `ui`, `wwan`, ...).
  - `custom.hiddenMenuEnabled`, `webd.gcdump` (modem crash-dump leak).
- Config backup: `GET /dui/export.cfg?save=export.cfg` â†’ **plaintext key=value**.
- Config restore: `POST /Forms/Import` (multipart field `config`, `.cfg`).
- APN profiles: `POST /Forms/profile` (`action=create|update|delete`, `profile.*`).
  - Debug-mode trigger in JS: a profile `{name:"testmode", apn:"ntgrdebug"}` sets
    `isDebugMode` (only enables extra `wwan.diagInfo` polling â€” not a shell).

### 2.4 Fastboot bootloader â€” UNLOCKED
- Enter: `AT!RECOVERYHOLD` on the 5510 AT console â†’ device re-enumerates as
  `VID_18D1&PID_D00D` (fastboot). Needs a WinUSB driver (Zadig) on Windows.
- The stock `fastboot.exe` does NOT enumerate it; use `tools/fb_cmd.py`
  (minimal libusb/WinUSB fastboot client) instead.
- `getvar:all` â†’ **`unlocked:yes`, `secure:no`**; `oem device-info` â†’
  `Device unlocked: true`, `Device critical unlocked: true` â†’ **flashable incl. critical**.
- Full partition table captured in `captures/fastboot_getvar_all.txt`
  (`system` ext4 0x1D640000, `boot` 0x3EC0000, `modem`, `cust`, `hdata`, `userrw`, ...).
- **No read support**: `fetch:`/`oem dump`/`oem read`/`oem partinfo` â†’ `unknown command`.
  So partitions cannot be dumped over fastboot.

---

## 3. Telstra hardening (what is blocked in the running OS)

| Attempt | Result |
|---|---|
| `AT!TELEN=1` (enable telnet 23) | **ERROR** â€” setter read-only (`AT!TELEN?`=0) |
| `AT!UDPID=68E2` (ADB composite) | **ERROR** â€” setter blocked |
| `AT!USBCOMP=...` | ERROR (unsupported on SDX75) |
| `AT!CUSTOM="ADBENABLE",1` / `"TELNETENABLE",1` | Accepted (`OK`) but **inert** (no service/USB change after reboot) |
| `AT!CUSTOM="RDENABLE",1` | ERROR (invalid flag) |
| Config `general.factoryTest=true` import | Accepted, rebooted, **no new ports/ADB** |
| ADB over USB (normal mode) | Not enumerated (PID 68E1 = RNDIS only); ADB suppressed via `sys.usb.config` |

Conclusion: Telstra locked the runtime setters; shell/ADB must come from a **flash-based**
route (patch rootfs) now that the bootloader is unlocked.

---

## 4. Open items / next steps

1. **Source NTGX75 firmware** (not public; no mirror; fastboot can't read). Options:
   user-supplied `.secc/.cwe`, community MEGA toolkit (password-protected/dead), or EDL
   dump (needs a signed SDX75 firehose loader â€” not publicly available).
2. Decrypt (try `netgear_fw_decrypt.py` X65 keys; X75 keys unpublished â†’ may need recovery),
   unpack `system` (ext4 on X75), patch `/etc/init.d/telnetd` (strip `bsinfo -s -n` gate)
   + SELinux, repack, flash **same version** via fastboot.
3. **Anti-rollback caution**: never flash an older version than currently running; keep a
   known-good dump + EDL recovery path. Check `AT!SECBOOTCFG?` / `AT!SECBOOTPKHASH?` first.
4. After shell: disable auto-update (`dx -c Oma.DMAccountServerAddress1 ""`), enable ADB via
   `sys.usb.config`/`adbd`, install static OpenSSH.

---

## 5. Inventory

### tools/ (this repo)
- `netgear_at.py` â€” AT console client + TCP port scan.
- `sierrakeygen.py` â€” bkerler/edl Sierra OPENLOCK/OPENCND keygen (SDX75 supported).
- `unlock.py` / `reunlock_state.py` â€” single-session engineer unlock.
- `opencnd.py` â€” CND unlock; `setup_telnet.py`/`telen.py`/`custom_flags.py`/`udpid_adb.py` â€” hardening probes.
- `reset_poll.py` â€” `AT!RESET` + wait-for-reboot.
- `web_login.py` / `dump_internal.py` / `get_config.py` / `import_cfg.py` / `inject_hostname.py` â€” web API + config export/import + injection test.
- `recoveryhold.py` â€” enter fastboot (`AT!RECOVERYHOLD`).
- `usb_enum.py` / `fb_client.py` / `fb_cmd.py` â€” libusb fastboot client (use instead of fastboot.exe).
- `map_endpoints.py` / `map_import.py` / `find_backup.py` / `profile_flow.py` â€” web recon.
- `listener.py` â€” local callback HTTP listener (for injection OOB detection).

### captures/
- `export.cfg` â€” full plaintext config backup.
- `internal_api.json` â€” `/api/model.json?internalapi=1` dump.
- `index_body.html`, `_static_js_script_js`, `_static_js_deps_js`, `_js_NetgearStrings_js` â€” web UI assets.
- `fastboot_getvar_all.txt`, `fastboot_oem_deviceinfo.txt` â€” bootloader state + partition table.

---

## 6. References
- bkerler/edl `sierrakeygen.py` (SDX75 keys), `enableadb.py`.
- leonzdev/mr6500 (NTGX65 root precedent, mods.md, usb.md, filesystem.md).
- 0xBAADF0OD/netgear_mr6400 (netgear-fw-tools, AT README).
- metahumanflash/mr7400-owe-hardening (confirms ADB/root achievable on MR7400/SDX75).
- Whirlpool MR7500 thread (forums.whirlpool.net.au/archive/9z4ymw6y).
- Wireless Joint MR7400 thread (wirelessjoint.com/viewtopic.php?p=30157).
