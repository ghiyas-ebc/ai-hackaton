"""Judgment question batch gating. (T007)"""


class JudgmentQuestionBatch:
    """Three judgment fields: network_placement, reachability, roles.

    T007: State tracking per data-model.md.
    """

    def __init__(self):
        """Start with all fields unanswered."""
        self.network_placement = "unanswered"
        self.reachability = "unanswered"
        self.roles = "unanswered"

    def set_answer(self, field, value):
        """Set field to 'answered' state with the value."""
        if field in ("network_placement", "reachability", "roles"):
            setattr(self, field, value)

    def set_draft(self, field, value, rationale=""):
        """Set field to 'draft' state (from update proposal). Value is the draft, not yet confirmed."""
        if field in ("network_placement", "reachability", "roles"):
            setattr(self, field, {"state": "draft", "value": value, "rationale": rationale})

    def is_draft(self, field):
        """Check if field is in draft state."""
        val = getattr(self, field, None)
        return isinstance(val, dict) and val.get("state") == "draft"

    def is_answered(self, field):
        """Check if field is in answered state (not unanswered, not draft)."""
        val = getattr(self, field, None)
        return val not in ("unanswered", None) and not self.is_draft(field)

    def all_answered(self):
        """Return True only when every field is answered (no unanswered, no draft). FR-005."""
        return (self.is_answered("network_placement") and
                self.is_answered("reachability") and
                self.is_answered("roles"))

    def to_dict(self):
        """Return confirmed values as dict (drop draft wrappers)."""
        result = {}
        for field in ("network_placement", "reachability", "roles"):
            val = getattr(self, field, None)
            if isinstance(val, dict):
                result[field] = val.get("value")
            elif val != "unanswered":
                result[field] = val
        return result
