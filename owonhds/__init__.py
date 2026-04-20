"""
owonhds — Python library for the OWON HDS200 series handheld oscilloscope.
Tested on Hanmatek HO52S (OWON firmware V8.0.1, VID 5345:1234).
"""
from .device import HDS200
from .waveform import Waveform

__version__ = "1.0.0"
__all__ = ["HDS200", "Waveform"]
