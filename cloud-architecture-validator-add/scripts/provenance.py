"""Build provenance blocks. (T006)"""


def build_provenance(sources):
    """Build provenance block: always generated=cloud-architecture-validator-add, status=unverified.

    T006: Provenance builder per FR-007, FR-008.

    Args:
        sources: list of URLs checked to produce the proposal

    Returns:
        dict: {generated: "cloud-architecture-validator-add", status: "unverified", sources: [...]}
    """
    return {
        "generated": "cloud-architecture-validator-add",
        "status": "unverified",
        "sources": sources or []
    }
