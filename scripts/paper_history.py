#!/usr/bin/env python3
"""Check a paper against the project's permanent introduction history."""

import argparse
import csv
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

HISTORY = Path(__file__).resolve().parents[1] / "PAPER_HISTORY.csv"
REQUIRED = {"selected_date_jst", "doi", "title", "source_deck", "slide_id", "status"}
STATUSES = {"historical_slide", "reserved", "drafts_verified", "completed"}


def normalize_doi(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)", "", value)
    return value.rstrip(".,;: ")


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return "".join(char for char in value if char.isalnum())


def read_history() -> list[dict[str, str]]:
    with HISTORY.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or set(reader.fieldnames) != REQUIRED:
            raise ValueError(f"Unexpected columns in {HISTORY}")
        return list(reader)


def audit(rows: list[dict[str, str]]) -> int:
    errors = []
    known_dois = set()
    known_titles = set()
    new_dates = set()
    for number, row in enumerate(rows, start=2):
        if not row["title"].strip():
            errors.append(f"line {number}: missing title")
        if row["status"] not in STATUSES:
            errors.append(f"line {number}: unknown status {row['status']!r}")
        date = row["selected_date_jst"]
        if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            errors.append(f"line {number}: invalid date {date!r}")
        if row["status"] != "historical_slide" and not date:
            errors.append(f"line {number}: new selection needs a date")
        if row["status"] in {"historical_slide", "completed"} and not row["slide_id"].strip():
            errors.append(f"line {number}: missing slide ID")
        doi = normalize_doi(row["doi"])
        title = normalize_title(row["title"])
        if row["status"] != "historical_slide":
            if doi and doi in known_dois:
                errors.append(f"line {number}: new selection repeats an earlier DOI")
            if title and title in known_titles:
                errors.append(f"line {number}: new selection repeats an earlier title")
            if date and date in new_dates:
                errors.append(f"line {number}: more than one new selection on this date")
            if date:
                new_dates.add(date)
        if doi:
            known_dois.add(doi)
        if title:
            known_titles.add(title)
    for error in errors:
        print(error, file=sys.stderr)
    doi_counts = Counter(normalize_doi(row["doi"]) for row in rows if row["doi"].strip())
    repeated = sum(count - 1 for count in doi_counts.values() if count > 1)
    print(f"{len(rows)} history rows; {len(doi_counts)} unique DOIs; {repeated} earlier repeated-DOI events; {len(errors)} validation errors")
    return 2 if errors else 0


def check(rows: list[dict[str, str]], doi: str, title: str) -> int:
    if not doi and not title:
        raise ValueError("Provide --doi, --title, or both")
    candidate_doi = normalize_doi(doi) if doi else ""
    candidate_title = normalize_title(title) if title else ""
    matches = []
    for row in rows:
        doi_match = bool(candidate_doi and candidate_doi == normalize_doi(row["doi"]))
        title_match = bool(candidate_title and candidate_title == normalize_title(row["title"]))
        if doi_match or title_match:
            matches.append((row, "DOI" if doi_match else "title"))
    if not matches:
        print("NO EXACT MATCH in history; still compare author/year, versions, and all monthly slides manually")
        return 0
    print("ALREADY SELECTED — do not introduce again")
    for row, reason in matches:
        print(f"{reason}: {row['selected_date_jst'] or 'date unknown'} | {row['doi']} | {row['title']} | {row['source_deck']} | {row['slide_id']} | {row['status']}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("audit", help="Validate the history and report old repeated DOIs")
    check_parser = subparsers.add_parser("check", help="Check a candidate against the history")
    check_parser.add_argument("--doi", default="")
    check_parser.add_argument("--title", default="")
    args = parser.parse_args()
    try:
        rows = read_history()
        if args.command == "audit":
            return audit(rows)
        return check(rows, args.doi, args.title)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
