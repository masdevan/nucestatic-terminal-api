from contextvars import ContextVar

DRY_RUN: ContextVar[bool] = ContextVar("dry_run", default=False)


def is_dry_run() -> bool:
    return DRY_RUN.get()
