# MR7500 reboot / boot-mode map

Owned-device research notes (Netgear Nighthawk M7 Ultra / MR7500, Telstra AU,
Qualcomm SDX75 "Pinnacle"). This file maps **how each reboot/mode command behaves**,
**what USB identity and protocol you land in**, **which host tools can talk to that
mode**, and **how to get back out**. It needs no device to read — it is the
consolidated state of what has been probed as of 2026-11-27.

See `README.md` (§2.4 fastboot, §4 firmware sourcing) and the two project memories
`boothold-edl-loader` and `tool-and-loader-paths` for the underlying evidence.

---

## 1. The map at a glance

| Entry command (AT console `telnet :5510`, or fastboot) | Lands in | USB VID:PID (descriptor) | USB class | Protocol | State / usable? | Exit |
|---|---|---|---|---|---|---|
| *(running OS)* | **Normal / APP** | `0846:68E1` (RNDIS) | RNDIS | IP mgmt, AT, web | Full app FW; mgmt on `192.168.1.1` (or `10.0.1.1` after a BOOTHOLD cycle) | — |
| `AT+CFUN=1,1` | Normal (warm reboot) | `0846:68E1` | RNDIS | — | Clean reboot back to APP | — |
| `AT!RESET` | Normal (reset) | `0846:68E1` | RNDIS | — | Clean reboot back to APP | — |
| `AT!RECOVERYHOLD` | **Fastboot** | `18D1:D00D` (Google) | `ff/42/03` | fastboot | `unlocked:yes`, `secure:no`, critical-unlocked → **writable**, but **read-blocked** (no `fetch`/`oem dump`/`max-fetch-size`) | `fastboot reboot` |
| `AT!BOOTHOLD` | **DLOAD download loader** | `0846:68E0` ("MSMPHONE") | `ff/42/03` | HDLC Streaming-DLOAD / DIAG family | **Live but security-locked** — NAKs every command | **power-cycle only** |
| *(none — software-unreachable)* | **EDL 9008 / Sahara** | would be `????:9008` | `ff/ff/ff` | Sahara + Firehose | Not reachable by any AT/fastboot path on this unit | — |

Key takeaways:

- **Two non-normal doors open by software:** fastboot (via `RECOVERYHOLD`) and the
  DLOAD loader (via `BOOTHOLD`). A third, **true EDL 9008/Sahara**, is *not* reachable
  by software here.
- **Fastboot is writable but not readable.** You can flash, but you cannot dump — so
  there is no software path to a known-good backup (the firmware-sourcing blocker).
- **The DLOAD loader is reached but locked.** `BOOTHOLD` genuinely boots a Qualcomm
  download loader, but it rejects every command, so nothing can be read or written
  through it as shipped.

---

## 2. Per-mode detail

### 2.1 Normal / APP mode
- USB `0846:68E1`, RNDIS-only. Management web + AT console (`telnet :5510`,
  unauthenticated) + web admin API.
- The USB *composition* is governed by the **UDPID** NV setting. Current APP,BOOT pair
  is `68E1,68E0`. `AT!UDPID=?` enumerates the compositions the firmware *supports*:
  ```
  APP     BOOT
  68E1,   68E0     <- current: RNDIS app + the locked DLOAD "BOOT" loader
  68E2,   68E0     <- ADB composite
  90DB,   9008     <- DIAG app + TRUE EDL/Sahara 9008  (the prize)
  ```
  The **setter (`AT!UDPID=...`) is hardened off in every unlock state** — normal, CND
  (`AT!ENTERCND="A710"`), engineer (`AT!OPENLOCK`), and engineer+CND all return
  `ERROR`. So `90DB,9008` (which would expose DIAG in APP and real EDL in BOOT) cannot
  be selected over AT.

