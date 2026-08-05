from __future__ import annotations

import argparse
import json
from pathlib import Path

from tests.api.chat_eval_runner import (
    DEFAULT_EVAL_CASES_PATH,
    DEFAULT_EVAL_SCHEMA_PATH,
    DEFAULT_REPORT_DIR,
    run_eval_v1_semireal,
)


def main() -> None:
    """运行本地问答评测并输出报告摘要。"""
    parser = argparse.ArgumentParser(description="运行本地多知识库问答评测")
    parser.add_argument("--cases", default=str(DEFAULT_EVAL_CASES_PATH))
    parser.add_argument("--schema", default=str(DEFAULT_EVAL_SCHEMA_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_REPORT_DIR))
    args = parser.parse_args()

    report = run_eval_v1_semireal(
        cases_path=Path(args.cases),
        schema_path=Path(args.schema),
        output_dir=Path(args.output_dir),
    )

    summary = report["suite_summary"]
    payload = {
        "dataset_name": report["dataset_name"],
        "run_passed": report["run_passed"],
        "suite_summary": summary,
        "run_gates": report["run_gates"],
        "artifacts": report["artifacts"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not report["run_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
