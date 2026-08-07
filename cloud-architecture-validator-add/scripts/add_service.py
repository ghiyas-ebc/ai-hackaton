"""
Stub. Not implemented — see ../SKILL.md for the design intent, in particular
the split between agent-verifiable fields (name, category, description,
references_url, icon) and human-gated fields (network_placement,
reachability, roles) that any real implementation must preserve.

This file performs no fetch, no validation, no write, under any flag
combination.
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="NOT IMPLEMENTED — see SKILL.md before building this out."
    )
    parser.add_argument("--name", help="Service display name (undefined — no agent-validation pipeline exists yet)")
    parser.add_argument("--provider", choices=["gcp", "azure"])
    parser.add_argument("--references-url", help="Provider docs URL for the agent to verify against")
    parser.parse_args()

    sys.exit(
        "cloud-architecture-validator-add is a design stub, not a working "
        "tool. See SKILL.md: 'Before implementing this for real'. Nothing "
        "was validated or written to services.yaml."
    )


if __name__ == "__main__":
    main()
