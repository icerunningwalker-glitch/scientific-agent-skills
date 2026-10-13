---
name: dna-sequence-model-benchmark
description: Run and audit nested cross-validation benchmarks for DNA sequences with aligned fixed features and count or continuous regression labels, including family-grouped tuning, OOF metrics, fitted-fold snapshots and optional offline TabPFN.
---

# DNA sequence model benchmark

Use the user's own DNA sequences, labels and fixed features to compare regressors under one recorded evaluation protocol. Read [the input and protocol reference](references/protocol.md) when preparing a dataset or choosing the generalization target. Read [the CK provenance reference](references/ck-example.md) only when reusing the packaged CK results or proxy definition.

## Prepare and run

1. Identify the target, its units, the family/group definition and the intended outer evaluation. Use `within-library` for shuffled five-fold development evaluation; use `group` when the intended test is transfer to unseen families. Choose before fitting.
2. Align `sequence_id` in the CSV and feature NPZ. Keep any learned normalization, feature selection, PCA and target scaling inside fold pipelines. Fixed external embeddings may be supplied with their encoder/version provenance. Resolve duplicate and reverse-complement samples before splitting, preserving raw replicate records and the aggregation rule.
3. Run the input check. The helper validates finite labels/features, unique sample IDs, canonical sequence duplicates, five outer folds, three family-grouped inner folds, and PCA feasibility. Count labels are nonnegative integers; continuous regression uses a separate target mode.
4. Fit into a new output directory only after the protocol check. The six numerical regressors and two baselines use the recorded CK parameter grids. Add `TabPFN` explicitly with a locally available compatible V2 regressor checkpoint. Record the actual model list and runtime versions.
5. Audit the saved run. Report each test fold and pooled OOF metrics. Each sample has one OOF prediction from a model fitted without that sample. A pooled OOF metric uses all such predictions once; an unweighted mean of fold metrics weights folds equally. Keep the average of four in-sample fold predictions labelled `train_diagnostic`.

Run relative to this skill directory, replacing inputs and output names:

```bash
python -B scripts/benchmark.py --data labels.csv --features features.npz --target-mode count --target-description "measured count under the stated assay" --check-inputs
python -B scripts/benchmark.py --data labels.csv --features features.npz --target-mode count --target-description "measured count under the stated assay" --fit --output new_run
python -B scripts/benchmark.py --audit-run new_run
```

For a bounded smoke check, use `--models Ridge`; the output records that subset. For continuous labels use `--target-mode regression`; classification metrics are then omitted. `--outer-split group` changes the evaluation to family transfer. Supply predeclared strata with `--strata-column` when continuous-label stratification is intended.

## Deliver the benchmark

Return input hashes and encoder provenance, protocol and assignments, selected parameters and inner losses, per-fold and pooled metrics, unique OOF predictions, training diagnostics, fitted snapshots, warnings and package versions. State which steps actually ran: arithmetic recomputation, saved-model inference, or fresh fitting. Compare metrics by their defined direction and units. Tune on inner folds; use outer test predictions for the reported evaluation.

Do not substitute training-fit values for held-out predictions. If fewer than the requested algorithms ran, name the actual subset and the concrete missing dependency or checkpoint. Repeated OOF inspection is part of development; a later confirmatory evaluation uses a new predefined test set.

The helper uses installed NumPy, scikit-learn, joblib and threadpoolctl. Optional TabPFN also uses installed torch/tabpfn. Keep the user's environment and existing outputs intact; report missing packages before a dependency change.
