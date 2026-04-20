#!/usr/bin/env python3
"""
siggen.py — Signal generator control for HDS200 / HO52S.

The HO52S has a built-in arbitrary function generator (GEN Out port).
This script controls it via SCPI.

Usage:
    python3 siggen.py --wave SINE --freq 1000 --amp 1.5
    python3 siggen.py --wave SQUare --freq 10000 --amp 3.3 --offset 1.65
    python3 siggen.py --wave RAMP --freq 500 --amp 2.0
    python3 siggen.py --status
    python3 siggen.py --off

Waveforms: SINE, SQUare, RAMP, PULSe

Requirements:
    pip install pyserial
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from owonhds import HDS200


def parse_args():
    p = argparse.ArgumentParser(description="Control HDS200 signal generator")
    p.add_argument("--port",   default="/dev/ttyUSB0")
    p.add_argument("--wave",   default=None,
                   choices=["SINE", "SQUare", "RAMP", "PULSe"],
                   help="Waveform type")
    p.add_argument("--freq",   type=float, default=None,
                   help="Frequency in Hz")
    p.add_argument("--amp",    type=float, default=None,
                   help="Amplitude in Vpp")
    p.add_argument("--offset", type=float, default=None,
                   help="DC offset in volts")
    p.add_argument("--on",     action="store_true", help="Enable output")
    p.add_argument("--off",    action="store_true", help="Disable output")
    p.add_argument("--status", action="store_true", help="Print current settings")
    return p.parse_args()


def print_status(scope):
    print("\n── Signal Generator Status ──────────────────────────")
    wave  = scope.siggen_get_waveform()
    freq  = scope.siggen_get_frequency()
    amp   = scope.siggen_get_amplitude()
    print(f"  Waveform  : {wave or '?'}")
    print(f"  Frequency : {freq/1000:.4f} kHz" if freq and freq >= 1000
          else f"  Frequency : {freq:.4f} Hz" if freq else "  Frequency : ?")
    print(f"  Amplitude : {amp:.4f} Vpp" if amp else "  Amplitude : ?")


def main():
    args = parse_args()

    scope = HDS200(port=args.port)
    if not scope.is_connected():
        print(f"ERROR: No scope on {args.port}")
        sys.exit(1)

    print(f"Device: {scope.identify()}")

    if args.status:
        print_status(scope)
        return

    if args.off:
        scope.siggen_output(False)
        print("Signal generator output: OFF")
        return

    changed = False

    if args.wave:
        scope.siggen_set_waveform(args.wave)
        print(f"  Waveform  → {args.wave}")
        changed = True

    if args.freq is not None:
        scope.siggen_set_frequency(args.freq)
        freq_str = f"{args.freq/1000:.4f} kHz" if args.freq >= 1000 \
                   else f"{args.freq:.4f} Hz"
        print(f"  Frequency → {freq_str}")
        changed = True

    if args.amp is not None:
        scope.siggen_set_amplitude(args.amp)
        print(f"  Amplitude → {args.amp:.4f} Vpp")
        changed = True

    if args.offset is not None:
        scope.siggen_set_offset(args.offset)
        print(f"  Offset    → {args.offset:.4f} V")
        changed = True

    if args.on or changed:
        scope.siggen_output(True)
        print("  Output    → ON")

    print_status(scope)
    print("\nDone.")


if __name__ == "__main__":
    main()
