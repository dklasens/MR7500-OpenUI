# Plan v2 — Additional ADB / Shell Vectors (repo review, 2026-08-19)

Follow-up to the README status. Review of the repo (tools, captures, web UI JS,
`export.cfg`, fastboot captures) turned up gaps in the current plan plus several
unexplored vectors, prioritized below.

---

## 1. Gaps in the current plan

1. **`Verity mode: true`** (`captures/fastboot_oem_deviceinfo.txt:2`) is not
   addressed anywhere. If dm-verity covers `system`, a patched rootfs will fail
   at mount even though it flashes fine. Whatever route is taken, plan to also
   strip/replace the verity args in `boot`, or verify the gate is cosmetic.
2. **No known-good dump + no EDL firehose** = any flash experiment is one-way.
   This pushes toward zero-write experiments first (see vectors 1, 2, 4, 6).
3. **`ntgfota` (0x37E80000, ~894 MB)** is the FOTA staging partition — that is
   the delivery mechanism a real update would use, and also where the device
   itself would fetch the stock image that cannot otherwise be sourced.

---

## 2. Unexplored vectors (highest value first)

### 2.1 `fastboot boot` — never probed
Only `fetch`/`oem dump`/`oem read`/`oem partinfo` were tried. Qualcomm
ABL/UEFI fastboot commonly implements `boot:` even when read commands are
stripped. If it works: boot a kernel+initramfs **without flashing anything**
→ instant root shell + `dd` every partition over RNDIS → solves both the shell
*and* the firmware-sourcing problem in one step.

- Extend `tools/fb_cmd.py` with `download:` + `boot:`.
- Even the error response is informative.

### 2.2 FOTA URL capture
Trigger "check for update" (`fota.fwupdater.chknow` via `/Forms/config`) while
capturing on the RNDIS interface. Netgear/Telstra FOTA endpoints typically hand
out the full `.cwe/.secc` once the URL is known — the legit way to get the
`NTGX75_10.04.43.00_TELSTRA` package.

- Also check Netgear EU/US support for the unlocked MR7500 (`MR7500-100EUS`)
  and MR7400 — same NTGX75 platform. Even without cross-flashing, an MR7400
  image gives the rootfs layout, the `bsinfo` telnetd gate, and a donor `boot`
  partition for vector 2.1.

### 2.3 Config-import injection — only `router.hostName` tested
Untested keys that land in daemon config files (all present in
`captures/export.cfg`):

| Key | Sink |
|---|---|
| `foIpv4Targets` | failover keepalive — periodically pinged via shell (the classic one) |
| `mediaserver.dlnaFriendlyName` | minidlna (DLNA is enabled) |
| `ready.deviceShare.workgroupName` / `networkDeviceName` | smb.conf |
| `wifi.SSID` / `wifi.aux.SSID` | hostapd |
| `captiveportal.redirectUrl` | captive portal |
| `profEntry` APN username/password | chat-script land |
| `router.ipPassThroughHostPcName` | passthrough host config |

Also vary payload style:

- newline (`%0A`) key-smuggling,
- backticks, `;`, and unencoded `$( )` (exports are URL-decoded on import,
  per the `%2E` dots in `export.cfg`).

Plus flip feature flags via import: `ui.demoMode`, `custom.hiddenMenuEnabled`,
`webd.ownerModeEnabled`, `sms.sendEnabled=true` (then probe
`/Forms/smsSendMsg` receiver/text).

### 2.4 Fastboot OEM command enumeration
Only 4 oem commands tried. Fuzz the OEM handler with `fb_cmd.py`:

- `oem edl`, `oem reboot-edl`, `oem console`, `oem uart`, `oem at`,
  `oem shell`
- plus `continue` / `reboot-bootloader` / `flashing get_unlock_ability`.

An `oem edl` path would also open the EDL door.

