#!/usr/bin/env python3
"""
stream.py — Live streaming waveform display from HDS200 scope.

Continuously captures and updates a matplotlib plot in real time.
Press Ctrl+C to stop.

Usage:
    python3 stream.py
    python3 stream.py --port /dev/ttyUSB0 --interval 0.5
    python3 stream.py --ch 1 --interval 1.0

Requirements:
    pip install pyserial matplotlib
"""

import argparse
import os
import sys
import time
import signal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from owonhds import HDS200

_running = True


def handle_sigint(sig, frame):
    global _running
    _running = False
    print("\n\nStopping stream...")


def parse_args():
    p = argparse.ArgumentParser(description="Live stream waveform from HDS200")
    p.add_argument("--port",     default="/dev/ttyUSB0", help="Serial port")
    p.add_argument("--ch",       type=int, default=1, choices=[1, 2])
    p.add_argument("--interval", type=float, default=1.0,
                   help="Capture interval in seconds (default: 1.0)")
    return p.parse_args()


def main():
    global _running
    args  = parse_args()
    signal.signal(signal.SIGINT, handle_sigint)

    try:
        import matplotlib
        matplotlib.use("TkAgg")  # Interactive backend
        import matplotlib.pyplot as plt
        import matplotlib.animation as animation
    except ImportError:
        print("ERROR: matplotlib required. pip install matplotlib")
        sys.exit(1)

    scope = HDS200(port=args.port)
    if not scope.is_connected():
        print(f"ERROR: No scope found on {args.port}")
        sys.exit(1)

    print(f"Streaming CH{args.ch} — {scope.identify()}")
    print("Press Ctrl+C to stop.\n")

    # ── Set up plot ───────────────────────────────────────────────────────────
    fig, (ax_wave, ax_info) = plt.subplots(
        2, 1, figsize=(14, 7),
        gridspec_kw={"height_ratios": [4, 1]}
    )
    fig.patch.set_facecolor("#111111")
    fig.suptitle(f"HDS200 Live Stream — CH{args.ch}",
                 color="white", fontsize=12)

    for ax in [ax_wave, ax_info]:
        ax.set_facecolor("#111111")
        ax.tick_params(colors="#AAAAAA")
        for spine in ax.spines.values():
            spine.set_color("#444444")

    ax_wave.set_xlabel("Time (s)", color="#AAAAAA")
    ax_wave.set_ylabel("Voltage (V)", color="#AAAAAA")
    ax_wave.grid(True, alpha=0.2, color="#555555", linestyle="--")

    ax_info.axis("off")

    line,      = ax_wave.plot([], [], color="#FFD700", linewidth=0.9)
    info_text  = ax_info.text(0.01, 0.5, "", color="white",
                               fontfamily="monospace", fontsize=9,
                               transform=ax_info.transAxes,
                               verticalalignment="center")

    capture_count = [0]
    last_time     = [0.0]

    def update(_frame):
        global _running
        if not _running:
            plt.close()
            return line, info_text

        now = time.time()
        if now - last_time[0] < args.interval:
            return line, info_text
        last_time[0] = now

        try:
            waveform = scope.get_waveform(ch=args.ch, normalize=True)
            if not waveform.voltages:
                return line, info_text

            capture_count[0] += 1
            line.set_data(waveform.times, waveform.voltages)
            ax_wave.relim()
            ax_wave.autoscale_view()

            m = waveform.meas
            freq = m.get("frequency")
            freq_str = f"{freq/1000:.3f} kHz" if freq and freq >= 1000 else \
                       f"{freq:.3f} Hz" if freq else "---"
            info_str = (
                f"  Captures: {capture_count[0]:>4}   "
                f"Freq: {freq_str:<14}  "
                f"Vpp: {m.get('vpp', 0):.4f} V   "
                f"Vmax: {m.get('vmax', 0):.4f} V   "
                f"Vmin: {m.get('vmin', 0):.4f} V   "
                f"Vavg: {m.get('vaverage', 0):.4f} V"
            )
            info_text.set_text(info_str)
            tb = waveform.header.get("timebase", {}).get("scale", "?")
            ax_wave.set_title(
                f"CH{args.ch}  timebase={tb}/div  "
                f"samples={len(waveform)}  "
                f"Vpp={waveform.vpp:.4f}V",
                color="white", fontsize=10
            )
        except Exception as e:
            info_text.set_text(f"  Error: {e}")

        return line, info_text

    ani = animation.FuncAnimation(
        fig, update, interval=100, blit=False, cache_frame_data=False
    )

    plt.tight_layout()
    plt.show()
    print("Stream ended.")


if __name__ == "__main__":
    main()
