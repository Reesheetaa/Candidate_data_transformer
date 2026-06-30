import json
from pathlib import Path


def write_merge_report(report: dict, output_path: str):

    Path(output_path).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(output_path, "w", encoding="utf8") as f:
        json.dump(
            report,
            f,
            indent=2,
        )