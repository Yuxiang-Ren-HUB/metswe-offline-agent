---
name: api-docs
description: Offline documentation for the libraries installed in this sandbox. There is no internet here; use this to find the right function and check its exact signature before calling it.
---

# Offline API documentation

The sandbox has no network access, so you cannot look up library documentation online.
This skill searches the signatures and docstrings of the third-party packages that the
repository imports (numpy, xarray, pandas, ... whatever is installed), entirely offline.

Use it when:
- you know what you want to do but not which function does it;
- you are about to call a library function and are unsure of its name, arguments or behaviour;
- a call failed with `AttributeError`, `TypeError: unexpected keyword argument`, or `ImportError`.

Run it with `run_skill_script(skill_name="api-docs", file_path="scripts/search_api_docs.py", args=[...])`:

- Search by description: `args=["interpolate a DataArray onto new coordinates"]`
- Restrict to one package: `args=["dewpoint from relative humidity", "--package", "metpy"]`
- Full docstring of one API: `args=["--show", "numpy.nanmax"]`

Each result line is `name(signature) [kind] first sentence of the docstring`.
If `--show` says a name does not exist, do not call it: search by description instead.