### 2.2 Fastboot mode — `AT!RECOVERYHOLD`
- Re-enumerates as Google fastboot `18D1:D00D`, interface class `ff/42/03`.
- Reports `unlocked:yes`, `secure:no`, `Device critical unlocked: true` → partitions
  (incl. `system`/`boot`) are flashable.
- **Write-only.** `fetch`, `oem dump`, `oem read`, `oem partinfo`, `max-fetch-size`
  are all absent/unsupported, so the bootloader exposes **no partition-read path**.
- All EDL-door variants from fastboot fail: `oem edl`, `reboot-edl`, `oem reboot-edl`,
  `dload` → `unknown command`; bare `reboot-edl` just warm-reboots to normal.
- Exit: `fastboot reboot`.
- Tooling: official `fastboot.exe` (platform-tools), or `tools/fb_cmd.py`
  (argparse-driven; `--boot IMG` / `--download IMG`, `--fuzz-oem`).

### 2.3 DLOAD download loader — `AT!BOOTHOLD`  ← *"what's the mode called"*
- **Name:** a Qualcomm/Sierra **"boot-and-hold" download loader** running the legacy
  **HDLC "Streaming DLOAD" (DLOAD / Download) protocol** — the same DLOAD/DIAG family
  that QPST/QFIL's classic "Software Download" path and Sierra's own firmware updater
  use. It is **NOT** the newer **EDL 9008 (Sahara + Firehose)** mode, despite both
  being loosely called "EDL" in the wild. (See §3 for why the distinction matters.)
- USB `0846:68E0`, descriptor **"MSMPHONE"** (the classic Qualcomm download descriptor),
  interface class `ff/42/03`.
- Protocol confirmed: **HDLC-framed** (`0x7E` delimiters, CRC-16/X.25). It CRC-parses
  frames and stays responsive to *well-formed* ones, but returns a **fixed NAK
  `0D 16 00 00 00 00`** to every distinct command — DIAG `0x00`, DLOAD/SDLOAD
  unlock `0x0E` / get-security `0x4B` / param `0x07` / nop `0x09`, and all
  Streaming-DLOAD Hello version×feature combos. (`0x0D` is the Streaming-DLOAD ERROR
  opcode; `0x16` the code.) **No unsolicited "hello" → this is not Sahara.**
- **Security-locked:** it wants a *signed* handshake / programmer it is not getting, so
  it honors nothing — not even reset.
- **Fragile:** sending *invalid* data (e.g. fastboot text) **wedges** the loader; a USB
  reset does not clear it. **Only a power-cycle (unplug/replug) exits BOOTHOLD** or
  recovers a wedged loader. Probe only with valid HDLC frames.
- After a BOOTHOLD cycle the device often comes back on **`10.0.1.1`** (tethering),
  not `192.168.1.1`.

### 2.4 True EDL 9008 / Sahara — *not reachable by software here*
- This is the mode the SDX75 firehose `.elf` loaders target (Sahara uploads the
  Firehose programmer, then Firehose does the raw partition read/write). It is the
  path that *would* give a full dump + known-good backup.
- The firmware **supports** it (the `90DB,9008` UDPID row above), but the only software
  switch — the UDPID setter — is locked in all unlock states. So reaching 9008 needs a
  **non-AT path**: a raw NV write (`AT!NVWRITE` in engineer mode — unknown item #,
  risky/brick), flashing the NV/efs partition over fastboot (risky; fastboot can't read
  it first to back up), or **hardware forced-EDL (test points)**. All are higher-risk
  and none has been attempted.

---

## 3. Which Qualcomm tools interface with each mode  ← *"what qualcomm tools interface with it"*

The critical split is **DLOAD/DIAG (the BOOTHOLD loader, 68E0)** vs
**Sahara/Firehose (EDL 9008)** — different protocols, different tools, different host
drivers. Firehose loaders and Sahara flashers **do not apply** to the 68E0 DLOAD mode.

