#!/usr/bin/env python3
"""
terminal.py — Interactive SCPI terminal for HDS200 / HO52S.

A command-line REPL for sending raw SCPI commands to the scope.
Useful for exploring undocumented commands, debugging, and testing.

Features:
  - Tab completion for known commands
  - Command history (up/down arrows)
  - Automatic binary detection for data responses
  - Save last response to file with 'save'
  - Crash protection: known-dangerous commands are flagged

Usage:
    python3 terminal.py
    python3 terminal.py --port /dev/ttyUSB0

Built-in commands (not sent to scope):
    help      Show this help
    list      List all known SCPI commands
    save      Save last response to file
    status    Print scope status summary
    exit/quit Exit the terminal

Requirements:
    pip install pyserial
"""

import os
import readline
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from owonhds import HDS200

# ── Known safe SCPI commands for autocomplete ─────────────────────────────────
KNOWN_COMMANDS = [
    "*IDN?", "*RST", "*CLS", "*OPC?",
    ":CH1:DISP?", ":CH1:SCALE?", ":CH1:OFFSET?", ":CH1:COUP?", ":CH1:PROBE?",
    ":CH2:DISP?", ":CH2:SCALE?", ":CH2:OFFSET?", ":CH2:COUP?", ":CH2:PROBE?",
    ":CH1:DISPlay ON", ":CH1:DISPlay OFF",
    ":CH1:COUPling AC", ":CH1:COUPling DC", ":CH1:COUPling GND",
    ":CH1:PROBe 1X", ":CH1:PROBe 10X", ":CH1:PROBe 100X",
    ":HOR:SCALE?", ":HOR:OFFSET?",
    ":HORIzontal:SCALe?", ":HORIzontal:OFFSet?",
    ":ACQ:MODE?", ":ACQ:DEPMEM?",
    ":ACQuire:MODE?", ":ACQuire:DEPMem?",
    ":ACQuire:MODE SAMPle", ":ACQuire:MODE PEAK",
    ":TRIGger:STATus?",
    ":TRIGger:SINGle:SOURce?", ":TRIGger:SINGle:SOURce CH1",
    ":TRIGger:SINGle:COUPling?", ":TRIGger:SINGle:SWEep?",
    ":TRIGger:SINGle:SWEep AUTO", ":TRIGger:SINGle:SWEep NORMal",
    ":MEASurement:CH1:FREQuency?", ":MEASurement:CH1:PERiod?",
    ":MEASurement:CH1:PKPK?", ":MEASurement:CH1:VAMP?",
    ":MEASurement:CH1:MAX?", ":MEASurement:CH1:MIN?",
    ":MEASurement:CH1:AVERage?",
    ":MEASurement:CH2:FREQuency?", ":MEASurement:CH2:PKPK?",
    ":DATa:WAVe:SCReen:HEAD?",
    ":DATa:WAVe:SCReen:CH1?", ":DATa:WAVe:SCReen:CH2?",
    ":FUNCtion?", ":FUNCtion SINE", ":FUNCtion SQUare",
    ":FUNCtion RAMP", ":FUNCtion PULSe",
    ":FUNCtion:FREQuency?", ":FUNCtion:AMPLitude?",
    ":FUNCtion:OFFSet?", ":FUNCtion:PERiod?",
    ":CHANnel ON", ":CHANnel OFF",
    ":SCPI:DISP?", ":READ?", ":FUNC?",
    ":FUNC DCV", ":FUNC ACV", ":FUNC RES", ":FUNC DIOD",
]

# Commands known to crash the firmware — warn before sending
DANGEROUS_COMMANDS = [
    ":TRIG:TYPE?", ":TRIG:SOU?", ":TRIG:STAT?",
    ":MEAS:FREQ?", ":MEAS:VPP?",
    ":WAV:DATA?", ":WAVeform:DATA?",
    ":DISP:DATA?",
]


class Completer:
    def __init__(self, commands):
        self.commands = commands
        self.matches  = []

    def complete(self, text, state):
        if state == 0:
            self.matches = [c for c in self.commands
                            if c.upper().startswith(text.upper())]
        try:
            return self.matches[state]
        except IndexError:
            return None


def setup_readline():
    try:
        readline.parse_and_bind("tab: complete")
        readline.set_completer(Completer(KNOWN_COMMANDS + ["help","list","save","status","exit","quit"]).complete)
        hist = os.path.expanduser("~/.hds200_history")
        if os.path.exists(hist):
            readline.read_history_file(hist)
        import atexit
        atexit.register(readline.write_history_file, hist)
    except Exception:
        pass


