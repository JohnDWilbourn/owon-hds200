#!/usr/bin/env python3
"""
compare.py — Overlay and compare multiple waveform captures.

Captures N waveforms in sequence and overlays them on a single plot.
Useful for comparing signal stability, jitter, or changes over time.
Also works with previously saved CSV files.

Usage:
    # Capture 5 waveforms live and compare:
    python3 compare.py --count 5

    # Compare existing CSV files:
    python3 compare.py --files wave1.csv wave2.csv wave3.csv

    # Live capture with custom interval:
    python3 compare.py --count 10 --interval 2.0

Requirements:
    pip install pyserial matplotlib numpy
"""

import argparse
import datetime
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from owonhds import HDS200


def parse_args():
    p = argparse.ArgumentParser(description="Compare multiple waveforms from HDS200")
    p.add_argument("--port",     default="/dev/ttyUSB0")
    p.add_argument("--ch",       type=int, default=1, choices=[1, 2])
    p.add_argument("--count",    type=int, default=5,
                   help="Number of live captures to compare (default: 5)")
    p.add_argument("--interval", type=float, default=1.0,
                   help="Seconds between captures (default: 1.0)")
    p.add_argument("--files",    nargs="+",
                   help="Compare existing CSV files instead of live capture")
    p.add_argument("--out",      default=".", help="Output directory")
    p.add_argument("--no-plot",  action="store_true")
    return p.parse_args()


def load_csv(path):
    """Load time/voltage from a waveform CSV file."""
    times = []
    volts = []
    with open(path) as f:
        header = f.readline()  # skip header
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 2:
                try:
                    times.append(float(parts[0]))
                    volts.append(float(parts[1]))
                except ValueError:
                    pass
    return times, volts


def plot_comparison(all_times, all_voltages, labels, stats, path, title):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("  matplotlib/numpy not installed — skipping plot")
        return

    colors = ["#FFD700", "#00CFFF", "#FF6B6B", "#7FFF00",
              "#FF9F40", "#C084FC", "#FB923C", "#34D399",
              "#F472B6", "#60A5FA"]

    fig, (ax_wave, ax_stat) = plt.subplots(
        2, 1, figsize=(16, 8),
        gridspec_kw={"height_ratios": [3, 1]}
    )
    fig.patch.set_facecolor("#111111")
    fig.suptitle(title, color="white", fontsize=12)

    for ax in [ax_wave, ax_stat]:
        ax.set_facecolor("#111111")
        ax.tick_params(colors="#AAAAAA")
        for spine in ax.spines.values():
            spine.set_color("#444444")

    ax_wave.grid(True, alpha=0.2, color="#555555", linestyle="--")
    ax_wave.set_xlabel("Time (s)", color="#AAAAAA")
    ax_wave.set_ylabel("Voltage (V)", color="#AAAAAA")

    for i, (times, voltages, label) in enumerate(zip(all_times, all_voltages, labels)):
        color = colors[i % len(colors)]
        ax_wave.plot(times, voltages, color=color, linewidth=0.8,
                     alpha=0.85, label=label)

    ax_wave.legend(facecolor="#222222", labelcolor="white",
                   fontsize=8, ncol=min(5, len(labels)))

    # Stats panel
    ax_stat.axis("off")
    if stats:
        try:
            vpps  = [s["vpp"]  for s in stats if s.get("vpp")]
            vmaxs = [s["vmax"] for s in stats if s.get("vmax")]
            vmins = [s["vmin"] for s in stats if s.get("vmin")]
            freqs = [s["freq"] for s in stats if s.get("freq")]
            lines = []
            if vpps:
                lines.append(
                    f"Vpp:  mean={np.mean(vpps):.4f}V  "
                    f"min={np.min(vpps):.4f}V  "
                    f"max={np.max(vpps):.4f}V  "
                    f"σ={np.std(vpps):.4f}V"
                )
            if freqs:
                lines.append(
                    f"Freq: mean={np.mean(freqs)/1000:.4f}kHz  "
                    f"min={np.min(freqs)/1000:.4f}kHz  "
                    f"max={np.max(freqs)/1000:.4f}kHz  "
                    f"σ={np.std(freqs)/1000:.6f}kHz"
                )
            ax_stat.text(0.01, 0.7, "\n".join(lines),
                         color="white", fontfamily="monospace",
                         fontsize=9, transform=ax_stat.transAxes,
                         verticalalignment="top")
        except Exception:
            pass

    plt.tight_layout()
    plt.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close()
    print(f"\n  Plot saved : {path}")


