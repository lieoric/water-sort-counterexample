#!/usr/bin/env python3
"""Union exact frontier instance catalogs, checking fingerprint collisions."""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-catalogs", required=True, type=int)
    args = parser.parse_args()

    catalogs = sorted(args.input.rglob("instances.tsv"))
    if len(catalogs) != args.expected_catalogs:
        raise SystemExit(
            f"expected {args.expected_catalogs} catalogs, found {len(catalogs)}"
        )

    instances: dict[str, str] = {}
    rows = 0
    for catalog in catalogs:
        with catalog.open(encoding="utf-8") as source:
            header = next(source).rstrip("\n\r").split("\t")
            if header != ["fingerprint", "instance"]:
                raise SystemExit(f"unexpected catalog header in {catalog}")
            for line in source:
                fingerprint, encoding = line.rstrip("\n\r").split("\t", 1)
                rows += 1
                previous = instances.setdefault(fingerprint, encoding)
                if previous != encoding:
                    raise SystemExit(f"fingerprint collision for {fingerprint}")

    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "instances.tsv").open("w", encoding="utf-8") as target:
        target.write("fingerprint\tinstance\n")
        for fingerprint, encoding in sorted(instances.items()):
            target.write(f"{fingerprint}\t{encoding}\n")
    report = {
        "catalogs": len(catalogs),
        "input_rows": rows,
        "unique_instances": len(instances),
        "duplicates_removed": rows - len(instances),
    }
    (args.output / "report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
