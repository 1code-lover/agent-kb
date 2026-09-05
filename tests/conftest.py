from __future__ import annotations

import sys
import warnings
from pathlib import Path

from pydantic.warnings import UnsupportedFieldAttributeWarning


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _suppress_known_third_party_warnings() -> None:
    warnings.filterwarnings(
        "ignore",
        message=r".*validate_default.*Field.*",
        category=UnsupportedFieldAttributeWarning,
        module=r"pydantic\._internal\._generate_schema",
    )
    warnings.filterwarnings(
        "ignore",
        message=r"pkg_resources is deprecated as an API\..*",
        category=UserWarning,
        module=r"jieba\._compat",
    )
    warnings.filterwarnings(
        "ignore",
        message=r".*declare_namespace.*google.*",
        category=DeprecationWarning,
        module=r"pkg_resources",
    )


def _prime_known_warning_modules() -> None:
    with warnings.catch_warnings():
        _suppress_known_third_party_warnings()
        try:
            import llama_index.core.node_parser.interface  # noqa: F401
        except Exception:
            pass
        try:
            import jieba  # noqa: F401
        except Exception:
            pass


_suppress_known_third_party_warnings()
_prime_known_warning_modules()


def pytest_configure(config) -> None:  # type: ignore[no-untyped-def]
    _suppress_known_third_party_warnings()
