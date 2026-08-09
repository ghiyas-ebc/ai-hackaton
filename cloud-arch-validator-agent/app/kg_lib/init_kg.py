"""
Stub. Not implemented — see ../SKILL.md for the design intent and the hard
constraints (never auto-write services.yaml) any real implementation must
keep.

This file exists so the skill has something to point `python3
scripts/init_kg.py` at instead of a bare "file not found," and so an argparse
--help gives a truthful answer about what's missing rather than nothing at
all. It performs no fetch, no parse, no write, under any flag combination.
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="NOT IMPLEMENTED — see SKILL.md before building this out."
    )
    parser.add_argument("--source", help="URL or path of the public service catalog (undefined — no source has been specified yet)")
    parser.add_argument("--version-tag", help="Label for this sync, for rollback (undefined — versioning scheme not designed yet)")
    parser.add_argument("--dry-run", action="store_true", help="Would produce a review queue instead of writing; not implemented either way")
    parser.parse_args()

    sys.exit(
        "cloud-architecture-validator-init is a design stub, not a working "
        "tool. See SKILL.md: 'Before implementing this for real'. Nothing "
        "was fetched or written."
    )


if __name__ == "__main__":
    main()