HELP_TEXT = """
HDS200 Interactive SCPI Terminal
─────────────────────────────────────────────────────────────
Built-in commands:
  help      Show this help message
  list      List all known SCPI commands
  save      Save last response to a file
  status    Print scope status summary
  exit      Exit the terminal

SCPI examples:
  *IDN?                              Identify scope
  :CH1:SCALE?                        Get CH1 vertical scale
  :CH1:COUPling DC                   Set CH1 to DC coupling
  :HORIzontal:SCALe 1ms              Set timebase to 1ms/div
  :DATa:WAVe:SCReen:HEAD?            Get waveform header JSON
  :DATa:WAVe:SCReen:CH1?             Get CH1 waveform data
  :MEASurement:CH1:FREQuency?        Measure CH1 frequency
  :TRIGger:STATus?                   Get trigger status
  :FUNCtion SINE                     Set siggen to sine wave
  :FUNCtion:FREQuency 1000           Set siggen to 1 kHz

Tab completion and command history are available.
WARNING: Unknown commands may crash the scope firmware.
         The scope will drop /dev/ttyUSB0. Unplug/replug to recover.
─────────────────────────────────────────────────────────────
"""


def main():
    import argparse
    p = argparse.ArgumentParser(description="Interactive SCPI terminal for HDS200")
    p.add_argument("--port", default="/dev/ttyUSB0")
    args = p.parse_args()

    setup_readline()

    scope = HDS200(port=args.port)
    if not scope.is_connected():
        print(f"ERROR: No scope on {args.port}")
        sys.exit(1)

    print("=" * 60)
    print("HDS200 SCPI Terminal")
    print("=" * 60)
    print(f"Device : {scope.identify()}")
    print("Type 'help' for help. Tab to complete. Ctrl+C or 'exit' to quit.\n")

    last_response = None

    while True:
        try:
            cmd = input("hds200> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not cmd:
            continue

        cmd_lower = cmd.lower()

        # Built-in commands
        if cmd_lower in ("exit", "quit"):
            print("Exiting.")
            break

        elif cmd_lower == "help":
            print(HELP_TEXT)
            continue

        elif cmd_lower == "list":
            print("\nKnown SCPI commands:")
            for c in sorted(KNOWN_COMMANDS):
                print(f"  {c}")
            print()
            continue

        elif cmd_lower == "status":
            print(f"\n  Device     : {scope.identify()}")
            print(f"  Trigger    : {scope.trigger_status()}")
            print(f"  Timebase   : {scope.get_timebase()}")
            print(f"  CH1 scale  : {scope.get_channel_scale(1)}")
            print(f"  CH1 probe  : {scope.get_channel_probe(1)}")
            print(f"  CH1 couple : {scope.get_channel_coupling(1)}")
            print(f"  Acq mode   : {scope.get_acquire_mode()}")
            print(f"  Mem depth  : {scope.get_memory_depth()}")
            print()
            continue

        elif cmd_lower == "save":
            if last_response is None:
                print("  Nothing to save yet.")
            else:
                path = input("  Save to file: ").strip()
                if path:
                    mode = "wb" if isinstance(last_response, bytes) else "w"
                    with open(path, mode) as f:
                        f.write(last_response)
                    size = len(last_response)
                    print(f"  Saved {size} bytes to {path}")
            continue

        # Warn about dangerous commands
        for danger in DANGEROUS_COMMANDS:
            if cmd.upper().startswith(danger.upper()):
                print(f"  WARNING: '{cmd}' is known to crash the firmware.")
                confirm = input("  Send anyway? [y/N] ").strip().lower()
                if confirm != "y":
                    print("  Cancelled.")
                    cmd = None
                break

        if cmd is None:
            continue

        # Determine if we expect binary data
        binary_cmds = [":DATA:WAVE:SCREEN:CH", ":DATa:WAVe:SCReen:CH"]
        is_binary   = any(cmd.upper().startswith(b.upper()) for b in binary_cmds)

        # Send command
        try:
            delay  = 1.5 if is_binary else 0.6
            resp   = scope.query(cmd, delay=delay, binary=is_binary)
            last_response = resp

            if resp is None or resp == b"" or resp == "":
                print("  (no response)")
            elif is_binary:
                import struct
                if len(resp) >= 4:
                    plen = struct.unpack("<I", resp[:4])[0]
                    print(f"  Binary response: {len(resp)} bytes total, "
                          f"payload={plen} bytes")
                    print(f"  First 16 bytes: {resp[:16].hex()}")
                else:
                    print(f"  Binary response: {len(resp)} bytes")
                    print(f"  Hex: {resp.hex()}")
            else:
                print(f"  {resp}")

        except ConnectionError as e:
            print(f"  ERROR: {e}")
            print("  Scope may have dropped connection. Try unplugging/replugging USB.")


if __name__ == "__main__":
    main()
