"""Search the APIs of the libraries installed in this sandbox, offline.

Usage (from the agent, via run_skill_script):
    search_api_docs.py "interpolate a DataArray onto new coordinates"
    search_api_docs.py "dewpoint from relative humidity" --package metpy -k 5
    search_api_docs.py --show xarray.DataArray.interp

By default the index covers the third-party packages imported by the code in /workspace. It is built
statically from .py/.pyi files with `ast` (nothing is imported), cached under /tmp, and searched with
BM25 over identifier pieces, parameter names and the first paragraph of each docstring.
Standard library only, so it runs in any sandbox.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

WORKSPACE = Path(os.environ.get("APIDOCS_WORKSPACE", "/workspace"))
CACHE_DIR = Path(os.environ.get("APIDOCS_CACHE", "/tmp"))
STOP = set("a an the of to in on for and or is are be by with as at from this that it its into "
           "if not no can will return returns value values given use used using".split())
SKIP_IMPORTS = {"setuptools", "pytest", "pkg_resources", "_pytest", "conftest", "distutils", "versioneer"}


# ---------------------------------------------------------------- indexing
SUFFIXES = ("ations", "ation", "ating", "ates", "ate", "ings", "ing", "ed", "es", "s")


def stem(t):
    """Very light stemming so that resample/resampling and interpolate/interpolation meet."""
    for suf in SUFFIXES:
        if t.endswith(suf) and len(t) - len(suf) >= 4:
            t = t[: -len(suf)]
            break
    return t[:-1] if t.endswith("e") and len(t) > 4 else t


def tokens(text):
    return [stem(t.lower()) for t in re.findall(r"[A-Za-z][a-z]*|[A-Z]+(?![a-z])|\d+", text)
            if len(t) > 1 and t.lower() not in STOP]


def first_paragraph(doc, limit=300):
    return " ".join((doc or "").strip().split("\n\n")[0].split())[:limit]


def package_root(name):
    try:
        spec = importlib.util.find_spec(name)  # finds files; does not execute the package
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.submodule_search_locations:
        return None
    root = Path(list(spec.submodule_search_locations)[0])
    try:
        root.relative_to(WORKSPACE)
        return None  # the repository itself is not part of the documentation pack
    except ValueError:
        return root


def module_name(pkg, root, path):
    parts = [pkg] + list(path.relative_to(root).with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def is_private(modname):
    return any(p.startswith("_") for p in modname.split(".")[1:]) or ".tests" in modname


def signature(fn):
    try:
        return f"({ast.unparse(fn.args)})"
    except Exception:
        return "(...)"


def index_file(path, modname, out):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError):
        return

    def add(qual, kind, sig, doc):
        out.append({"name": qual, "kind": kind, "sig": sig, "doc": first_paragraph(doc), "full_doc": (doc or "")[:4000]})

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            add(f"{modname}.{node.name}", "function", signature(node), ast.get_docstring(node))
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            cls = f"{modname}.{node.name}"
            init = next((n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"), None)
            add(cls, "class", signature(init) if init else "", ast.get_docstring(node))
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and not sub.name.startswith("_"):
                    prop = any(getattr(d, "id", None) == "property" for d in sub.decorator_list)
                    add(f"{cls}.{sub.name}", "property" if prop else "method", "" if prop else signature(sub),
                        ast.get_docstring(sub))


def reexports(root, pkg):
    """defining name -> public name, from `from X import Y` in public __init__ files (numpy 2, scipy...)."""
    alias = {}
    for init in sorted(list(root.rglob("__init__.py")) + list(root.rglob("__init__.pyi"))):
        here = module_name(pkg, root, init)
        if is_private(here):
            continue
        try:
            tree = ast.parse(init.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, ValueError):
            continue
        for node in tree.body:
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.level >= 1:
                base = here.split(".")
                base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                src = ".".join(base + ([node.module] if node.module else []))
            elif node.module and node.module.split(".")[0] == pkg:
                src = node.module
            else:
                continue
            for a in node.names:
                key = src + ".*" if a.name == "*" else f"{src}.{a.name}"
                public = here if a.name == "*" else f"{here}.{a.asname or a.name}"
                if key not in alias or len(public) < len(alias[key]):
                    alias[key] = public
    return alias


def resolve_alias(name, alias):
    parts = name.split(".")
    for cut in range(len(parts), 1, -1):
        head = ".".join(parts[:cut])
        if head in alias:
            return ".".join([alias[head]] + parts[cut:])
        star = ".".join(parts[: cut - 1]) + ".*"
        if star in alias:
            return ".".join([alias[star]] + parts[cut - 1:])
    return None


def index_package(pkg):
    root = package_root(pkg)
    if root is None:
        return []
    stub, src = [], []
    for path in sorted(root.rglob("*.pyi")):
        m = module_name(pkg, root, path)
        if ".tests" not in m:
            index_file(path, m, stub)
    for path in sorted(root.rglob("*.py")):
        m = module_name(pkg, root, path)
        if ".tests" not in m:
            index_file(path, m, src)
    # stubs: precise signatures, usually no docstrings, sometimes `nanmax = amax` -> merge with sources
    by_name = {e["name"]: e for e in stub}
    found = list(stub)
    for e in src:
        s = by_name.get(e["name"])
        if s is None:
            found.append(e)
        elif not s["doc"] and e["doc"]:
            s["doc"], s["full_doc"] = e["doc"], e["full_doc"]
    alias = reexports(root, pkg)
    kept = []
    for e in found:
        pub = resolve_alias(e["name"], alias)
        if pub and pub != e["name"]:
            e["alias"] = pub
        owner = e["name"].rsplit(".", 1)[0] if e["kind"] in ("function", "class") else e["name"].rsplit(".", 2)[0]
        if not is_private(owner) or "alias" in e:
            kept.append(e)
    return kept


def imported_packages():
    """Top-level third-party packages imported anywhere in the repository."""
    names = set()
    for path in WORKSPACE.rglob("*.py"):
        if any(p in path.parts for p in (".git", "build", "dist", ".tox")):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    return sorted(n for n in names if n not in stdlib and n not in SKIP_IMPORTS and package_root(n))


def load_index(packages):
    key = hashlib.sha1(",".join(packages).encode()).hexdigest()[:12]
    cache = CACHE_DIR / f"_apidocs_{key}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    entries = []
    for p in packages:
        entries += index_package(p)
    try:
        cache.write_text(json.dumps(entries), encoding="utf-8")
    except OSError:
        pass
    return entries


# ---------------------------------------------------------------- search
def is_public_name(name):
    """Short public paths (numpy.nanmax, xarray.DataArray.resample) rather than internal module paths."""
    parts = name.split(".")
    return len(parts) <= 3 and not any(p.startswith("_") or p in ("core", "internal", "internals") for p in parts)


class BM25:
    PUBLIC_BOOST = 1.5

    def __init__(self, entries, k1=1.2, b=0.75):
        self.e, self.k1, self.b = entries, k1, b
        self.docs = []
        for e in entries:
            shown = e.get("alias") or e["name"]
            rest = e["full_doc"][len(e["doc"]):][:600] if e.get("full_doc") else ""
            self.docs.append(Counter(tokens(shown) + tokens(shown.rsplit(".", 1)[-1]) * 2 + tokens(e["sig"])
                                     + tokens(e["doc"]) * 2 + tokens(rest)))
        self.boost = [self.PUBLIC_BOOST if is_public_name(e.get("alias") or e["name"]) else 1.0 for e in entries]
        self.len = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.len) / max(len(self.len), 1)
        self.post = defaultdict(list)
        for i, d in enumerate(self.docs):
            for t in d:
                self.post[t].append(i)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.post.items()}

    def search(self, query, k):
        scores = defaultdict(float)
        for t in set(tokens(query)):
            for i in self.post.get(t, ()):
                tf = self.docs[i][t]
                scores[i] += self.idf[t] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
        hits, seen = [], set()
        for i, _ in sorted(scores.items(), key=lambda x: -x[1] * self.boost[x[0]]):
            shown = self.e[i].get("alias") or self.e[i]["name"]
            if shown not in seen:  # stub overloads and re-exports produce duplicates
                seen.add(shown)
                hits.append(self.e[i])
            if len(hits) == k:
                break
        return hits


def show(entries, name):
    for e in entries:
        if name in (e["name"], e.get("alias")):
            return f"{e.get('alias') or e['name']}{e['sig']}  [{e['kind']}]\n{e['full_doc'] or '(no docstring)'}"
    tail = "." + name.rsplit(".", 1)[-1]
    close = sorted({e.get("alias") or e["name"] for e in entries if (e.get("alias") or e["name"]).endswith(tail)})
    msg = f"'{name}' is not an API of the indexed packages."
    return msg + (f" Did you mean: {', '.join(close[:8])}" if close else " It may not exist; search by description instead.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("query", nargs="*", help="what you want to do, in words or identifiers")
    ap.add_argument("--package", action="append", help="restrict to these top-level packages")
    ap.add_argument("--show", help="print the full docstring of one API, e.g. numpy.nanmax")
    ap.add_argument("-k", type=int, default=8)
    a = ap.parse_args()
    packages = sorted(a.package) if a.package else imported_packages()
    entries = load_index(packages)
    if not entries:
        print(f"No documentation indexed (packages: {packages or 'none found'}).")
        return
    if a.show:
        print(show(entries, a.show))
        return
    if not a.query:
        print(f"Indexed {len(entries)} APIs from: {', '.join(packages)}. Pass a query or --show NAME.")
        return
    hits = BM25(entries).search(" ".join(a.query), a.k)
    if not hits:
        print("No matching API found. Try other words, or --show with a full name.")
    for e in hits:
        print(f"{e.get('alias') or e['name']}{e['sig']}  [{e['kind']}]  {e['doc'][:160]}")


if __name__ == "__main__":
    main()
