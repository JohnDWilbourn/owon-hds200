"""
owonhds.device — Low-level SCPI interface for OWON HDS200 series.

Confirmed working on:
  Hanmatek HO52S, OWON firmware V8.0.1
  USB VID:PID 5345:1234 (HID mode)

Wire protocol notes:
  - Device must be in HID mode (not MSC) for /dev/ttyUSB0 to appear
  - Each SCPI command requires a fresh serial connection (firmware drops
    the port if the connection is held open between commands)
  - :DATa:WAVe:SCReen:HEAD? response has a 4-byte binary prefix before JSON
  - :DATa:WAVe:SCReen:CH<x>? returns: [4-byte LE uint32 length][N raw bytes]
    where each byte is an unsigned 8-bit ADC sample (0-255, midpoint=128)
  - ADC scaling is NOT fixed — varies with V/div setting. Normalization
    against :MEASurement:CH1:PKPK? is required for accurate amplitude.
"""

import serial
import time
import json
import struct
import re
from typing import Optional


# ── Default port ──────────────────────────────────────────────────────────────
DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUD = 115200
DEFAULT_TIMEOUT = 3


class HDS200:
    """
    Interface to the OWON HDS200-series handheld oscilloscope.

    Usage:
        scope = HDS200()
        print(scope.identify())
        header = scope.get_header()
        waveform = scope.get_waveform("CH1")
    """

    def __init__(self, port: str = DEFAULT_PORT,
                 baud: int = DEFAULT_BAUD,
                 timeout: float = DEFAULT_TIMEOUT):
        self.port    = port
        self.baud    = baud
        self.timeout = timeout

    # ── Low-level transport ───────────────────────────────────────────────────

    def _open(self) -> serial.Serial:
        return serial.Serial(
            port=self.port, baudrate=self.baud,
            bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE, timeout=self.timeout,
        )

    def query(self, cmd: str, delay: float = 0.6,
              binary: bool = False, max_bytes: int = 131072) -> Optional[bytes | str]:
        """
        Send one SCPI command and return the response.

        Opens and closes the serial port for each command — required because
        the HDS200 firmware drops the connection after each transaction.

        Args:
            cmd:       SCPI command string (newline appended automatically)
            delay:     seconds to wait after sending before reading
            binary:    if True, return raw bytes; otherwise return decoded str
            max_bytes: maximum bytes to read

        Returns:
            str (binary=False) or bytes (binary=True), or None on error
        """
        try:
            ser = self._open()
            ser.reset_input_buffer()
            ser.write((cmd + "\n").encode("utf-8"))
            time.sleep(delay)
            chunks = []
            deadline = time.time() + self.timeout
            while time.time() < deadline:
                waiting = ser.in_waiting
                if waiting:
                    chunks.append(ser.read(waiting))
                    if sum(len(c) for c in chunks) >= max_bytes:
                        break
                    time.sleep(0.05)
                else:
                    if chunks:
                        break
                    time.sleep(0.05)
            ser.close()
            raw = b"".join(chunks)
            if binary:
                return raw
            return raw.decode("utf-8", errors="replace").strip()
        except Exception as e:
            raise ConnectionError(f"SCPI query failed ({cmd!r}): {e}") from e

    # ── Identity & status ─────────────────────────────────────────────────────

    def identify(self) -> str:
        """Return *IDN? response."""
        return self.query("*IDN?") or ""

    def is_connected(self) -> bool:
        """Return True if scope responds to *IDN?."""
        try:
            return bool(self.identify())
        except Exception:
            return False

    def trigger_status(self) -> str:
        """Return current trigger status: AUTO, READY, TRIG, SCAN, or STOP."""
        return self.query(":TRIGger:STATus?") or ""

    def reset(self):
        """Send *RST to restore default settings."""
        self.query("*RST", delay=1.0)

    # ── Channel settings ──────────────────────────────────────────────────────

    def get_channel_scale(self, ch: int = 1) -> str:
        """Return vertical scale for channel (e.g. '500mV')."""
        return self.query(f":CH{ch}:SCALe?") or ""

    def set_channel_scale(self, scale: str, ch: int = 1):
        """Set vertical scale. scale e.g. '500mV', '1V', '2V'."""
        self.query(f":CH{ch}:SCALe {scale}", delay=0.3)

    def get_channel_coupling(self, ch: int = 1) -> str:
        """Return coupling: AC, DC, or GND."""
        return self.query(f":CH{ch}:COUP?") or ""

    def set_channel_coupling(self, coupling: str, ch: int = 1):
        """Set coupling: AC, DC, or GND."""
        self.query(f":CH{ch}:COUPling {coupling}", delay=0.3)

    def get_channel_probe(self, ch: int = 1) -> str:
        """Return probe attenuation: 1X, 10X, 100X, or 1000X."""
        return self.query(f":CH{ch}:PROBE?") or ""

    def set_channel_probe(self, atten: str, ch: int = 1):
        """Set probe attenuation: 1X, 10X, 100X, or 1000X."""
        self.query(f":CH{ch}:PROBe {atten}", delay=0.3)

    def get_channel_display(self, ch: int = 1) -> str:
        """Return channel display state: ON or OFF."""
        return self.query(f":CH{ch}:DISPlay?") or ""

    def set_channel_display(self, state: bool, ch: int = 1):
        """Turn channel display on or off."""
        self.query(f":CH{ch}:DISPlay {'ON' if state else 'OFF'}", delay=0.3)

    def get_channel_offset(self, ch: int = 1) -> str:
        """Return vertical offset in divisions."""
        return self.query(f":CH{ch}:OFFSet?") or ""

    # ── Horizontal settings ───────────────────────────────────────────────────

    def get_timebase(self) -> str:
        """Return horizontal scale (e.g. '500us')."""
        return self.query(":HOR:SCALE?") or ""

    def set_timebase(self, scale: str):
        """Set horizontal scale. scale e.g. '500us', '1ms', '10us'."""
        self.query(f":HORIzontal:SCALe {scale}", delay=0.3)

    def get_timebase_offset(self) -> str:
        """Return horizontal offset in divisions."""
        return self.query(":HOR:OFFSET?") or ""

    # ── Acquire settings ──────────────────────────────────────────────────────

    def get_acquire_mode(self) -> str:
        """Return acquire mode: SAMPle or PEAK."""
        return self.query(":ACQ:MODE?") or ""

    def set_acquire_mode(self, mode: str):
        """Set acquire mode: SAMPle or PEAK."""
        self.query(f":ACQuire:MODE {mode}", delay=0.3)

    def get_memory_depth(self) -> str:
        """Return memory depth: 4K or 8K."""
        return self.query(":ACQ:DEPMEM?") or ""

    def set_memory_depth(self, depth: str):
        """Set memory depth: 4K or 8K."""
        self.query(f":ACQuire:DEPMem {depth}", delay=0.3)

    # ── Measurements ─────────────────────────────────────────────────────────

    def measure(self, item: str, ch: int = 1) -> Optional[float]:
        """
        Query a measurement value.

        Args:
            item: MAX, MIN, PKPK, VAMP, AVERage, PERiod, FREQuency
            ch:   channel number (1 or 2)

        Returns:
            float value in SI units (volts/seconds), or None on failure
        """
        raw = self.query(f":MEASurement:CH{ch}:{item}?", delay=0.5)
        return _parse_measurement(raw)

    def measure_all(self, ch: int = 1) -> dict:
        """Return dict of all measurements for the channel."""
        items = {
            "frequency":  "FREQuency",
            "period":     "PERiod",
            "vpp":        "PKPK",
            "vamp":       "VAMP",
            "vmax":       "MAX",
            "vmin":       "MIN",
            "vaverage":   "AVERage",
        }
        results = {}
        for name, cmd in items.items():
            results[name] = self.measure(cmd, ch)
        return results

    # ── Header ────────────────────────────────────────────────────────────────

    def get_header(self) -> dict:
        """
        Fetch and parse the screen waveform header JSON.

        Returns dict with keys: timebase, sample, channel, runstatus, trig.
        Keys are lowercased. Returns empty dict on failure.
        """
        raw = self.query(":DATa:WAVe:SCReen:HEAD?", delay=1.0)
        if not raw:
            return {}
        # Strip stray binary prefix bytes before opening brace
        idx = raw.find("{")
        if idx < 0:
            return {}
        try:
            return json.loads(raw[idx:].lower())
        except json.JSONDecodeError:
            return {}

    # ── Waveform data ─────────────────────────────────────────────────────────

    def get_raw_waveform(self, ch: int = 1) -> bytes:
        """
        Fetch raw waveform bytes for the specified channel.

        Returns: raw bytes including 4-byte length prefix.
        """
        raw = self.query(f":DATa:WAVe:SCReen:CH{ch}?",
                         delay=1.5, binary=True)
        return raw or b""

    def get_waveform(self, ch: int = 1, normalize: bool = True):
        """
        Fetch and parse a complete waveform from the scope.

        Args:
            ch:        channel number (1 or 2)
            normalize: if True, scale amplitude to match scope's Vpp measurement

        Returns:
            Waveform object
        """
        from .waveform import Waveform
        header   = self.get_header()
        raw      = self.get_raw_waveform(ch)
        meas     = self.measure_all(ch)
        waveform = Waveform.from_raw(raw, header, ch, meas)
        if normalize and waveform.vpp_raw > 0 and meas.get("vpp"):
            waveform.normalize(meas["vpp"])
        return waveform

    # ── Signal generator ─────────────────────────────────────────────────────

    def siggen_set_waveform(self, waveform: str):
        """Set signal generator waveform: SINE, SQUare, RAMP, PULSe."""
        self.query(f":FUNCtion {waveform}", delay=0.3)

    def siggen_set_frequency(self, freq_hz: float):
        """Set signal generator frequency in Hz."""
        self.query(f":FUNCtion:FREQuency {freq_hz:.6e}", delay=0.3)

    def siggen_set_amplitude(self, vpp: float):
        """Set signal generator amplitude in Vpp."""
        self.query(f":FUNCtion:AMPLitude {vpp:.6e}", delay=0.3)

    def siggen_set_offset(self, volts: float):
        """Set signal generator DC offset in volts."""
        self.query(f":FUNCtion:OFFSet {volts:.6e}", delay=0.3)

    def siggen_get_waveform(self) -> str:
        return self.query(":FUNCtion?") or ""

    def siggen_get_frequency(self) -> Optional[float]:
        raw = self.query(":FUNCtion:FREQuency?")
        return _parse_measurement(raw)

    def siggen_get_amplitude(self) -> Optional[float]:
        raw = self.query(":FUNCtion:AMPLitude?")
        return _parse_measurement(raw)

    def siggen_output(self, enabled: bool):
        """Enable or disable signal generator output."""
        self.query(f":CHANnel {'ON' if enabled else 'OFF'}", delay=0.3)

    # ── DMM ───────────────────────────────────────────────────────────────────

    def dmm_set_function(self, func: str):
        """
        Set DMM function.
        func: DCV, ACV, DCA, ACA, RES, DIOD, BEEP, CAP
        """
        self.query(f":FUNC {func}", delay=0.3)

    def dmm_read(self) -> Optional[float]:
        """Read current DMM measurement. Returns float in SI units."""
        raw = self.query(":READ?", delay=0.5)
        return _parse_measurement(raw)

    def dmm_activate_scpi(self) -> bool:
        """
        Activate DMM SCPI mode. Must be called before DMM commands.
        Returns True if scope confirms SCPI mode.
        """
        resp = self.query(":SCPI:DISP?", delay=0.5)
        return resp is not None and "scpion" in resp.lower()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_measurement(raw: Optional[str]) -> Optional[float]:
    """
    Parse a measurement response string to a float in SI units.

    Handles formats like:
      "F=60.96kHz"  -> 60960.0
      "Vpp=3.280V"  -> 3.280
      "T=16.42us"   -> 1.642e-05
      "V=28.00mV"   -> 0.028
      "Ma=2.320V"   -> 2.320
      "3.280"        -> 3.280
    """
    if not raw:
        return None
    s = raw.strip()

    # Strip leading label (e.g. "F=", "Vpp=", "Ma=")
    if "=" in s:
        s = s.split("=", 1)[1].strip()

    # Extract numeric part and unit
    m = re.match(r"^([+-]?\d+\.?\d*(?:[eE][+-]?\d+)?)\s*([a-zA-Zμ]*)", s)
    if not m:
        return None

    try:
        value = float(m.group(1))
    except ValueError:
        return None

    unit = m.group(2).lower()

    # Apply SI prefix
    if unit.startswith("k"):
        value *= 1e3
    elif unit.startswith("m") and not unit.startswith("ms"):
        value *= 1e-3
    elif unit.startswith("u") or unit.startswith("μ"):
        value *= 1e-6
    elif unit.startswith("n"):
        value *= 1e-9
    elif unit.startswith("ms"):
        value *= 1e-3

    return value