### 3.1 Tools for the DLOAD / DIAG loader (BOOTHOLD, `0846:68E0`)
These speak the HDLC DLOAD/DIAG protocol that this loader uses. All need the
**Qualcomm USB serial / QDLoader (COM-port) driver**, *not* the Zadig WinUSB binding
used for raw libusb probing.

| Tool | Role | Applies to this mode? |
|---|---|---|
| **QPST** (Software Download, EFS Explorer, Service Programming) | Classic Qualcomm download + NV/EFS over DLOAD/DIAG | Yes, protocol-wise — but **blocked** by the loader's lock |
| **QFIL** (Qualcomm Flash Image Loader) | Front-end for both "Flat Build"/DLOAD *and* Sahara/Firehose; its DLOAD path matches here | DLOAD path yes; Firehose path = wrong mode |
| **QXDM / QCAT** | DIAG monitoring & logging (NV, radio) | Only if the loader accepts DIAG — **it NAKs `0x00`**, so no |
| **QDART** | Diagnostic/automation over DIAG | Same as QXDM — gated by the lock |
| **Sierra/Netgear firmware updater** (`.cwe/.spk/.secc`) | The vendor's own download client — *natively* uses this DLOAD boot-and-hold | The intended client; needs the signed/packaged image + vendor handshake |
| **bkerler `qc_diag.py`** (open-source DIAG) | Connects over libusb and speaks DIAG | **Connects** to `0846:68e0`, but loader NAKs `info`/`cmd 00`/`cmd 0a`/`nvread` → `0D 16…` |
| **QCSuper** (open-source DIAG capture) | Cellular-signaling capture over a DIAG COM port | Needs a live DIAG port; not exposed by the locked loader |

Bottom line: the DLOAD-family tools are the *correct* ones for the mode, but the loader
rejects all commands as shipped, so none can actually read/write through it without the
vendor's signed handshake.

### 3.2 Tools for EDL 9008 / Sahara (not reachable by software here)
These are the firehose tools — staged for a future **hardware** EDL entry, useless
until the device is actually in 9008/Sahara:

| Tool | Role |
|---|---|
| **qdl** (`QDL_2.9.1_Win_ARM64\qdl.exe`, native ARM64) | Sahara → Firehose flasher |
| **qil** (`qil_v1.5.1_Windows_ARM64`) | Qualcomm image loader |
| **QPST/QFIL (Sahara/Firehose path)** | GUI emergency download |
| **bkerler `edl.py` / `qdl`** | Open-source Sahara/Firehose (note: does **not** build cleanly on this Win-ARM64/py3.15 box) |
| SDX75 firehose `.elf` programmers | `prog_firehose_sdx7x*.elf`, incl. the `pinnaclesle` one for this chip (+ `hack_firehose_*` auth-bypass variants) |

### 3.3 Driver note
- **DLOAD/DIAG tools (§3.1)** → Qualcomm USB serial / QDLoader driver (a COM port).
- **Raw libusb probing** (what `qc_diag.py` used to confirm the NAK) → WinUSB bound via
  **Zadig**, which on this Win-ARM64 box required test-signing on + Secure Boot off.
- The two bindings are mutually exclusive on the same interface — rebind to switch
  between GUI-tool access and raw-libusb probing.

---

## 4. Practical sequencing

1. **Normal → fastboot:** `AT!RECOVERYHOLD`; flash a same-version patched `system`;
   `fastboot reboot`. (The committed README route — blocked only on sourcing the image.)
2. **Normal → DLOAD probe:** `AT!BOOTHOLD`, talk HDLC only, **power-cycle to exit.**
   Currently a dead end (locked loader); revisit only with the vendor handshake or a
   signed DLOAD package.
3. **Toward true EDL 9008:** no software path — hardware forced-EDL (test points) is the
   realistic route; then the §3.2 firehose stack applies.

> One-line status: **fastboot = open & writable but read-blocked; BOOTHOLD DLOAD loader
> = reached but locked; EDL 9008/Sahara = supported by firmware but software-gated.**
