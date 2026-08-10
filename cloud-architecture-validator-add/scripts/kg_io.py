"""Load/write/lookup for services.yaml. (T003, T004, T008, T019)"""

from pathlib import Path
from datetime import datetime


def load_services(yaml_path):
    """Load services.yaml preserving list order. Returns dict {services: [...]}.

    T003: Round-trip load for append/replace.
    """
    import yaml
    with open(yaml_path) as f:
        return yaml.safe_load(f) or {"services": []}


def write_services(yaml_path, services_dict):
    """Write services_dict back to yaml_path without reformatting unmodified entries.

    T003: Round-trip write after append/replace.
    """
    import yaml
    with open(yaml_path, "w") as f:
        yaml.dump(services_dict, f, default_flow_style=False, sort_keys=False)


def find_existing(services, name, provider):
    """Case-insensitive (name, provider) lookup in services list.

    Returns matching entry dict or None.
    T004: Duplicate detection, feeds FR-002 branch.
    """
    if not services or "services" not in services:
        return None

    name_lower = name.lower()
    provider_lower = provider.lower()

    for entry in services["services"]:
        if (entry.get("name", "").lower() == name_lower and
            entry.get("provider", "").lower() == provider_lower):
            return entry

    return None


def write_entry(yaml_path, services_dict, entry, mode="append"):
    """Append (new entry) or replace (update existing) in services_dict.

    T008: Write path, called from main() after all judgment fields confirmed.
    Always goes through this function, never hand-constructed YAML writes (FR-009).

    Args:
        yaml_path: Path to services.yaml
        services_dict: Loaded services dict
        entry: New or updated entry dict
        mode: "append" or "replace"

    Returns:
        Updated services_dict
    """
    if "services" not in services_dict:
        services_dict["services"] = []

    if mode == "append":
        services_dict["services"].append(entry)
    elif mode == "replace":
        # Find and replace matching (name, provider)
        name_lower = entry.get("name", "").lower()
        provider_lower = entry.get("provider", "").lower()

        for i, svc in enumerate(services_dict["services"]):
            if (svc.get("name", "").lower() == name_lower and
                svc.get("provider", "").lower() == provider_lower):
                services_dict["services"][i] = entry
                break

    write_services(yaml_path, services_dict)
    return services_dict


def is_newer(reference_checked_at, existing_entry):
    """Check if reference_checked_at is newer than entry's last-checked date.

    T019: Staleness check for update path (US4).

    Follows spec Assumption:
    - If existing_entry has provenance.verified date: compare against that
    - Else use entry write time (if available, else treat as always-stale)
    - Always-stale = any reference triggers update proposal

    Args:
        reference_checked_at: datetime or string (ISO format) of reference fetch date
        existing_entry: dict from services list

    Returns:
        bool: True if reference is demonstrably newer
    """
    if isinstance(reference_checked_at, str):
        try:
            reference_checked_at = datetime.fromisoformat(reference_checked_at)
        except (ValueError, TypeError):
            return True  # Can't parse → assume newer

    prov = existing_entry.get("provenance", {})
    last_checked = prov.get("verified")

    if last_checked:
        try:
            last_checked = datetime.fromisoformat(last_checked)
            return reference_checked_at > last_checked
        except (ValueError, TypeError):
            return True  # Malformed date in entry → assume newer

    # No verified date found → always-stale, any reference is newer
    return True
