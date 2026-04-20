#!/usr/bin/env python3
"""
log.py — Timed interval data logger for HDS200 scope.

Captures measurements (and optionally waveforms) at a set interval
and logs them to a timestamped CSV. Useful for signal monitoring,
trend analysis, and long-duration recording.

Usage:
    python3 log.py
    python3 log.py --interval 5 --duration 3600 --out ~/Oscilloscope
    python3 log.py --interval 1 --waveforms  (also save waveform CSVs)
    python3 log.py --interval 10 --count 100

Press Ctrl+C to stop early. Partial log is always saved.

Requirements:
    pip install pyserial
"""

import argparse
import csv
import datetime
import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from owonhds import HDS200

_running = True


def handle_sigint(sig, frame):
    global _running
    _running = False
    print("\n\nStopping logger...")


def parse_args():
    p = argparse.ArgumentParser(description="Interval logger for HDS200")
    p.add_argument("--port",      default="/dev/ttyUSB0")
    p.add_argument("--ch",        type=int, default=1, choices=[1, 2])
    p.add_argument("--interval",  type=float, default=5.0,
                   help="Seconds between captures (default: 5)")
    p.add_argument("--duration",  type=float, default=None,
                   help="Total logging duration in seconds (default: unlimited)")
    p.add_argument("--count",     type=int, default=None,
                   help="Number of captures then stop (default: unlimited)")
    p.add_argument("--out",       default=".", help="Output directory")
    p.add_argument("--waveforms", action="store_true",
                   help="Also save full waveform CSV per capture")
    return p.parse_args()


def main():
    global _running
    args  = parse_args()
    signal.signal(signal.SIGINT, handle_sigint)

    stamp    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(args.out, exist_ok=True)
    log_path = os.path.join(args.out, f"{stamp}_CH{args.ch}_log.csv")

    scope = HDS200(port=args.port)
    if not scope.is_connected():
        print(f"ERROR: No scope on {args.port}")
        sys.exit(1)

    print("=" * 60)
    print("HDS200 Interval Logger")
    print("=" * 60)
    print(f"Device   : {scope.identify()}")
    print(f"Channel  : CH{args.ch}")
    print(f"Interval : {args.interval}s")
    print(f"Duration : {args.duration}s" if args.duration else "Duration : unlimited")
    print(f"Count    : {args.count}" if args.count else "Count    : unlimited")
    print(f"Log file : {log_path}")
    print(f"Waveforms: {'yes' if args.waveforms else 'no'}")
    print("\nPress Ctrl+C to stop.\n")

    fieldnames = [
        "timestamp", "elapsed_s",
        "frequency_Hz", "period_s",
        "vpp_V", "vamp_V", "vmax_V", "vmin_V", "vaverage_V",
        "trigger_status", "timebase", "scale", "probe", "coupling",
    ]

    start_time   = time.time()
    capture_num  = 0

    with open(log_path, "w", newline="") as logfile:
        writer = csv.DictWriter(logfile, fieldnames=fieldnames)
        writer.writeheader()

        while _running:
            # Check stop conditions
            if args.count and capture_num >= args.count:
                print(f"\nReached {args.count} captures. Done.")
                break
            if args.duration and (time.time() - start_time) >= args.duration:
                print(f"\nDuration {args.duration}s elapsed. Done.")
                break

            t0 = time.time()
            capture_num += 1
            ts = datetime.datetime.now().isoformat()
            elapsed = time.time() - start_time

            try:
                meas    = scope.measure_all(args.ch)
                trig    = scope.trigger_status()
                tb      = scope.get_timebase()
                scale   = scope.get_channel_scale(args.ch)
                probe   = scope.get_channel_probe(args.ch)
                coupling = scope.get_channel_coupling(args.ch)

                row = {
                    "timestamp":    ts,
                    "elapsed_s":    f"{elapsed:.3f}",
                    "frequency_Hz": meas.get("frequency") or "",
                    "period_s":     meas.get("period") or "",
                    "vpp_V":        meas.get("vpp") or "",
                    "vamp_V":       meas.get("vamp") or "",
                    "vmax_V":       meas.get("vmax") or "",
                    "vmin_V":       meas.get("vmin") or "",
                    "vaverage_V":   meas.get("vaverage") or "",
                    "trigger_status": trig,
                    "timebase":     tb,
                    "scale":        scale,
                    "probe":        probe,
                    "coupling":     coupling,
                }
                writer.writerow(row)
                logfile.flush()

                freq = meas.get("frequency")
                vpp  = meas.get("vpp")
                print(f"  [{capture_num:>4}] {ts}  "
                      f"freq={freq/1000:.3f}kHz  " if freq and freq >= 1000 else
                      f"  [{capture_num:>4}] {ts}  "
                      f"freq={freq:.3f}Hz  " if freq else
                      f"  [{capture_num:>4}] {ts}  freq=---  ",
                      end="")
                print(f"Vpp={vpp:.4f}V" if vpp else "Vpp=---")

                # Optionally save full waveform
                if args.waveforms:
                    try:
                        waveform = scope.get_waveform(ch=args.ch, normalize=True)
                        wv_path  = os.path.join(
                            args.out,
                            f"{stamp}_{capture_num:04d}_CH{args.ch}_wave.csv"
                        )
                        waveform.save_csv(wv_path)
                    except Exception as e:
                        print(f"    (waveform save failed: {e})")

            except Exception as e:
                print(f"  [{capture_num:>4}] ERROR: {e}")
                writer.writerow({
                    "timestamp": ts, "elapsed_s": f"{elapsed:.3f}",
                    **{k: "" for k in fieldnames if k not in ("timestamp","elapsed_s")}
                })
                logfile.flush()

            # Wait for next interval
            elapsed_this = time.time() - t0
            wait = max(0, args.interval - elapsed_this)
            waited = 0.0
            while _running and waited < wait:
                time.sleep(0.1)
                waited += 0.1

    print(f"\nLog saved: {log_path}  ({capture_num} captures)")


if __name__ == "__main__":
    main()
