# Inputs and evaluation protocol

## Input schema

`labels.csv` has `sequence_id,sequence,group,target`. IDs and groups are nonempty strings; sequences use uppercase A/C/G/T and have one fixed length. `features.npz` has finite numeric `X` (samples by features) and a one-dimensional string `sequence_id` array. The helper aligns feature rows by ID and rejects missing or duplicate IDs. Optional additional CSV columns may hold predeclared regression strata.

The default replicate policy rejects repeated canonical sequences, where canonical means the lexicographically smaller forward sequence or reverse complement. Before running, decide whether technical replicates should be aggregated or represented as one shared group. Preserve the replicate source and label aggregation record. Conflicting duplicate labels need an explicit scientific resolution; a new ID does not make the same sequence independent.

Specify the label source and units in `--target-description`. Count mode clips predictions at zero, uses the observed count >=1 for the binary outcome and predicted count >=0.5 for confusion matrices. Continuous regression keeps signed predictions and reports MAE, MSE and RMSE. Count-only integer metrics use floor(prediction+0.5). AUC ranks continuous count scores; single-class fold AUC is recorded as null.

## Splits and tuning

Default seed: 20261003. Count mode uses exact-count stratified shuffled five-fold outer CV. When some counts occur fewer than five times, allocation remains deterministic and the warning and fold composition are saved; rare counts cannot appear in every test fold. Regression mode uses shuffled KFold, or predeclared strata when supplied. Group outer CV uses GroupKFold(5) and saves the actual memberships. It requires enough distinct families in every outer training set for GroupKFold(3).

Inside each outer training set, three family-grouped folds select hyperparameters by minimum unweighted mean validation MAE. Unequal validation sizes do not turn this criterion into pooled sample-weighted MAE. All learned transformations use only the fit partition: variance filtering, feature standardization, PCA (default 8 components), and target standardization. One-hot Ridge omits PCA. The median baseline uses only outer training targets.

The helper records actual outer and inner memberships. Keep these files when reproducing a run: equivalent group labels or changed library versions may alter tie allocation when splits are generated again. Saved-model reproduction also needs compatible package versions and a trusted snapshot source.

The grids are the CK benchmark grids: MLP hidden widths 2/4/8 and alpha 1/10/100; SVR C 0.5/2/10 and epsilon 0.05/0.15; Ridge alpha 1/10/100/1000; forest and ExtraTrees depth 3/6/unlimited, minimum leaf 3/6 and max features 0.5/1; GPR alpha 0.01/0.1/1 with the recorded RBF+white kernel. Default models are the six numerical regressors, plus median and one-hot Ridge baselines. Adding TabPFN gives seven regressors and two baselines. TabPFN V2 uses four estimators on CPU with a supplied local checkpoint and no gradient fine-tuning.

## Outputs and reuse

`protocol.json` includes hashes, versions, model list, seeds, target mode, feature provenance, splits and grids. `outer_assignments.csv` and `inner_assignments.csv` describe membership; `oof_predictions.csv` has one held-out value per model/sample; `training_fit_predictions.csv` has four in-sample fits per model/sample; `train_diagnostic_predictions.csv` averages those four fits. `metrics.json` distinguishes pooled OOF, pooled training diagnostics, per-fold metrics and unweighted test-fold means. `selection.json`, `candidate_losses.csv` and `warnings.json` preserve tuning and warnings. Numerical snapshots in `models/` retain the full fitted pipeline and exact train/test IDs.

For new-sequence inference, use a full fitted pipeline with features from the same encoder and ordering contract. Fold snapshots support reproducing fold predictions; a full-data deployment model is a separate fit with its own provenance. TabPFN stores training context and selected parameters; restoring that context requires the same local checkpoint. The helper never labels saved CSV arithmetic as fresh model inference.

## Special conditions

- Frozen embeddings trained with the evaluation labels require a different leakage audit; a cache alone does not establish encoder independence.
- Variable-length sequences need a declared representation and baseline adaptation before using this fixed-length one-hot protocol.
- A new hyperparameter grid, outer grouping scheme or feature encoder is a new benchmark configuration. Record it rather than attaching the old score to a new model.
- This helper compares count or continuous regressors. Classification labels need a classifier protocol rather than relabelling regression scores as probabilities.
