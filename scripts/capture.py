#!/usr/bin/env python3
"""
capture.py — Single waveform capture from OWON HDS200 / Hanmatek HO52S.

Captures one waveform from CH1 (and CH2 if active), saves timestamped
CSV and PNG to the output directory, and prints all measurements.

Usage:
    python3 capture.py
    python3 capture.py --port /dev/ttyUSB0 --out ~/Oscilloscope
    python3 capture.py --ch 2
    python3 capture.py --no-plot

Requirements:
    pip install pyserial matplotlib

Device setup:
    Scope must be in HID USB mode (not MSC).
    System → USB → HID on the scope menu.
"""

import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from owonhds import HDS200


def parse_args():
    p = argparse.ArgumentParser(description="Capture waveform from HDS200 scope")
    p.add_argument("--port",    default="/dev/ttyUSB0", help="Serial port")
    p.add_argument("--out",     default=".", help="Output directory")
    p.add_argument("--ch",      type=int, default=1, choices=[1, 2], help="Channel")
    p.add_argument("--no-plot", action="store_true", help="Skip PNG plot")
    p.add_argument("--both",    action="store_true", help="Capture CH1 and CH2")
    return p.parse_args()


def plot_waveform(times, voltages, path, title="Waveform"):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(14, 5))
        fig.patch.set_facecolor("#111111")
        ax.set_facecolor("#111111")
        ax.plot(times, voltages, color="#FFD700", linewidth=0.9)
        ax.set_xlabel("Time (s)", color="#AAAAAA")
        ax.set_ylabel("Voltage (V)", color="#AAAAAA")
        ax.set_title(title, color="white", fontsize=11)
        ax.tick_params(colors="#AAAAAA")
        ax.spines["bottom"].set_color("#444444")
        ax.spines["left"].set_color("#444444")
        ax.spines["top"].set_color("#444444")
        ax.spines["right"].set_color("#444444")
        ax.grid(True, alpha=0.2, color="#555555", linestyle="--")
        fig.tight_layout()
        plt.savefig(path, dpi=150, facecolor=fig.get_facecolor())
        plt.close()
        print(f"  Plot saved : {path}")
        return True
    except ImportError:
        print("  (matplotlib not installed — skipping plot)")
        return False


def capture_channel(scope, ch, args, stamp):
    print(f"\n── Channel {ch} ─────────────────────────────────")
    waveform = scope.get_waveform(ch=ch, normalize=True)

    if not waveform.voltages:
        print(f"  ERROR: No data returned for CH{ch}")
        return

    print(f"  Samples    : {len(waveform)}")
    print(f"  Duration   : {waveform.duration*1000:.3f} ms")
    print(f"  Sample rate: {waveform.sample_rate/1e6:.3f} MSa/s"
          if waveform.sample_rate else "  Sample rate: unknown")
    print(f"  Vpp        : {waveform.vpp:.4f} V")
    print(f"  Vmax       : {waveform.vmax:.4f} V")
    print(f"  Vmin       : {waveform.vmin:.4f} V")
    print(f"  Normalized : {waveform.normalized}")

    # Measurements
    print(f"\n  Measurements (from scope):")
    for k, v in waveform.meas.items():
        if v is not None:
            print(f"    {k:<12} {v:.6g}")

    # Save CSV
    os.makedirs(args.out, exist_ok=True)
    csv_path = os.path.join(args.out, f"{stamp}_CH{ch}_waveform.csv")
    waveform.save_csv(csv_path)
    print(f"\n  CSV saved  : {csv_path}")

    # Save plot
    if not args.no_plot:
        header = waveform.header
        tb  = header.get("timebase", {}).get("scale", "?")
        try:
            ch_info = next(c for c in header["channel"]
                           if c["name"] == f"ch{ch}")
            sc = ch_info["scale"]
            pr = ch_info.get("probe", "?")
        except Exception:
            sc, pr = "?", "?"
        freq = waveform.meas.get("frequency")
        freq_str = f"{freq/1000:.3f} kHz" if freq and freq >= 1000 else \
                   f"{freq:.3f} Hz" if freq else "?"
        title = (f"CH{ch}  {sc}/div  probe={pr}  "
                 f"timebase={tb}/div  freq={freq_str}  "
                 f"Vpp={waveform.vpp:.3f}V")
        plot_path = os.path.join(args.out, f"{stamp}_CH{ch}_waveform.png")
        plot_waveform(waveform.times, waveform.voltages, plot_path, title)


def main():
    args  = parse_args()
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 60)
    print("HDS200 Waveform Capture")
    print("=" * 60)

    scope = HDS200(port=args.port)

    if not scope.is_connected():
        print(f"ERROR: No response from scope on {args.port}")
        print("  1. Is the scope powered on?")
        print("  2. Is USB mode set to HID? (System → USB → HID)")
        print("  3. Is /dev/ttyUSB0 present? (ls /dev/ttyUSB*)")
        print("  4. Are you in the dialout group? (groups | grep dialout)")
        sys.exit(1)

    print(f"\nDevice     : {scope.identify()}")
    print(f"Trigger    : {scope.trigger_status()}")
    print(f"Timebase   : {scope.get_timebase()}")
    print(f"CH1 scale  : {scope.get_channel_scale(1)}")
    print(f"CH1 probe  : {scope.get_channel_probe(1)}")
    print(f"CH1 couple : {scope.get_channel_coupling(1)}")
    print(f"Acq mode   : {scope.get_acquire_mode()}")
    print(f"Mem depth  : {scope.get_memory_depth()}")

    channels = [1, 2] if args.both else [args.ch]
    for ch in channels:
        if ch == 2:
            disp = scope.get_channel_display(2)
            if "off" in disp.lower():
                print(f"\nCH2 is off — skipping")
                continue
        capture_channel(scope, ch, args, stamp)

    print("\nDone.")


if __name__ == "__main__":
    main()
