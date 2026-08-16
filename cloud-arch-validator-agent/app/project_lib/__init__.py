"""The company's own delivered-project history, separate from the KG.

Plain `app.`-relative imports throughout this package — unlike `app/kg_lib`,
these modules have no bare-name-import history between each other, so they
don't need the `sys.path` insert `tools.py` does for `kg_lib` (and don't
carry the per-file E402 ignore that comes with it).
"""
