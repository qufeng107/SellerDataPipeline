from __future__ import annotations

import sys
from collections.abc import Callable
from typing import NoReturn

from seller_data_pipeline.common.exceptions import SellerDataPipelineError


def print_cli_error(exc: BaseException) -> None:
    """Print a concise CLI error without exposing a full traceback for expected failures."""

    print(f"ERROR: {exc}", file=sys.stderr)


def exit_with_cli_error(exc: BaseException) -> NoReturn:
    print_cli_error(exc)
    raise SystemExit(1)


def run_cli_main(main_func: Callable[[], None]) -> None:
    """Run a script main function with project-level friendly error handling."""

    try:
        main_func()
    except SellerDataPipelineError as exc:
        exit_with_cli_error(exc)