def main():
    args  = parse_args()
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(args.out, exist_ok=True)

    print("=" * 60)
    print("HDS200 Waveform Comparison")
    print("=" * 60)

    all_times    = []
    all_voltages = []
    labels       = []
    stats        = []

    if args.files:
        # Load from CSV files
        print(f"Loading {len(args.files)} CSV files...\n")
        for path in args.files:
            print(f"  Loading: {path}")
            times, volts = load_csv(path)
            if times:
                all_times.append(times)
                all_voltages.append(volts)
                labels.append(os.path.basename(path))
                vpp = max(volts) - min(volts) if volts else 0
                stats.append({"vpp": vpp, "vmax": max(volts), "vmin": min(volts)})
                print(f"    {len(times)} samples, Vpp={vpp:.4f}V")
            else:
                print(f"    WARNING: No data loaded")
    else:
        # Live capture
        scope = HDS200(port=args.port)
        if not scope.is_connected():
            print(f"ERROR: No scope on {args.port}")
            sys.exit(1)

        print(f"Device  : {scope.identify()}")
        print(f"Capturing {args.count} waveforms from CH{args.ch} "
              f"(interval={args.interval}s)...\n")

        for i in range(args.count):
            print(f"  Capture {i+1}/{args.count}...", end=" ", flush=True)
            try:
                waveform = scope.get_waveform(ch=args.ch, normalize=True)
                if waveform.voltages:
                    all_times.append(waveform.times)
                    all_voltages.append(waveform.voltages)
                    labels.append(f"#{i+1}")
                    freq = waveform.meas.get("frequency")
                    stats.append({
                        "vpp":  waveform.vpp,
                        "vmax": waveform.vmax,
                        "vmin": waveform.vmin,
                        "freq": freq,
                    })
                    freq_str = f"{freq/1000:.3f}kHz" if freq and freq >= 1000 else \
                               f"{freq:.3f}Hz" if freq else "?"
                    print(f"Vpp={waveform.vpp:.4f}V  freq={freq_str}")

                    # Save individual CSV
                    csv_path = os.path.join(
                        args.out,
                        f"{stamp}_{i+1:03d}_CH{args.ch}_compare.csv"
                    )
                    waveform.save_csv(csv_path)
                else:
                    print("no data")
            except Exception as e:
                print(f"ERROR: {e}")

            if i < args.count - 1:
                time.sleep(args.interval)

    # Summary statistics
    if stats:
        try:
            import numpy as np
            vpps  = [s["vpp"]  for s in stats if s.get("vpp")]
            freqs = [s["freq"] for s in stats if s.get("freq")]
            print(f"\n── Statistics ({'%d captures' % len(stats)}) ───────────────────")
            if vpps:
                print(f"  Vpp : mean={np.mean(vpps):.4f}V  "
                      f"min={np.min(vpps):.4f}V  max={np.max(vpps):.4f}V  "
                      f"σ={np.std(vpps):.6f}V")
            if freqs:
                print(f"  Freq: mean={np.mean(freqs)/1000:.4f}kHz  "
                      f"min={np.min(freqs)/1000:.4f}kHz  "
                      f"max={np.max(freqs)/1000:.4f}kHz  "
                      f"σ={np.std(freqs)/1000:.6f}kHz")
        except ImportError:
            pass

    if not args.no_plot and all_voltages:
        plot_path = os.path.join(args.out, f"{stamp}_compare.png")
        title = (f"HDS200 Waveform Comparison — CH{args.ch}  "
                 f"({len(all_voltages)} captures)")
        plot_comparison(all_times, all_voltages, labels, stats, plot_path, title)

    print("\nDone.")


if __name__ == "__main__":
    main()
