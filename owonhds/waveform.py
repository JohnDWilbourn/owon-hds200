"""
owonhds.waveform — Waveform data container and converter.
"""

import struct
import json
from typing import List, Optional, Tuple


class Waveform:
    """
    Parsed oscilloscope waveform.

    Attributes:
        channel:    channel number (1 or 2)
        samples:    raw ADC byte values (0-255)
        times:      time axis in seconds
        voltages:   voltage axis in volts (after normalization)
        vpp_raw:    Vpp before normalization
        header:     full scope header dict
        meas:       measurement dict from scope
        normalized: True if amplitude has been normalized to scope measurement
    """

    def __init__(self):
        self.channel:    int         = 1
        self.samples:    List[int]   = []
        self.times:      List[float] = []
        self.voltages:   List[float] = []
        self.vpp_raw:    float       = 0.0
        self.header:     dict        = {}
        self.meas:       dict        = {}
        self.normalized: bool        = False

    @classmethod
    def from_raw(cls, raw_bytes: bytes, header: dict,
                 ch: int = 1, meas: dict = None) -> "Waveform":
        """
        Parse raw bytes from :DATa:WAVe:SCReen:CH<x>? into a Waveform.

        Wire format:
          [4 bytes LE uint32 = payload length]
          [N unsigned bytes = ADC samples, 0-255, midpoint=128]

        Scaling:
          ADC gain varies with V/div. Amplitude must be normalized against
          scope's own Vpp measurement for accuracy.
          Shape and timing are always correct without normalization.
        """
        w = cls()
        w.channel = ch
        w.header  = header
        w.meas    = meas or {}

        if not raw_bytes or len(raw_bytes) < 6:
            return w

        payload_len = struct.unpack("<I", raw_bytes[:4])[0]
        payload     = raw_bytes[4:4 + payload_len]
        w.samples   = list(payload)

        if not w.samples:
            return w

        # ── Voltage axis (pre-normalization estimate) ─────────────────────
        try:
            ch_info    = _get_channel_info(header, ch)
            probe_mult = _parse_probe(ch_info.get("probe", "1x"))
            vdiv       = _parse_scale(ch_info.get("scale", "1.00v"))
            # Best-estimate formula: varies with V/div, will be overridden
            # by normalize() if Vpp measurement is available
            mv_per_cnt = vdiv * probe_mult * 1000.0 / 25.0
            midpoint   = 128.0
            w.voltages = [(s - midpoint) * mv_per_cnt / 1000.0
                          for s in w.samples]
        except Exception:
            w.voltages = [(s - 128.0) / 128.0 for s in w.samples]

        w.vpp_raw = max(w.voltages) - min(w.voltages) if w.voltages else 0.0

        # ── Time axis ─────────────────────────────────────────────────────
        try:
            tb_scale = header.get("timebase", {}).get("scale", "500us")
            spd      = _parse_time(tb_scale)
            n        = len(w.samples)
            dt       = (spd * 12.0) / n
            w.times  = [i * dt for i in range(n)]
        except Exception:
            w.times = list(range(len(w.samples)))

        return w

    def normalize(self, scope_vpp: float):
        """
        Scale voltages so Vpp matches the scope's own measurement.

        This corrects for the variable ADC gain across V/div settings.
        Always call this after from_raw() for accurate amplitude values.
        """
        if self.vpp_raw > 0 and scope_vpp > 0:
            factor     = scope_vpp / self.vpp_raw
            self.voltages   = [v * factor for v in self.voltages]
            self.normalized = True

    # ── Computed properties ───────────────────────────────────────────────────

    @property
    def vpp(self) -> float:
        return max(self.voltages) - min(self.voltages) if self.voltages else 0.0

    @property
    def vmax(self) -> float:
        return max(self.voltages) if self.voltages else 0.0

    @property
    def vmin(self) -> float:
        return min(self.voltages) if self.voltages else 0.0

    @property
    def sample_rate(self) -> Optional[float]:
        """Sample rate in Sa/s derived from time axis."""
        if len(self.times) > 1:
            dt = self.times[1] - self.times[0]
            return 1.0 / dt if dt > 0 else None
        return None

    @property
    def duration(self) -> float:
        """Total capture duration in seconds."""
        return self.times[-1] if self.times else 0.0

    def __len__(self):
        return len(self.samples)

    def __repr__(self):
        return (f"Waveform(ch={self.channel}, samples={len(self.samples)}, "
                f"vpp={self.vpp:.4f}V, normalized={self.normalized})")

    # ── Export ────────────────────────────────────────────────────────────────

    def to_csv_rows(self) -> List[str]:
        """Return list of CSV row strings (including header row)."""
        rows = ["time_s,voltage_V"]
        for t, v in zip(self.times, self.voltages):
            rows.append(f"{t:.9f},{v:.6f}")
        return rows

    def save_csv(self, path: str):
        """Save waveform to CSV file."""
        with open(path, "w") as f:
            f.write("\n".join(self.to_csv_rows()))

    def to_numpy(self):
        """Return (times, voltages) as numpy arrays if numpy is available."""
        try:
            import numpy as np
            return np.array(self.times), np.array(self.voltages)
        except ImportError:
            raise ImportError("numpy required: pip install numpy")


# ── Parsing helpers ───────────────────────────────────────────────────────────

def _get_channel_info(header: dict, ch: int) -> dict:
    for c in header.get("channel", []):
        if c.get("name", "") == f"ch{ch}":
            return c
    return {}


def _parse_probe(s: str) -> float:
    """'10x' -> 10.0, '1x' -> 1.0"""
    return float(s.lower().replace("x", "").strip())


def _parse_scale(s: str) -> float:
    """'500mv' -> 0.5, '1.00v' -> 1.0, '2.00kv' -> 2000.0 (volts/div)"""
    s = s.lower().strip()
    if "mv" in s:
        return float(s.replace("mv", "")) / 1000.0
    elif "kv" in s:
        return float(s.replace("kv", "")) * 1000.0
    else:
        return float(s.replace("v", ""))


def _parse_time(s: str) -> float:
    """'500us' -> 5e-4, '1.0ms' -> 1e-3, '5.0ns' -> 5e-9 (seconds/div)"""
    s = s.lower().strip()
    if "ns" in s:
        return float(s.replace("ns", "")) * 1e-9
    elif "us" in s:
        return float(s.replace("us", "")) * 1e-6
    elif "ms" in s:
        return float(s.replace("ms", "")) * 1e-3
    else:
        return float(s.replace("s", ""))
