# owon-hds200

Python interface for the **OWON HDS200 series** handheld oscilloscopes on Linux — including the **Hanmatek HO52S**, which runs OWON HDS200 firmware.

Tested on:
- **Hanmatek HO52S** — OWON firmware V8.0.1, USB VID:PID `5345:1234`
- **Host:** Ubuntu 24.04, Python 3.12, OptiPlex 9010 / Chuwi B14 Air

---

## Contents

- [Hardware Overview](#hardware-overview)
- [USB Modes](#usb-modes)
- [Linux Setup](#linux-setup)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Scripts](#scripts)
  - [capture.py](#capturepy)
  - [stream.py](#streampy)
  - [fft.py](#fftpy)
  - [log.py](#logpy)
  - [compare.py](#comparepy)
  - [siggen.py](#siggenpy)
  - [dmm.py](#dmmpy)
  - [terminal.py](#terminalpy)
- [Python Library](#python-library)
- [SCPI Command Reference](#scpi-command-reference)
- [Protocol Notes](#protocol-notes)
- [Waveform Data Format](#waveform-data-format)
- [Voltage Scaling](#voltage-scaling)
- [Known Limitations](#known-limitations)
- [Windows](#windows)
- [Troubleshooting](#troubleshooting)

---

## Hardware Overview

The Hanmatek HO52S is a 3-in-1 handheld instrument:

| Function | Spec |
|---|---|
| Oscilloscope | 50 MHz bandwidth, 2 channels, 62.5 MSa/s |
| Multimeter | True-RMS, 20,000 counts, DC/AC V/A, Ω, capacitance, diode |
| Signal Generator | 25 MHz max, sine/square/ramp/pulse + arbitrary waveforms |
| Display | 3.5" TFT, 320×240 |
| Memory | 4K or 8K samples per channel |
| Power | 18650 Li-ion, ~6 hours, USB-C charging |
| PC Interface | USB-C (HID mode for SCPI, MSC mode for file transfer) |

The HO52S is manufactured by Hanmatek but runs OWON HDS200-series firmware. All SCPI commands follow the HDS200 protocol.

---

## USB Modes

The scope has two USB modes. You must use **HID mode** for SCPI/Python control.

| Mode | USB IDs | What appears on Linux | Use for |
|---|---|---|---|
| **MSC** (default) | `28e9:0285` GDMicroelectronics | `/dev/sdX` (USB flash drive) | Copying saved CSVs/BMPs off scope |
| **HID** | `5345:1234` Owon PDS6062T | `/dev/ttyUSB0` | SCPI control, Python scripts |

### Switching to HID mode

On the scope:

```
System → [F4] Page 2 → [F1] HID
```

The scope will reconnect. Confirm with:

```bash
lsusb | grep -i "5345\|owon"
# Should show: ID 5345:1234 Owon PDS6062T Oscilloscope

ls /dev/ttyUSB*
# Should show: /dev/ttyUSB0
```

### Switching back to MSC mode (file transfer)

```
System → [F4] Page 2 → [F1] MSC
```

In MSC mode the scope mounts as a USB flash drive containing saved waveforms (CSV) and screenshots (BMP).

---

## Linux Setup

### 1. Add yourself to the dialout group

```bash
sudo usermod -aG dialout $USER
```

Log out and back in (or run `newgrp dialout` in the current terminal).

Verify:

```bash
groups | grep dialout
```

### 2. Confirm the port appears

With scope in HID mode:

```bash
ls /dev/ttyUSB*
# /dev/ttyUSB0
```

---

## Installation

### Clone the repo

```bash
git clone https://github.com/JohnDWilbourn/owon-hds200.git
cd owon-hds200
```

### Create a virtual environment (recommended)

```bash
python3 -m venv venv
source venv/bin/activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

Or install only what you need:

```bash
pip install pyserial              # minimum (SCPI only)
pip install pyserial matplotlib   # capture, stream, compare
pip install pyserial matplotlib numpy  # FFT analysis
```

### Optional: install as a package

```bash
pip install -e .
```

---

## Quick Start

```bash
# Confirm scope is connected
python3 -c "from owonhds import HDS200; s=HDS200(); print(s.identify())"

# Capture a waveform
python3 scripts/capture.py

# Live stream
python3 scripts/stream.py

# FFT analysis
python3 scripts/fft.py

# Interactive SCPI terminal
python3 scripts/terminal.py
```

---

## Scripts

All scripts accept `--help` for full option lists.

---

### capture.py

Single waveform capture. Saves timestamped CSV and PNG plot.

```bash
python3 scripts/capture.py
python3 scripts/capture.py --port /dev/ttyUSB0 --out ~/Oscilloscope
python3 scripts/capture.py --ch 2
python3 scripts/capture.py --both          # CH1 and CH2
python3 scripts/capture.py --no-plot       # CSV only
```

**Output files:**
```
20260419_143022_CH1_waveform.csv
20260419_143022_CH1_waveform.png
```

The CSV contains `time_s,voltage_V` columns. The PNG is a dark-themed waveform plot with measurements in the title.

---

### stream.py

Live continuous capture with real-time updating plot. Requires an interactive display (X11 or Wayland).

```bash
python3 scripts/stream.py
python3 scripts/stream.py --interval 0.5    # update every 0.5s
python3 scripts/stream.py --ch 1 --interval 2.0
```

Press **Ctrl+C** to stop.

> **Note:** The HDS200 SCPI interface is not fast — each full capture cycle takes ~3–5 seconds due to the open/close-per-command protocol. The `--interval` sets the minimum time between updates.

---

### fft.py

Frequency spectrum analysis. Captures a waveform and displays time-domain and frequency-domain plots side by side. Saves both a waveform CSV and an FFT CSV.

```bash
python3 scripts/fft.py
python3 scripts/fft.py --window hann        # default
python3 scripts/fft.py --window blackman    # better sidelobe rejection
python3 scripts/fft.py --window rectangular # no windowing
python3 scripts/fft.py --out ~/Oscilloscope
```

**Output files:**
```
20260419_143022_CH1_fft.csv     # frequency_Hz, magnitude_dBV
20260419_143022_CH1_fft.png     # dual-panel plot
```

The script prints the top 5 spectral components to the terminal.

---

### log.py

Timed interval measurement logger. Captures scope measurements at a set interval and writes them to a CSV log. Optionally saves full waveform data per capture.

```bash
# Log measurements every 5 seconds indefinitely
python3 scripts/log.py

# Log every 1 second for 1 hour
python3 scripts/log.py --interval 1 --duration 3600

# Log 100 captures then stop
python3 scripts/log.py --count 100 --interval 2

# Also save waveform CSVs per capture
python3 scripts/log.py --interval 5 --waveforms --out ~/Oscilloscope
```

**Log CSV columns:**
```
timestamp, elapsed_s, frequency_Hz, period_s, vpp_V, vamp_V,
vmax_V, vmin_V, vaverage_V, trigger_status, timebase, scale, probe, coupling
```

Press **Ctrl+C** to stop. The partial log is always saved.

---

### compare.py

Capture multiple waveforms and overlay them on a single plot. Useful for measuring jitter, comparing signal stability, or A/B testing.

```bash
# Capture 5 waveforms live and compare
python3 scripts/compare.py --count 5

# Capture 10 with 2-second interval
python3 scripts/compare.py --count 10 --interval 2.0

# Compare existing CSV files
python3 scripts/compare.py --files wave1.csv wave2.csv wave3.csv
```

The comparison plot shows all waveforms overlaid with a statistics panel showing mean/min/max/σ for Vpp and frequency.

---

### siggen.py

Control the built-in signal generator (HO52S/HO102S models only). Connect your circuit to the **GEN Out** port on the scope.

```bash
# 1 kHz sine wave at 1.5 Vpp
python3 scripts/siggen.py --wave SINE --freq 1000 --amp 1.5

# 10 kHz square wave at 3.3 Vpp with 1.65V offset (0–3.3V logic level)
python3 scripts/siggen.py --wave SQUare --freq 10000 --amp 3.3 --offset 1.65

# 500 Hz ramp at 2 Vpp
python3 scripts/siggen.py --wave RAMP --freq 500 --amp 2.0

# Check current settings
python3 scripts/siggen.py --status

# Turn output off
python3 scripts/siggen.py --off
```

**Available waveforms:** `SINE`, `SQUare`, `RAMP`, `PULSe`

**Frequency range:** DC to 25 MHz

---

### dmm.py

Read and log the built-in digital multimeter. The scope must be in **Multimeter mode** (press Mode button to switch).

```bash
# Single DC voltage reading
python3 scripts/dmm.py --func DCV

# Log AC voltage every second
python3 scripts/dmm.py --func ACV --log --interval 1

# Log resistance every 2 seconds, 50 readings
python3 scripts/dmm.py --func RES --log --interval 2 --count 50

# Log DC current to specific directory
python3 scripts/dmm.py --func DCA --log --out ~/Oscilloscope
```

**Available functions:**

| Code | Measurement |
|---|---|
| `DCV` | DC Voltage |
| `ACV` | AC Voltage |
| `DCA` | DC Current |
| `ACA` | AC Current |
| `RES` | Resistance |
| `DIOD` | Diode voltage |
| `CAP` | Capacitance |
| `BEEP` | Continuity |

> **Note:** DMM SCPI requires activating SCPI mode (`:SCPI:DISP?` command). The script does this automatically, but the scope must be in Multimeter mode for DMM commands to respond.

---

### terminal.py

Interactive SCPI terminal with tab completion and command history.

```bash
python3 scripts/terminal.py
```

```
hds200> *IDN?
  ,HO52S,2234686,V8.0.1

hds200> :CH1:SCALE?
  500mV

hds200> :MEASurement:CH1:FREQuency?
  F=1.000kHz

hds200> :DATa:WAVe:SCReen:HEAD?
  {"timebase":{"scale":"500us",...},...}

hds200> status
  Device     : ,HO52S,2234686,V8.0.1
  Trigger    : TRIG
  Timebase   : 500us
  CH1 scale  : 500mV
  ...

hds200> save
  Save to file: /home/john/Oscilloscope/response.json

hds200> exit
```

**Tab completion** works for all known SCPI commands.  
**Command history** is saved to `~/.hds200_history`.  
**Warning system** flags commands known to crash the firmware.

---

## Python Library

The `owonhds` package can be used directly in your own scripts.

```python
from owonhds import HDS200

scope = HDS200(port="/dev/ttyUSB0")

# Check connection
print(scope.identify())           # ,HO52S,2234686,V8.0.1
print(scope.is_connected())       # True

# Scope settings
print(scope.get_timebase())       # 500us
print(scope.get_channel_scale())  # 500mV
print(scope.get_channel_probe())  # 10X

# Set settings
scope.set_timebase("1ms")
scope.set_channel_scale("1V")
scope.set_channel_coupling("DC")

# Measurements
meas = scope.measure_all(ch=1)
print(meas)
# {
#   'frequency': 1000.0,
#   'period': 0.001,
#   'vpp': 3.28,
#   'vamp': 3.2,
#   'vmax': 1.68,
#   'vmin': -1.62,
#   'vaverage': 0.015
# }

# Waveform capture
waveform = scope.get_waveform(ch=1, normalize=True)
print(waveform)
# Waveform(ch=1, samples=600, vpp=3.2800V, normalized=True)

print(f"Vpp: {waveform.vpp:.4f} V")
print(f"Vmax: {waveform.vmax:.4f} V")
print(f"Samples: {len(waveform)}")
print(f"Duration: {waveform.duration*1000:.2f} ms")

# Save
waveform.save_csv("output.csv")

# Numpy arrays
times, voltages = waveform.to_numpy()

# Signal generator
scope.siggen_set_waveform("SINE")
scope.siggen_set_frequency(1000)
scope.siggen_set_amplitude(1.5)
scope.siggen_output(True)

# Raw SCPI
resp = scope.query(":TRIGger:STATus?")
print(resp)  # TRIG
```

---

## SCPI Command Reference

Commands confirmed working on HDS200 firmware V8.0.1:

### Confirmed Responding

| Command | Response | Notes |
|---|---|---|
| `*IDN?` | `,HO52S,2234686,V8.0.1` | Identity |
| `:CH1:DISP?` | `ON` / `OFF` | Channel display state |
| `:CH1:SCALE?` | `500mV` | Vertical scale |
| `:CH1:OFFSET?` | `0.00` | Vertical offset (divisions) |
| `:CH1:COUP?` | `AC` / `DC` / `GND` | Coupling mode |
| `:CH1:PROBE?` | `1X` / `10X` | Probe attenuation |
| `:HOR:SCALE?` | `500us` | Timebase |
| `:HOR:OFFSET?` | `0.00` | Horizontal offset |
| `:ACQ:MODE?` | `SAMPle` | Acquire mode |
| `:ACQ:DEPMEM?` | `4K` | Memory depth |
| `:TRIGger:STATus?` | `AUTO` / `TRIG` / `STOP` | Trigger state |
| `:DATa:WAVe:SCReen:HEAD?` | JSON string | Scope state + channel info |
| `:DATa:WAVe:SCReen:CH1?` | Binary blob | Raw waveform bytes |
| `:MEASurement:CH1:FREQuency?` | `F=1.000kHz` | Frequency |
| `:MEASurement:CH1:PERiod?` | `T=1000.0us` | Period |
| `:MEASurement:CH1:PKPK?` | `Vpp=3.280V` | Peak-to-peak |
| `:MEASurement:CH1:VAMP?` | `Va=3.200V` | Amplitude |
| `:MEASurement:CH1:MAX?` | `Ma=1.640V` | Maximum |
| `:MEASurement:CH1:MIN?` | `Mi=-1.640V` | Minimum |
| `:MEASurement:CH1:AVERage?` | `V=4.800mV` | Average |
| `:FUNCtion?` | `SINE` | Signal generator waveform |
| `:FUNCtion:FREQuency?` | `1.000000e+03` | Siggen frequency |
| `:FUNCtion:AMPLitude?` | `1.500000e+00` | Siggen amplitude |

### Set Commands

| Command | Example | Notes |
|---|---|---|
| `:CH1:DISPlay <ON\|OFF>` | `:CH1:DISPlay ON` | |
| `:CH1:COUPling <AC\|DC\|GND>` | `:CH1:COUPling DC` | |
| `:CH1:PROBe <1X\|10X\|100X\|1000X>` | `:CH1:PROBe 10X` | Must match physical switch |
| `:CH1:SCALe <scale>` | `:CH1:SCALe 500mV` | See valid values below |
| `:CH1:OFFSet <n>` | `:CH1:OFFSet 0` | Integer divisions, -200 to 200 |
| `:HORIzontal:SCALe <scale>` | `:HORIzontal:SCALe 1ms` | See valid values below |
| `:ACQuire:MODE <SAMPle\|PEAK>` | `:ACQuire:MODE SAMPle` | |
| `:ACQuire:DEPMem <4K\|8K>` | `:ACQuire:DEPMem 4K` | |
| `:FUNCtion <wave>` | `:FUNCtion SINE` | SINE, SQUare, RAMP, PULSe |
| `:FUNCtion:FREQuency <Hz>` | `:FUNCtion:FREQuency 1000` | |
| `:FUNCtion:AMPLitude <Vpp>` | `:FUNCtion:AMPLitude 1.5` | |
| `:FUNCtion:OFFSet <V>` | `:FUNCtion:OFFSet 0` | |
| `:CHANnel <ON\|OFF>` | `:CHANnel ON` | Siggen output enable |

### Valid Timebase Values

```
5.0ns 10.0ns 20.0ns 50.0ns 100ns 200ns 500ns
1.0us 2.0us 5.0us 10us 20us 50us 100us 200us 500us
1.0ms 2.0ms 5.0ms 10ms 20ms 50ms 100ms 200ms 500ms
1.0s 2.0s 5.0s 10s 20s 50s 100s 200s 500s 1000s
```

### Valid Vertical Scale Values (1X probe)

```
10.0mV 20.0mV 50.0mV 100mV 200mV 500mV 1.00V 2.00V 5.00V 10.0V
```

At 10X probe multiply by 10. At 100X multiply by 100.

### Commands That Crash the Firmware

These commands cause the scope to drop `/dev/ttyUSB0`. Do not send them:

```
:TRIG:TYPE?    :TRIG:SOU?     :TRIG:STAT?
:MEAS:FREQ?    :MEAS:VPP?     :WAV:DATA?
:WAVeform:DATA?               :DISP:DATA?
```

The scope recovers when you unplug and replug the USB-C cable (keep it powered on).

---

## Protocol Notes

### One connection per command

The HDS200 firmware drops the serial connection after each transaction. Every SCPI command must open and close `/dev/ttyUSB0` separately. Holding the port open between commands causes an `[Errno 5] Input/output error`.

### Header JSON prefix

The `:DATa:WAVe:SCReen:HEAD?` response has a 4-byte binary prefix before the JSON object (e.g. `J\x02\x00\x00`). Strip everything before the `{` character before parsing.

### Trigger status affects waveform data

`:DATa:WAVe:SCReen:CH1?` returns valid data when trigger status is `TRIG` or `AUTO`. In `STOP` or `READY` state the payload may be empty or stale.

### USB VID:PID changes with mode

| Mode | VID:PID | Device name shown by lsusb |
|---|---|---|
| MSC | `28e9:0285` | GDMicroelectronics oscilloscope |
| HID | `5345:1234` | Owon PDS6062T Oscilloscope |

---

## Waveform Data Format

The `:DATa:WAVe:SCReen:CH<x>?` response:

```
[4 bytes] Little-endian uint32 = payload length in bytes
[N bytes] Raw ADC samples, one byte each, unsigned (0–255)
```

- **Midpoint:** 128 (represents 0V)
- **Sample count:** 600 (at 4K memory depth)
- **12 horizontal divisions** of waveform data

### Decoding

```python
import struct

raw_bytes   = scope.get_raw_waveform(ch=1)
payload_len = struct.unpack("<I", raw_bytes[:4])[0]
samples     = list(raw_bytes[4:4 + payload_len])  # 600 unsigned bytes
```

---

## Voltage Scaling

The ADC scaling is **not fixed** — it varies with V/div setting. The scope changes its internal ADC gain as you change the vertical scale.

**The reliable method:** normalize the parsed waveform against the scope's own `:MEASurement:CH1:PKPK?` value:

```python
raw_vpp   = max(voltages) - min(voltages)
scope_vpp = 3.280  # from :MEASurement:CH1:PKPK?
factor    = scope_vpp / raw_vpp
voltages  = [v * factor for v in voltages]
```

This is what `scope.get_waveform(normalize=True)` does automatically.

**Why this works:** The waveform *shape* (relative sample values) is always correct. The normalization only adjusts the amplitude scale to match the scope's own measurement, which uses a separate internal path unaffected by the display scaling.

---

## Known Limitations

| Limitation | Detail |
|---|---|
| **Clipping** | If the signal extends beyond the visible screen, raw ADC bytes saturate at 0 or 255. The scope's own measurements still report correct values (they use internal memory, not screen data). Always set V/div so the signal fits on screen before capturing. Use the scope's `Auto` function first. |
| **No live streaming of screen pixels** | `STARTBMP` and `STARTBIN` (OWON legacy commands) do not respond in HID mode. Screenshot capture requires MSC mode and manual file copy. |
| **No trigger commands** | Trigger source, level, slope, and mode cannot be set via SCPI on this firmware. Configure triggers on the scope hardware. |
| **Slow capture rate** | ~3–5 seconds per full capture cycle. The serial port must open/close per command. |
| **600 samples max** | At 4K memory depth, only 600 screen samples are returned by `:DATa:WAVe:SCReen:CH<x>?`. Setting depth to 8K returns 600 screen samples (the visible window) not the full 8K memory. |
| **DMM SCPI reliability** | DMM SCPI mode requires the scope to be in Multimeter mode. Switching modes on the scope resets the SCPI activation. |

---

## Windows

The Hanmatek PC software for Windows is available at:
`https://bit.ly/3GCcmYn`

It provides a live waveform display and data export. On Windows, the scope likely presents a CDC ACM serial interface rather than HID — different driver behavior. The SCPI commands documented here should work the same way, but port will be `COMx` instead of `/dev/ttyUSB0`.

The Python scripts in this repo work on Windows with minor changes:

```python
scope = HDS200(port="COM3")  # adjust port number
```

On Windows you may need to install a `libusb` driver (e.g. via Zadig) if the scope does not appear as a COM port.

---

## Troubleshooting

### `/dev/ttyUSB0` does not appear

1. Confirm scope is in HID mode: `lsusb | grep 5345`
2. Check dialout group: `groups | grep dialout`
3. If not in dialout: `sudo usermod -aG dialout $USER` then log out/in
4. Try a different USB port
5. Try a different USB-C cable (some are charge-only, no data)

### `[Errno 5] Input/output error`

The scope dropped the connection — a SCPI command crashed the firmware handler. Unplug and replug the USB-C cable (keep scope powered on). The port will reappear. Do not send the commands listed in [Commands That Crash the Firmware](#commands-that-crash-the-firmware).

### `Device: None` or no response to `*IDN?`

1. Port present? `ls /dev/ttyUSB*`
2. In HID mode? `lsusb | grep 5345`
3. In dialout group? `groups | grep dialout`
4. Scope is on and not sleeping? (auto-off timer — check System menu)
5. Try: `python3 -c "import serial; s=serial.Serial('/dev/ttyUSB0',115200,timeout=2); s.write(b'*IDN?\n'); import time; time.sleep(0.6); print(s.read(256))"`

### SSH over T-Mobile hotspot — scope not reachable from laptop

T-Mobile hotspot blocks peer-to-peer traffic. Use a USB-to-Ethernet adapter for a direct wired connection between the OptiPlex and the laptop, or work directly on the OptiPlex.

### Waveform amplitude wrong

Set V/div on the scope so the signal fits within the 8 vertical divisions without clipping (no flat tops/bottoms on the waveform). Use the scope's `Auto` button first. Then run `capture.py` — the normalization step will correct the amplitude automatically.

### Signal generator not working

The signal generator only exists on the **HO52S** and **HO102S** models (not HO52 or HO102). Confirm your model. Connect to the **GEN Out** BNC port (not CH1 or CH2).

---

## Repository Structure

```
owon-hds200/
├── owonhds/
│   ├── __init__.py       # Package exports
│   ├── device.py         # HDS200 class — all SCPI communication
│   └── waveform.py       # Waveform data container and converter
├── scripts/
│   ├── capture.py        # Single waveform capture + plot
│   ├── stream.py         # Live streaming display
│   ├── fft.py            # FFT frequency spectrum analysis
│   ├── log.py            # Timed interval measurement logger
│   ├── compare.py        # Multi-capture overlay comparison
│   ├── siggen.py         # Signal generator control
│   ├── dmm.py            # Multimeter readout and logger
│   └── terminal.py       # Interactive SCPI terminal
├── requirements.txt
├── setup.py
├── LICENSE
└── README.md
```

---

## License

MIT — see [LICENSE](LICENSE)