### 2.5 Full TCP scan
`netgear_at.py --scan` checks 14 ports. Run all 65535 + UDP 1900
(SSDP/DLNA is live) + 5353, and IPv6 link-local. The Insight agent
(v25.11.53.1, enabled) is another listening daemon worth finding.

### 2.6 UART on the PCB
No hardware vector is mentioned anywhere in the repo. SDX75 boards expose UART
pads; with a UEFI-based boot chain (`kernel:uefi`) there is a real chance of a
UEFI shell or at least boot logs. Read-only probing, fully independent of the
flash risk.

### 2.7 AT surface completeness
- Save the full `AT!CUSTOM?` flag list to `captures/` (`custom_flags.py`
  prints it but it is not archived) — the flag inventory may reveal non-inert
  knobs (e.g. diag port enables).
- Run the open-item `AT!SECBOOTCFG?` / `AT!SECBOOTPKHASH?` before any flash.
- Consider SMS-AT passthrough (receive path works; some Sierra builds accept
  AT commands by SMS).

### 2.8 Mine the MR7400 precedent for the exact delta
metahumanflash/mr7400 confirms ADB on the same platform — determine *how*
(AT-setter vs firmware image):

- If it's an image, the same path is inherited.
- If it's AT commands, the diff tells precisely which NV/carrier flag Telstra
  neutered — which is what a patched `system` must flip.

---

## 3. Priority order

1. **Vector 2.1 (`fastboot boot`)** — free, reversible, and collapses the whole
   "source firmware → patch → flash" chain if supported.
2. **Vectors 2.2 + 2.3** — cheap to run in parallel.
3. Vectors 2.4, 2.5 — mechanical fuzzing/scanning.
4. Vectors 2.6, 2.7, 2.8 — background research / hardware.

## 4. Tooling TODO

- [x] `fb_cmd.py`: `download:` + `boot:` support (vector 2.1) — `--boot IMG` / `--download IMG`
- [x] `fb_cmd.py`: OEM command fuzz mode (vector 2.4) — `--fuzz-oem [--aggressive]`
- [x] Injection sweep script for untested config keys (vector 2.3) — `tools/inject_sweep.py` (dry-run by default, `--fire` to import)
- [x] Full-port TCP/UDP scanner (vector 2.5) — `tools/full_scan.py` (65535 TCP + SSDP/mDNS + optional IPv6)
- [x] Archive `AT!CUSTOM?` full flag list to `captures/` (vector 2.7) — `tools/at_capture.py --preset custom`
- [x] `AT!SECBOOTCFG?` / `AT!SECBOOTPKHASH?` capture (README §4 open item 3) — `tools/at_capture.py --preset secboot`

### 4.1 Notes on the new tooling

- **`fb_cmd.py`** is now argparse-driven but still back-compatible with the old
  positional form (`python fb_cmd.py getvar:all "oem device-info"`). `--boot`
  implements the full `download:%08x` → DATA → bulk-write → `boot` handshake, so
  2.1 can be tried the moment a donor `boot` image (e.g. from an MR7400) exists —
  RAM-only, nothing flashed. The OEM fuzz list splits read-only probes from
  state-changing ones (`oem edl`, `flashing unlock`, `continue`, …); the latter
  are skipped unless `--aggressive`, and the loop stops on the first device drop.
- **`inject_sweep.py`** payloads are OOB-callback only (`wget`/`curl` to
  `tools/listener.py`); no destructive commands. Values are URL-encoded so the
  import-time URL-decode restores `$( )`, backticks, `;`, `|` and smuggled
  newlines (`%0A`) at the sink. Dry-run writes every crafted `.cfg` for review;
  `--fire` imports and reboot-polls between cases. The feature-flag flips
  (`ui.demoMode`, `webd.ownerModeEnabled`, `sms.sendEnabled`, …) are intentionally
  left out of the automated sweep — set those deliberately with `import_cfg.py`.
- **`full_scan.py`** is a threaded connect scan; raise `--workers` for speed, and
  pass `--ipv6 "<addr>%<zone>"` once the device's link-local address is known.
