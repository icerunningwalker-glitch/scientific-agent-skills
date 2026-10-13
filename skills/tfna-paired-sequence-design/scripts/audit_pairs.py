#!/usr/bin/env python3
"""Independently audit real four-strand tFNA topology and mutation counts."""
import argparse
import csv
import hashlib
import itertools
import json
import os
from pathlib import Path
import re


def rc(sequence):
    return sequence.translate(str.maketrans("ACGT", "TGCA"))[::-1]


def load_reference(path):
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    strands = config["strands"]
    if set(strands) != {"1c", "2c", "3c", "4c"}:
        raise ValueError("Reference requires 1c, 2c, 3c, 4c.")
    if any(len(s) != 63 or set(s) - set("ACGT") for s in strands.values()):
        raise ValueError("Reference requires four 63-nt uppercase DNA strands.")
    linkers = config["junctions"]["linker_positions_1based"]
    if sorted(linkers) != [1, 22, 43]:
        raise ValueError("Reference requires junction positions 1, 22, 43.")
    coverage = {name: set() for name in strands}
    strand_pairs = set()
    edges = config["edges"]
    if len(edges) != 6:
        raise ValueError("Reference requires six edges.")
    for edge, spec in edges.items():
        a, b = spec["strand_a"], spec["strand_b"]
        pair = tuple(sorted((a, b)))
        if a not in strands or b not in strands or a == b or pair in strand_pairs:
            raise ValueError("Invalid or duplicate reference edge: " + edge)
        strand_pairs.add(pair)
        if spec["length"] != 20:
            raise ValueError("Reference edge must contain 20 bases: " + edge)
        for label in ("a", "b"):
            name, start = spec["strand_" + label], spec["start_" + label]
            if not isinstance(start, int) or not 1 <= start <= 44:
                raise ValueError("Invalid 1-based edge start: " + edge)
            sites = set(range(start, start + 20))
            if sites & coverage[name] or sites & set(linkers):
                raise ValueError("Overlapping reference edge or junction: " + edge)
            coverage[name].update(sites)
        first = strands[a][spec["start_a"] - 1:spec["start_a"] + 19]
        partner = strands[b][spec["start_b"] - 1:spec["start_b"] + 19]
        if partner != rc(first):
            raise ValueError("Reference is not complementary: " + edge)
    expected_pairs = {tuple(sorted(p)) for p in itertools.combinations(strands, 2)}
    expected_sites = set(range(1, 64)) - set(linkers)
    if strand_pairs != expected_pairs or any(sites != expected_sites for sites in coverage.values()):
        raise ValueError("Reference edges do not cover the tetrahedron exactly once.")
    return config


def load_fasta(path):
    strands = {}
    current = None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            tokens = line[1:].split()
            match = re.search(r"(?:^|_)([1-4]c)$", tokens[0], re.I) if tokens else None
            if match is None or match.group(1).lower() in strands:
                raise ValueError("Use four unique FASTA headers ending in 1c through 4c.")
            current = match.group(1).lower()
            strands[current] = ""
        elif current is None:
            raise ValueError("Sequence precedes a FASTA header.")
        else:
            strands[current] += line.upper()
    return strands


def audit(identifier, strands, config, declared_count=None):
    reference = config["strands"]
    errors = []
    if set(strands) != set(reference) or any(len(s) != 63 or set(s) - set("ACGT") for s in strands.values()):
        return {"candidate_id": identifier, "status": "FAIL", "errors": ["Require four 63-nt uppercase DNA strands."]}
    nucleotide_changes = sum(sum(a != b for a, b in zip(reference[name], strands[name])) for name in reference)
    for name, sequence in strands.items():
        if any(sequence[p - 1] != reference[name][p - 1] for p in config["junctions"]["linker_positions_1based"]):
            errors.append("junction_changed_" + name)
    mutations = []
    for edge, spec in config["edges"].items():
        first = strands[spec["strand_a"]][spec["start_a"] - 1:spec["start_a"] + 19]
        partner = strands[spec["strand_b"]][spec["start_b"] - 1:spec["start_b"] + 19]
        parent = reference[spec["strand_a"]][spec["start_a"] - 1:spec["start_a"] + 19]
        if partner != rc(first):
            errors.append("pairing_" + edge)
        mutations.extend(f"{edge}:{i}{a}>{b}" for i, (a, b) in enumerate(zip(parent, first), 1) if a != b)
    if nucleotide_changes != 2 * len(mutations):
        errors.append("paired_vs_nucleotide_count_mismatch")
    if declared_count is not None and int(declared_count) != len(mutations):
        errors.append("declared_paired_count_mismatch")
    key = "".join(strands[name] for name in sorted(reference))
    return {"candidate_id": identifier, "status": "FAIL" if errors else "PASS", "errors": errors,
            "paired_site_mutations": len(mutations), "actual_nucleotide_changes": nucleotide_changes,
            "mutations": mutations, "sequence_sha256": hashlib.sha256(key.encode("ascii")).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, help="Checkout root; defaults to TFNA_CK_REPO.")
    parser.add_argument("--reference", type=Path, help="Explicit real reference JSON instead of repository lookup.")
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--fasta", type=Path)
    inputs.add_argument("--table", type=Path)
    parser.add_argument("--expected-count", type=int, help="Optional expected number of constructs.")
    parser.add_argument("--output", type=Path, help="New JSON output path; existing files are preserved.")
    args = parser.parse_args()
    repo = args.repo or (Path(os.environ["TFNA_CK_REPO"]) if os.environ.get("TFNA_CK_REPO") else None)
    if args.reference is None and repo is None:
        parser.error("Supply --reference, --repo or TFNA_CK_REPO.")
    if args.expected_count is not None and args.expected_count < 1:
        parser.error("Expected count must be positive.")
    if args.output and args.output.exists():
        raise FileExistsError("Preserve existing output: " + str(args.output))
    reference_path = args.reference or repo / "data/ai_optimization/design/reference.json"
    config = load_reference(reference_path)
    if args.fasta:
        records = [audit(args.fasta.stem, load_fasta(args.fasta), config)]
    else:
        with args.table.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            raise ValueError("Empty candidate table.")
        ids = [row["candidate_id"] for row in rows]
        if any(not identifier for identifier in ids) or len(set(ids)) != len(ids):
            raise ValueError("Candidate IDs must be nonempty and unique.")
        records = [audit(row["candidate_id"], {name: row["strand_" + name] for name in config["strands"]},
                         config, row.get("paired_site_mutations")) for row in rows]
    failed = sum(record["status"] != "PASS" for record in records)
    count_matches = args.expected_count is None or args.expected_count == len(records)
    report = {"status": "PASS" if failed == 0 and count_matches else "FAIL", "constructs": len(records),
              "failed_constructs": failed, "expected_count_matches": count_matches,
              "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
              "scope": "Independent topology and mutation-count audit", "checks": records}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "checks"}, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
