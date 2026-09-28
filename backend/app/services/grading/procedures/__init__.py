from app.services.grading.procedures.base import MarkAward, Procedure
from app.services.grading.procedures.registry import available_procedures, get_procedure, register
from app.services.grading.procedures import quadratic  # noqa: F401  imported for its @register side effect
from app.services.grading.procedures import simultaneous  # noqa: F401  imported for its @register side effect
from app.services.grading.procedures import like_terms  # noqa: F401  imported for its @register side effect
from app.services.grading.procedures import algebra  # noqa: F401  imported for its @register side effect

__all__ = ["Procedure", "MarkAward", "register", "get_procedure", "available_procedures"]
