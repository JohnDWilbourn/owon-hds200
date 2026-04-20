#!/usr/bin/env python3
"""
fft.py — Frequency spectrum (FFT) analysis from HDS200 scope.

Captures a waveform and displays both the time-domain signal and
its frequency spectrum side by side.

Usage:
    python3 fft.py
    python3 fft.py --port /dev/ttyUSB0 --ch 1
    python3 fft.py --window hann --out ~/Oscilloscope

FFT window options: hann (default), hamming, blackman, rectangular

Requirements:
    pip install pyserial matplotlib numpy
"""

import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from owonhds import HDS200


def parse_args():
    p = argparse.ArgumentParser(description="FFT analysis from HDS200")
    p.add_argument("--port",   default="/dev/ttyUSB0")
    p.add_argument("--ch",     type=int, default=1, choices=[1, 2])
    p.add_argument("--window", default="hann",
                   choices=["hann", "hamming", "blackman", "rectangular"])
    p.add_argument("--out",    default=".", help="Output directory for saved files")
    p.add_argument("--no-plot", action="store_true")
    return p.parse_args()


def compute_fft(times, voltages, window_name="hann"):
    """
    Compute FFT of waveform.

    Returns:
        freqs:      frequency axis in Hz
        magnitudes: magnitude spectrum in dBV
        fund_freq:  estimated fundamental frequency in Hz
        fund_mag:   fundamental magnitude in dBV
    """
    try:
        import numpy as np
    except ImportError:
        raise ImportError("numpy required: pip install numpy")

    t = np.array(times)
    v = np.array(voltages)
    n = len(v)

    if n < 4:
        return [], [], None, None

    # Sample rate
    dt = t[1] - t[0] if len(t) > 1 else 1.0
    fs = 1.0 / dt

    # Apply window
    if window_name == "hann":
        window = np.hanning(n)
    elif window_name == "hamming":
        window = np.hamming(n)
    elif window_name == "blackman":
        window = np.blackman(n)
    else:
        window = np.ones(n)

    # Compensate for window amplitude loss
    window_gain = np.mean(window)
    v_windowed  = v * window / window_gain

    # FFT
    fft_vals = np.fft.rfft(v_windowed)
    freqs    = np.fft.rfftfreq(n, d=dt)

    # Magnitude in dBV (peak amplitude)
    magnitudes = 20 * np.log10(
        np.abs(fft_vals) * 2 / n + 1e-12
    )

    # Find fundamental (skip DC bin 0)
    if len(magnitudes) > 1:
        fund_idx  = np.argmax(magnitudes[1:]) + 1
        fund_freq = freqs[fund_idx]
        fund_mag  = magnitudes[fund_idx]
    else:
        fund_freq = fund_mag = None

    return freqs.tolist(), magnitudes.tolist(), fund_freq, fund_mag


