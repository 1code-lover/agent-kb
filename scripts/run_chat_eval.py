from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.api.chat_eval_runner import (
    DEFAULT_EVAL_CASES_PATH,
    DEFAULT_EVAL_SCHEMA_PATH,
    DEFAULT_LAYERED_SUITE_PATH,
    DEFAULT_REPORT_DIR,
    run_eval_semireal,
    run_eval_semireal_suite,
)


def main() -> None:
    """运行本地问答评测并输出报告摘要。"""
    parser = argparse.ArgumentParser(description="运行本地多知识库问答评测")
    parser.add_argument("--cases", default=str(DEFAULT_EVAL_CASES_PATH))
    parser.add_argument("--schema", default=str(DEFAULT_EVAL_SCHEMA_PATH))
    parser.add_argument("--suite", default=None, help=f"分层 suite manifest，默认可用值：{DEFAULT_LAYERED_SUITE_PATH}")
    parser.add_argument("--output-dir", default=str(DEFAULT_REPORT_DIR))
    args = parser.parse_args()

    if args.suite:
        report = run_eval_semireal_suite(
            suite_path=Path(args.suite),
            output_dir=Path(args.output_dir),
        )
        payload = {
            "suite_name": report["suite_name"],
            "suite_passed": report["suite_passed"],
            "totals": report["totals"],
            "layer_summaries": report["layer_summaries"],
            "artifacts": report["artifacts"],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if not report["suite_passed"]:
            raise SystemExit(1)
        return

    report = run_eval_semireal(
        cases_path=Path(args.cases),
        schema_path=Path(args.schema),
        output_dir=Path(args.output_dir),
    )

    payload = {
        "dataset_name": report["dataset_name"],
        "run_passed": report["run_passed"],
        "suite_summary": report["suite_summary"],
        "run_gates": report["run_gates"],
        "artifacts": report["artifacts"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not report["run_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
