---
name: tfna-paired-sequence-design
description: Validate, edit, generate and rank four-strand DNA tetrahedron sequences with paired substitutions and a frozen local docking-count predictor. Use for 63-nt tFNA constructs and reproducible sequence screening.
---

# Paired tFNA Sequence Design

Produce traceable four-strand designs and clearly identified screening scores. Use real input sequences, the chosen topology reference and a pinned model. A request to replay saved candidates does not require generating a new pool or fitting a model.

## Locate the implementation

Prefer the user's checkout. Otherwise locate the repository at [tfna-ck-modeling](https://github.com/icerunningwalker-glitch/tfna-ck-modeling), confirm its availability and select a recorded commit or release. Set `TFNA_CK_REPO` or pass the checkout to the helper's `--repo` option. Confirm these files before running:

- `src/ai_optimization/design/common.py` and the requested CLI.
- `data/ai_optimization/design/reference.json` and real FASTA/CSV inputs.
- For prediction, `models/ai_optimization/design/historical_mlp_weights.npz`, its metadata and a matching local feature cache or encoder checkpoint.

The skill contains no training data, fitted model or checkpoint. Keep input/model assets in the checkout and use a new output directory. Run repository commands from its root, or pass absolute paths from another directory.

## Choose the requested operation

- **Validate or replay:** use the supplied FASTA or saved pool. Run the independent helper below and the repository's full sequence validator. Predict with `--cached-only` when encoding is outside the requested work.
- **Explicit edits:** use `mutation_design.py edit`. Edits such as `E12:11T>G` refer to the WT first-oriented edge at a 1-based position. The CLI replaces the partner's reverse complement automatically. Validate the result and report both paired-site and nucleotide change counts.
- **New candidates:** run `generate_candidates.py` only when generation is requested. Record the seed, per-pattern quota, maximum attempts and prior-pool hash file. Keep the new pool and rejection records separate from saved research outputs.
- **Score and select:** score validated sequences, then use `select_candidates.py` if the requested scheme is the historical burden/pattern selection. Describe the actual selection scheme and any distance fallback.

Read [references/model-and-design.md](references/model-and-design.md) for topology, sequence constraints, model provenance, input fields and selection mechanics.

## Encoding and score interpretation

`--cached-only` stops when a sequence is absent from the cache. `--fresh` ignores cached features and uses the pinned local encoder for every sequence. Without either flag, the repository uses the cache and computes missing features offline. Choose this behavior explicitly; check local dependencies before fresh encoding. Use `--checkpoint` and `--model-dir` to select compatible assets, and record their hashes/revisions.

The historical MLP predicts a continuous local docking-site count. Sum the six edge estimates as a dimensionless screening proxy and retain the six contributions. Keep training overlaps and model version in the output. A different ligand, count protocol, topology or fitted model requires a compatible model/cache and updated metadata.

## Commands

Independent topology/count audit, using only Python's standard library:

```text
python <skill>/scripts/audit_pairs.py --repo <checkout> --fasta <input.fasta> --output <new-run>/pair_audit.json
python <skill>/scripts/audit_pairs.py --repo <checkout> --table <candidate-table.csv> --output <new-run>/pool_audit.json
```

From the repository root:

```text
python src/ai_optimization/design/mutation_design.py validate --fasta <input.fasta>
python src/ai_optimization/design/predict.py --fasta <input.fasta> --cached-only --output <new-run>/score.json
python src/ai_optimization/design/smoke_check.py --output <new-run>/saved_84_replay.json
```

For explicitly requested new edits or generation:

```text
python src/ai_optimization/design/mutation_design.py edit --id candidate --edits "E12:11T>G" --output <new-run>/candidate.fasta
python src/ai_optimization/design/generate_candidates.py --seed 20261002 --per-pattern 250 --max-attempts 25000 --output-dir <new-run>/pool
python src/ai_optimization/design/score_candidates.py --input <pool.csv> --cached-only --output <new-run>/scored.csv
python src/ai_optimization/design/select_candidates.py --input <new-run>/scored.csv --output <new-run>/selected.csv
```

If an uncached new sequence needs scoring, select fresh/offline encoding according to the user's scope and available dependencies. Return input identity, parameters, model identity, topology/count checks, scores and actual run status. Mark behavior-check candidates as software checks when they were created for verification.
