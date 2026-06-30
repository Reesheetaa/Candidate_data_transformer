"""CLI entrypoint for the Candidate Data Transformation Pipeline.

Usage:
    python src/main.py \\
        --csv sample_input/recruiter.csv \\
        --resume sample_input/resume.txt \\
        --notes sample_input/recruiter_notes.txt \\
        --config config/default_config.json

Produces output/canonical.json and output/<config-name>_output.json.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

# Allow `python src/main.py ...` to work without manually setting PYTHONPATH,
# by ensuring the project root (parent of src/) is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import typer

from src.adapters.csv_adapter import CsvAdapter
from src.adapters.notes_adapter import NotesAdapter
from src.adapters.resume_adapter import ResumeAdapter
from src.merger import merge_candidate
from src.models import PartialCandidate
from src.projector import project
from src.validator import validate_candidate, validate_config

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("candidate_transformer")

app = typer.Typer(add_completion=False)


def _group_partials_by_candidate(partials: list[PartialCandidate]) -> list[list[PartialCandidate]]:
    """Group PartialCandidate objects across sources into per-person buckets.

    Matching strategy (deterministic, documented in README as a known limitation):
      1. If there is exactly one CSV-derived candidate, every unstructured
         (resume/notes) partial is attached to it — this is the common single
         candidate case the sample inputs exercise.
      2. Otherwise, partials are matched by shared `candidate_key`
         (typically a normalized email or name) when available.
      3. Any unstructured partial that cannot be matched becomes its own
         standalone candidate rather than being silently dropped.
    """
    csv_partials = [p for p in partials if p.source == "csv"]
    other_partials = [p for p in partials if p.source != "csv"]

    if len(csv_partials) == 1 and other_partials:
        return [csv_partials + other_partials]

    groups: dict[str, list[PartialCandidate]] = {}
    unmatched: list[list[PartialCandidate]] = []

    for p in csv_partials:
        key = p.candidate_key or f"__csv_{len(groups)}"
        groups.setdefault(key, []).append(p)

    for p in other_partials:
        if p.candidate_key and p.candidate_key in groups:
            groups[p.candidate_key].append(p)
        else:
            unmatched.append([p])

    return list(groups.values()) + unmatched


# def run_pipeline(csv_path: Optional[str], resume_path: Optional[str], notes_path: Optional[str]) -> list:
def run_pipeline(
    csv_path: Optional[str],
    resume_path: Optional[str],
    notes_path: Optional[str],
    resume_dir: Optional[str],
    notes_dir: Optional[str],
) -> list:
    """Run adapters -> grouping -> merge for all configured input sources.
    Returns a list of CanonicalCandidate objects. Never raises on missing files."""
    # partials: list[PartialCandidate] = []

    # if csv_path:
    #     partials.extend(CsvAdapter().parse(csv_path))
    # else:
    #     logger.info("No CSV provided; skipping structured source.")

    # if resume_path:
    #     partials.extend(ResumeAdapter().parse(resume_path))
    # else:
    #     logger.info("No resume provided; skipping resume source.")

    # if notes_path:
    #     partials.extend(NotesAdapter().parse(notes_path))
    # else:
    #     logger.info("No recruiter notes provided; skipping notes source.")

    # if not partials:
    #     logger.warning("No usable input from any source — producing no candidates.")
    #     return []

    # grouped = _group_partials_by_candidate(partials)
    # return [merge_candidate(group, idx) for idx, group in enumerate(grouped)]

    partials: list[PartialCandidate] = []

    # ----------------------------
    # CSV
    # ----------------------------

    if csv_path:
        partials.extend(
            CsvAdapter().parse(csv_path)
        )
    else:
        logger.info("No CSV provided.")

    # ----------------------------
    # Single Resume
    # ----------------------------

    if resume_path:
        partials.extend(
            ResumeAdapter().parse(resume_path)
        )

    # ----------------------------
    # Resume Directory
    # ----------------------------

    if resume_dir:

        folder = Path(resume_dir)

        if folder.exists():

            for file in sorted(folder.iterdir()):

                if file.suffix.lower() not in {
                    ".txt",
                    ".pdf",
                }:
                    continue

                partials.extend(
                    ResumeAdapter().parse(
                        str(file)
                    )
                )

    # ----------------------------
    # Single Notes
    # ----------------------------

    if notes_path:
        partials.extend(
            NotesAdapter().parse(notes_path)
        )

    # ----------------------------
    # Notes Directory
    # ----------------------------

    if notes_dir:

        folder = Path(notes_dir)

        if folder.exists():

            for file in sorted(folder.iterdir()):

                if file.suffix.lower() != ".txt":
                    continue

                partials.extend(
                    NotesAdapter().parse(
                        str(file)
                    )
                )

    if not partials:

        logger.warning(
            "No usable input from any source."
        )

        return []

    grouped = _group_partials_by_candidate(
        partials
    )

    return [
        merge_candidate(group, idx)
        for idx, group in enumerate(grouped)
    ]



@app.command()
def main(
    csv: Optional[str] = typer.Option(None, "--csv", help="Path to recruiter CSV export."),
    resume: Optional[str] = typer.Option(None, "--resume", help="Path to resume (.pdf or .txt)."),
    notes: Optional[str] = typer.Option(None, "--notes", help="Path to recruiter notes (.txt)."),
    resume_dir: Optional[str] = typer.Option(
        None,
        "--resume-dir",
        help="Directory containing resumes (.txt/.pdf).",
    ),

    notes_dir: Optional[str] = typer.Option(
        None,
        "--notes-dir",
        help="Directory containing recruiter notes (.txt).",
    ),
    config: str = typer.Option(..., "--config", help="Path to a projection config JSON file."),
    output_dir: str = typer.Option("output", "--output-dir", help="Directory to write JSON outputs to."),
) -> None:
    """Run the candidate transformation pipeline end-to-end."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    if resume and resume_dir:
        raise typer.BadParameter(
            "Use either --resume or --resume-dir, not both."
        )

    if notes and notes_dir:
        raise typer.BadParameter(
            "Use either --notes or --notes-dir, not both."
        )

    # candidates = run_pipeline(csv, resume, notes)
    candidates = run_pipeline(
        csv,
        resume,
        notes,
        resume_dir,
        notes_dir,
    )
    if not candidates:
        typer.echo("No candidates produced. Check that at least one input file is valid.")
        raise typer.Exit(code=0)

    config_path = Path(config)
    try:
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        typer.echo(f"Could not read config at {config}: {exc}")
        raise typer.Exit(code=1)

    canonical_payload = [c.model_dump() for c in candidates]
    (out_dir / "canonical.json").write_text(json.dumps(canonical_payload, indent=2), encoding="utf-8")
    logger.info("Wrote %s", out_dir / "canonical.json")

    projected_payload = []
    config_name = config_path.stem
    for candidate in candidates:
        config_warnings = validate_config(config_data, candidate)
        for warning in config_warnings:
            logger.warning("[config] %s", warning)

        data_result = validate_candidate(candidate)
        for warning in data_result.warnings:
            logger.warning("[%s] %s", candidate.candidate_id, warning)
        for error in data_result.errors:
            logger.error("[%s] %s", candidate.candidate_id, error)

        projected = project(candidate, config_data)
        projected_payload.append(projected)

    if config_name == "default_config":
        output_name = "default_output.json"
    elif config_name == "custom_config":
        output_name = "custom_output.json"
    else:
        output_name = f"{config_name}_output.json"

    out_path = out_dir / output_name
    out_path.write_text(json.dumps(projected_payload, indent=2), encoding="utf-8")
    logger.info("Wrote %s", out_path)

    # typer.echo(f"Done. Processed {len(candidates)} candidate(s).")
    # typer.echo(f"  Canonical: {out_dir / 'canonical.json'}")
    # typer.echo(f"  Projected: {out_path}")
    typer.echo(f"\nPipeline completed successfully.")
    typer.echo(f"Candidates processed : {len(candidates)}")
    typer.echo(f"Canonical output     : {out_dir / 'canonical.json'}")
    typer.echo(f"Projected output     : {out_path}")
    # typer.echo("Merge reports        : output/<candidate_id>_merge_report.json")
    for c in candidates:
        typer.echo(
            f"Merge report        : output/{c.candidate_id}_merge_report.json"
        )


if __name__ == "__main__":
    app()