def plot_fft(times, voltages, freqs, magnitudes,
             fund_freq, fund_mag, waveform, path, args):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("  matplotlib/numpy not installed — skipping plot")
        return

    fig, (ax_time, ax_freq) = plt.subplots(1, 2, figsize=(16, 6))
    fig.patch.set_facecolor("#111111")

    for ax in [ax_time, ax_freq]:
        ax.set_facecolor("#111111")
        ax.tick_params(colors="#AAAAAA")
        for spine in ax.spines.values():
            spine.set_color("#444444")
        ax.grid(True, alpha=0.2, color="#555555", linestyle="--")

    # Time domain
    ax_time.plot(np.array(times) * 1000, voltages, color="#FFD700", linewidth=0.9)
    ax_time.set_xlabel("Time (ms)", color="#AAAAAA")
    ax_time.set_ylabel("Voltage (V)", color="#AAAAAA")
    ax_time.set_title(f"Time Domain — CH{args.ch}", color="white")

    # Frequency domain
    ax_freq.plot(np.array(freqs) / 1000, magnitudes, color="#00CFFF", linewidth=0.9)
    if fund_freq:
        ax_freq.axvline(fund_freq / 1000, color="#FF4444", alpha=0.7,
                        linestyle="--", linewidth=1.2,
                        label=f"Fund: {fund_freq/1000:.3f} kHz ({fund_mag:.1f} dBV)")
        ax_freq.legend(facecolor="#222222", labelcolor="white", fontsize=9)
    ax_freq.set_xlabel("Frequency (kHz)", color="#AAAAAA")
    ax_freq.set_ylabel("Magnitude (dBV)", color="#AAAAAA")
    ax_freq.set_title(f"Frequency Spectrum — {args.window.capitalize()} window",
                      color="white")

    # Stats
    m    = waveform.meas
    freq = m.get("frequency")
    freq_str = f"{freq/1000:.3f} kHz" if freq and freq >= 1000 else \
               f"{freq:.3f} Hz" if freq else "?"
    fig.suptitle(
        f"HDS200 FFT Analysis   CH{args.ch}   "
        f"Freq={freq_str}   Vpp={waveform.vpp:.4f}V",
        color="white", fontsize=11
    )

    plt.tight_layout()
    plt.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close()
    print(f"  Plot saved : {path}")


def main():
    args  = parse_args()
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 60)
    print("HDS200 FFT Analysis")
    print("=" * 60)

    scope = HDS200(port=args.port)
    if not scope.is_connected():
        print(f"ERROR: No scope on {args.port}")
        sys.exit(1)

    print(f"Device  : {scope.identify()}")

    print(f"\nCapturing CH{args.ch}...")
    waveform = scope.get_waveform(ch=args.ch, normalize=True)

    if not waveform.voltages:
        print("ERROR: No waveform data")
        sys.exit(1)

    print(f"  Samples     : {len(waveform)}")
    print(f"  Vpp         : {waveform.vpp:.4f} V")
    sr = waveform.sample_rate
    if sr:
        print(f"  Sample rate : {sr/1e6:.3f} MSa/s")
        print(f"  Max freq    : {sr/2/1e3:.1f} kHz (Nyquist)")

    print(f"\nComputing FFT (window={args.window})...")
    freqs, mags, fund_freq, fund_mag = compute_fft(
        waveform.times, waveform.voltages, args.window
    )

    if fund_freq:
        print(f"  Fundamental : {fund_freq/1000:.4f} kHz  ({fund_mag:.2f} dBV)")

    # Print top 5 spectral peaks
    if freqs and mags:
        try:
            import numpy as np
            mag_arr  = np.array(mags[1:])
            freq_arr = np.array(freqs[1:])
            # Simple peak finding: top 5 values
            idx = np.argsort(mag_arr)[-5:][::-1]
            print("\n  Top spectral components:")
            print(f"  {'Frequency':>14}  {'Magnitude':>10}")
            print(f"  {'-'*14}  {'-'*10}")
            for i in idx:
                f = freq_arr[i]
                m = mag_arr[i]
                f_str = f"{f/1000:.4f} kHz" if f >= 1000 else f"{f:.2f} Hz"
                print(f"  {f_str:>14}  {m:>8.2f} dBV")
        except ImportError:
            pass

    # Save
    os.makedirs(args.out, exist_ok=True)
    csv_path = os.path.join(args.out, f"{stamp}_CH{args.ch}_fft.csv")
    with open(csv_path, "w") as f:
        f.write("frequency_Hz,magnitude_dBV\n")
        for freq, mag in zip(freqs, mags):
            f.write(f"{freq:.4f},{mag:.6f}\n")
    print(f"\n  FFT CSV    : {csv_path}")

    if not args.no_plot:
        plot_path = os.path.join(args.out, f"{stamp}_CH{args.ch}_fft.png")
        plot_fft(waveform.times, waveform.voltages, freqs, mags,
                 fund_freq, fund_mag, waveform, plot_path, args)

    print("\nDone.")


if __name__ == "__main__":
    main()
