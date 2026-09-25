from app.services.grading.procedures.base import Procedure

_PROCEDURES: dict[str, type[Procedure]] = {}


def get_procedure(name: str) -> Procedure:
    try:
        procedure_cls = _PROCEDURES[name]
    except KeyError:
        available = ", ".join(sorted(_PROCEDURES)) or "none registered"
        raise ValueError(f"Unknown procedure {name!r}. Available procedures: {available}") from None

    return procedure_cls()


def register(procedure_cls: type[Procedure]) -> type[Procedure]:
    name = getattr(procedure_cls, "name", None)
    if not name:
        raise ValueError(f"{procedure_cls!r} must define a non-empty 'name' to be registered")

    if name in _PROCEDURES:
        raise ValueError(f"Procedure {name!r} is already registered")

    _PROCEDURES[name] = procedure_cls
    return procedure_cls


def available_procedures() -> list[str]:
    return sorted(_PROCEDURES)
