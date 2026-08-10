"""Conventions for source assertion rubric identifiers."""


def rubric_id(case_id: str, ordinal: int) -> str:
    if not case_id or ordinal < 1:
        raise ValueError("case_id and positive ordinal required")
    return f"{case_id}-A{ordinal:02d}"
