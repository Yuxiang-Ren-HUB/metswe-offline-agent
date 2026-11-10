# Compatibility shim: `xdrlib` was removed from the standard library in Python 3.13 and older Py-ART
# imports it directly. Same approach as the official sandbox's imp.py / telnetlib.py shims.
from mda_xdrlib.xdrlib import *  # noqa: F401,F403
from mda_xdrlib.xdrlib import ConversionError, Error, Packer, Unpacker  # noqa: F401
