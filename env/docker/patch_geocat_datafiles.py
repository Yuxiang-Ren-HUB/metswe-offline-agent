"""Offline shim for geocat.datafiles: it re-downloads registry.txt at import time, which fails in an
air-gapped sandbox even though all data files are cached. Fall back to the registry cached during the
networked warm-up."""
import importlib.util
from pathlib import Path

f = Path(importlib.util.find_spec("geocat.datafiles").origin)
src = f.read_text()
old = '    new_sha256 = hashlib.sha256(requests.get(p.get_url("registry.txt")).content).hexdigest()\n'
new = '''    try:
        new_sha256 = hashlib.sha256(requests.get(p.get_url("registry.txt"), timeout=5).content).hexdigest()
    except Exception:  # offline sandbox: use the registry cached during the networked warm-up
        cached = os.path.join(str(p.abspath), "registry.txt")
        if os.path.exists(cached):
            p.load_registry(cached)
        return
'''
assert old in src, "geocat.datafiles changed; update the shim"
f.write_text(src.replace(old, new))
print("patched", f)
