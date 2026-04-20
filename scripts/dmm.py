#!/usr/bin/env python3
"""
dmm.py — Digital multimeter readout from HDS200 / HO52S.

The HO52S has an independent True-RMS multimeter. This script
reads and logs DMM measurements via SCPI.

Usage:
    python3 dmm.py --func DCV
    python3 dmm.py --func ACV --log --interval 1
    python3 dmm.py --func RES
    python3 dmm.py --func DCA

DMM functions:
    DCV   DC Voltage
    ACV   AC Voltage
    DCA   DC Current
    ACA   AC Current
    RES   Resistance
    DIOD  Diode voltage
    CAP   Capacitance
    BEEP  Continuity

NOTE: DMM SCPI requires activating SCPI mode on the scope.
      The scope must be in Multimeter mode for DMM commands to work.

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
    print("\n\nStopping...")


def parse_args():
    p = argparse.ArgumentParser(description="DMM readout from HDS200")
    p.add_argument("--port",     default="/dev/ttyUSB0")
    p.add_argument("--func",     default="DCV",
                   choices=["DCV","ACV","DCA","ACA","RES","DIOD","CAP","BEEP"],
                   help="DMM function (default: DCV)")
    p.add_argument("--log",      action="store_true",
                   help="Log readings to CSV")
    p.add_argument("--interval", type=float, default=1.0,
                   help="Seconds between readings when logging (default: 1.0)")
    p.add_argument("--count",    type=int, default=None,
                   help="Number of readings then stop")
    p.add_argument("--out",      default=".", help="Output directory for log")
    return p.parse_args()


UNITS = {
    "DCV":  "V",
    "ACV":  "V",
    "DCA":  "A",
    "ACA":  "A",
    "RES":  "Ω",
    "DIOD": "V",
    "CAP":  "F",
    "BEEP": "",
}

FUNC_NAMES = {
    "DCV":  "DC Voltage",
    "ACV":  "AC Voltage",
    "DCA":  "DC Current",
    "ACA":  "AC Current",
    "RES":  "Resistance",
    "DIOD": "Diode",
    "CAP":  "Capacitance",
    "BEEP": "Continuity",
}


def main():
    global _running
    args = parse_args()
    signal.signal(signal.SIGINT, handle_sigint)

    scope = HDS200(port=args.port)
    if not scope.is_connected():
        print(f"ERROR: No scope on {args.port}")
        sys.exit(1)

    print("=" * 60)
    print("HDS200 Digital Multimeter")
    print("=" * 60)
    print(f"Device   : {scope.identify()}")
    print(f"Function : {FUNC_NAMES.get(args.func, args.func)}")
    print()

    # Activate DMM SCPI mode
    print("Activating DMM SCPI mode...")
    if scope.dmm_activate_scpi():
        print("  DMM SCPI mode active.")
    else:
        print("  WARNING: DMM SCPI activation failed.")
        print("  Make sure the scope is in Multimeter mode.")
        print("  Press Mode button on scope to switch modes.")

    # Set function
    scope.dmm_set_function(args.func)
    unit = UNITS.get(args.func, "")

    if not args.log:
        # Single reading
        val = scope.dmm_read()
        if val is not None:
            print(f"Reading: {val:.6g} {unit}")
        else:
            print("Reading: --- (no response)")
        return

    # Logging mode
    stamp    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(args.out, exist_ok=True)
    log_path = os.path.join(args.out, f"{stamp}_dmm_{args.func.lower()}.csv")

    print(f"Logging to: {log_path}")
    print("Press Ctrl+C to stop.\n")

    count = 0
    start = time.time()

    with open(log_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "elapsed_s", f"value_{unit}"])

        while _running:
            if args.count and count >= args.count:
                break

            ts      = datetime.datetime.now().isoformat()
            elapsed = time.time() - start
            val     = scope.dmm_read()
            count  += 1

            if val is not None:
                writer.writerow([ts, f"{elapsed:.3f}", f"{val:.8g}"])
                f.flush()
                print(f"  [{count:>4}] {ts}  {val:.6g} {unit}")
            else:
                writer.writerow([ts, f"{elapsed:.3f}", ""])
                print(f"  [{count:>4}] {ts}  ---")

            time.sleep(args.interval)

    print(f"\nLog saved: {log_path}  ({count} readings)")


if __name__ == "__main__":
    main()
