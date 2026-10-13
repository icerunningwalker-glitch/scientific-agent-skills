"""Nested DNA-feature regression benchmark; fixed defaults, explicit fresh fitting."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import os
import platform
import warnings
from importlib.metadata import version

os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
os.environ.setdefault('TABPFN_DISABLE_TELEMETRY', '1')

import joblib
import numpy as np
from sklearn.base import clone
from sklearn.compose import TransformedTargetRegressor
from sklearn.decomposition import PCA
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.feature_selection import VarianceThreshold
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
from sklearn.linear_model import Ridge
from sklearn.metrics import confusion_matrix, mean_absolute_error, mean_squared_error, roc_auc_score
from sklearn.model_selection import GridSearchCV, GroupKFold, KFold, StratifiedKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from threadpoolctl import threadpool_limits

NAMES = ['MLP', 'SVR', 'Ridge', 'RandomForest', 'ExtraTrees', 'GPR', 'TabPFN']
PREFIX = 'regressor__model__'


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def canonical(sequence):
    reverse = sequence.translate(str.maketrans('ACGT', 'TGCA'))[::-1]
    return min(sequence, reverse)


def postprocess(values, mode):
    values = np.asarray(values, dtype=float)
    return np.maximum(values, 0) if mode == 'count' else values


def metrics(y, p, mode):
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    if len(y) == 0 or not (np.isfinite(y).all() and np.isfinite(p).all()):
        raise ValueError('Empty or nonfinite metric input.')
    mse = float(mean_squared_error(y, p))
    result = dict(n=len(y), MAE=float(mean_absolute_error(y, p)), MSE=mse, RMSE=float(np.sqrt(mse)))
    if mode == 'count':
        binary = y >= 1
        cm = confusion_matrix(binary, p >= .5, labels=[False, True])
        integer = np.floor(p + .5)
        result.update(AUC=float(roc_auc_score(binary, p)) if len(set(binary)) == 2 else None,
                      TN=int(cm[0, 0]), FP=int(cm[0, 1]), FN=int(cm[1, 0]), TP=int(cm[1, 1]),
                      integer_MAE=float(mean_absolute_error(y, integer)),
                      exact_count_fraction=float(np.mean(y == integer)))
    return result


def model_configs(seed):
    forest_grid = dict(max_depth=[3, 6, None], min_samples_leaf=[3, 6], max_features=[.5, 1.])
    return {
        'MLP': (MLPRegressor(solver='lbfgs', max_iter=2000, tol=1e-5, random_state=seed),
                dict(hidden_layer_sizes=[(2,), (4,), (8,)], alpha=[1, 10, 100])),
        'SVR': (SVR(kernel='rbf'), dict(C=[.5, 2, 10], epsilon=[.05, .15])),
        'Ridge': (Ridge(), dict(alpha=[1, 10, 100, 1000])),
        'RandomForest': (RandomForestRegressor(n_estimators=200, n_jobs=1, random_state=seed), forest_grid),
        'ExtraTrees': (ExtraTreesRegressor(n_estimators=200, n_jobs=1, random_state=seed), forest_grid),
        'GPR': (GaussianProcessRegressor(kernel=ConstantKernel(1., (1e-2, 1e2)) * RBF(10., (.1, 1e3))
                                        + WhiteKernel(.1, (.01, 1.)), n_restarts_optimizer=0, random_state=seed),
                dict(alpha=[.01, .1, 1.])),
        'TabPFN': (None, {}),
        'OneHotRidge': (Ridge(), dict(alpha=[1, 10, 100, 1000]))}


def prepare(args):
    rows = read_csv(args.data)
    required = {'sequence_id', 'sequence', 'group', 'target'}
    if not rows or not required.issubset(rows[0]):
        raise ValueError('CSV requires sequence_id,sequence,group,target.')
    ids = [r['sequence_id'] for r in rows]
    sequences = [r['sequence'] for r in rows]
    if any(not r['sequence_id'] or not r['group'] for r in rows) or len(set(ids)) != len(ids):
        raise ValueError('IDs must be unique and IDs/groups nonempty.')
    if len(set(map(len, sequences))) != 1 or any(not s or set(s) - set('ACGT') for s in sequences):
        raise ValueError('Use fixed-length uppercase A/C/G/T sequences.')
    if len(set(map(canonical, sequences))) != len(rows):
        raise ValueError('Duplicate or reverse-complement sequences: resolve replicates before splitting.')
    y = np.array([float(r['target']) for r in rows])
    if not np.isfinite(y).all():
        raise ValueError('Labels must be finite.')
    if args.target_mode == 'count' and (np.any(y < 0) or np.any(y != np.floor(y))):
        raise ValueError('Count labels must be nonnegative integers.')
    with np.load(args.features, allow_pickle=False) as cache:
        raw = np.asarray(cache['X'], dtype=float)
        feature_ids = list(map(str, cache['sequence_id']))
    if raw.ndim != 2 or len(raw) != len(feature_ids) or len(feature_ids) != len(set(feature_ids)) or set(feature_ids) != set(ids):
        raise ValueError('Feature rows require unique IDs matching exactly the label IDs.')
    lookup = {identity: i for i, identity in enumerate(feature_ids)}
    X = raw[[lookup[identity] for identity in ids]]
    if not np.isfinite(X).all():
        raise ValueError('Features must be finite.')
    H = np.array([[float(base == letter) for base in canonical(s) for letter in 'ACGT'] for s in sequences])
    groups = np.array([r['group'] for r in rows])
    split_warnings = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        if args.outer_split == 'group':
            outer = list(GroupKFold(5).split(X, y, groups))
        elif args.target_mode == 'count' or args.strata_column:
            strata = y if args.target_mode == 'count' else np.array([r[args.strata_column] for r in rows])
            outer = list(StratifiedKFold(5, shuffle=True, random_state=args.seed).split(X, strata))
        else:
            outer = list(KFold(5, shuffle=True, random_state=args.seed).split(X))
    split_warnings.extend(dict(stage='outer_split', category=w.category.__name__, message=str(w.message)) for w in caught)
    inner, memberships, outer_ids = {}, [], np.zeros(len(y), dtype=int)
    for fold, (train, test) in enumerate(outer, 1):
        outer_ids[test] = fold
        inner[fold] = list(GroupKFold(3).split(X[train], y[train], groups[train]))
        for number, (fit, val) in enumerate(inner[fold], 1):
            if set(groups[train[fit]]) & set(groups[train[val]]):
                raise ValueError('Family leakage in inner folds.')
            if len(fit) < args.pca_components or np.count_nonzero(np.var(X[train[fit]], axis=0) > 0) < args.pca_components:
                raise ValueError('An inner fit partition has fewer samples or variable features than PCA components.')
            memberships.extend(dict(sequence_id=ids[train[i]], outer_fold=fold, inner_fold=number, group=groups[train[i]]) for i in val)
        if args.outer_split == 'group' and set(groups[train]) & set(groups[test]):
            raise ValueError('Family leakage in group outer folds.')
    return rows, ids, X, H, y, outer, inner, outer_ids, memberships, split_warnings


def run(args):
    prepared = prepare(args)
    rows, ids, X, H, y, outer, inner, outer_ids, memberships, warning_log = prepared
    if args.check_inputs:
        print(json.dumps(dict(status='inputs_validated', samples=len(y), features=X.shape[1],
                              outer_folds=5, inner_folds=3, models=args.models, no_training=True)))
        return
    if not args.fit or not args.output:
        raise ValueError('Choose --check-inputs or --fit --output NEW_DIRECTORY.')
    if args.output.exists():
        raise ValueError('Output already exists; choose a new directory.')
    if 'TabPFN' in args.models:
        if not args.tabpfn_checkpoint or not args.tabpfn_checkpoint.is_file():
            raise ValueError('TabPFN requires a local licensed V2 regressor checkpoint.')
        import torch
        from tabpfn import TabPFNRegressor
        from tabpfn.constants import ModelVersion
        torch.set_num_threads(2)
        torch.manual_seed(args.seed)
    configs = model_configs(args.seed)
    all_models = args.models + ['TrainingMedian', 'OneHotRidge']
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in [('labels', args.data), ('features', args.features)]}
    if args.tabpfn_checkpoint:
        hashes['TabPFN_checkpoint'] = hashlib.sha256(args.tabpfn_checkpoint.read_bytes()).hexdigest()
    protocol = dict(seed=args.seed, target_mode=args.target_mode, target_description=args.target_description,
                    feature_provenance=args.feature_provenance, outer_split=args.outer_split,
                    strata_column=args.strata_column, models=all_models, n=len(y), feature_dimensions=X.shape[1],
                    pca_components=args.pca_components, inner_folds=3, tuning='unweighted mean inner validation MAE',
                    hashes=hashes, grids={name: configs[name][1] for name in all_models if name != 'TrainingMedian'},
                    runtime=dict(python=platform.python_version(), dependencies={name: version(name) for name in
                                 ['numpy', 'scipy', 'scikit-learn', 'joblib', 'threadpoolctl']}),
                    execution='fresh fitting on supplied labels and features')
    args.output.mkdir(parents=True, exist_ok=False)
    model_dir = args.output / 'models'
    model_dir.mkdir()
    write_json(args.output / 'protocol.json', protocol)
    write_csv(args.output / 'outer_assignments.csv', [dict(sequence_id=ids[i], sequence=r['sequence'], group=r['group'], target=float(y[i]), outer_fold=int(outer_ids[i])) for i, r in enumerate(rows)])
    write_csv(args.output / 'inner_assignments.csv', memberships)
    oof, training, diagnostics, selection, losses, metric_rows = [], [], [], [], [], []
    with threadpool_limits(limits=1):
        for name in all_models:
            features = H if name == 'OneHotRidge' else X
            heldout = np.full(len(y), np.nan)
            train_sum, train_n = np.zeros(len(y)), np.zeros(len(y), dtype=int)
            for fold, (train, test) in enumerate(outer, 1):
                if name == 'TrainingMedian':
                    predicted = np.full(len(y), np.median(y[train]))
                    selection.append(dict(model=name, outer_fold=fold, training_median=float(np.median(y[train]))))
                else:
                    estimator, grid = configs[name]
                    if name == 'TabPFN':
                        estimator = TabPFNRegressor.create_default_for_version(ModelVersion.V2,
                            model_path=str(args.tabpfn_checkpoint.resolve()), device='cpu', n_estimators=4,
                            n_preprocessing_jobs=1, random_state=args.seed)
                    stages = [('variance', VarianceThreshold()), ('scale', StandardScaler())]
                    if name != 'OneHotRidge':
                        stages.append(('pca', PCA(n_components=args.pca_components, svd_solver='full')))
                    target = TransformedTargetRegressor(regressor=Pipeline(stages + [('model', clone(estimator))]), transformer=StandardScaler())
                    def score(model, features, actual):
                        return -mean_absolute_error(actual, postprocess(model.predict(features), args.target_mode))
                    search = GridSearchCV(target, {PREFIX + key: value for key, value in grid.items()}, scoring=score,
                                          cv=inner[fold], n_jobs=1, error_score='raise')
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter('always')
                        search.fit(features[train], y[train])
                        predicted = postprocess(search.predict(features), args.target_mode)
                    warning_log.extend(dict(model=name, outer_fold=fold, category=w.category.__name__, message=str(w.message)) for w in caught)
                    selection.append(dict(model=name, outer_fold=fold, parameters=search.best_params_, mean_inner_MAE=-float(search.best_score_)))
                    for i, params in enumerate(search.cv_results_['params']):
                        losses.append(dict(model=name, outer_fold=fold, candidate=i, parameters=json.dumps(params),
                                           mean_inner_MAE=-float(search.cv_results_['mean_test_score'][i]),
                                           fold_MAE_1=-float(search.cv_results_['split0_test_score'][i]),
                                           fold_MAE_2=-float(search.cv_results_['split1_test_score'][i]),
                                           fold_MAE_3=-float(search.cv_results_['split2_test_score'][i]), selected=i == search.best_index_))
                    if name == 'TabPFN':
                        np.savez_compressed(model_dir / f'{name}_context_fold{fold}.npz', X=X[train], y=y[train], sequence_id=np.array([ids[i] for i in train]))
                    else:
                        joblib.dump(dict(estimator=search.best_estimator_, model=name, outer_fold=fold,
                                         train_sequence_ids=[ids[i] for i in train], test_sequence_ids=[ids[i] for i in test]),
                                    model_dir / f'{name}_fold{fold}.joblib')
                heldout[test] = predicted[test]
                train_sum[train] += predicted[train]
                train_n[train] += 1
                oof.extend(dict(model=name, outer_fold=fold, sequence_id=ids[i], target=float(y[i]), prediction=float(predicted[i])) for i in test)
                training.extend(dict(model=name, outer_fold=fold, sequence_id=ids[i], target=float(y[i]), prediction=float(predicted[i])) for i in train)
                for split, indices in [('test_fold', test), ('train_fold', train)]:
                    metric_rows.append(dict(model=name, split=split, outer_fold=fold, **metrics(y[indices], predicted[indices], args.target_mode)))
            if not np.isfinite(heldout).all() or not np.all(train_n == 4):
                raise ValueError('Incomplete OOF coverage or in-sample fit count.')
            train_mean = train_sum / train_n
            metric_rows.extend([dict(model=name, split='OOF', **metrics(y, heldout, args.target_mode)),
                                dict(model=name, split='train_diagnostic', **metrics(y, train_mean, args.target_mode))])
            diagnostics.extend(dict(model=name, sequence_id=ids[i], target=float(y[i]), prediction=float(train_mean[i])) for i in range(len(y)))
            fold_values = [r for r in metric_rows if r['model'] == name and r['split'] == 'test_fold']
            averaged = {key: float(np.mean([r[key] for r in fold_values])) if all(r[key] is not None for r in fold_values) else None for key in metrics(y, heldout, args.target_mode) if key != 'n'}
            metric_rows.append(dict(model=name, split='unweighted_test_fold_mean', **averaged))
    write_csv(args.output / 'oof_predictions.csv', oof)
    write_csv(args.output / 'training_fit_predictions.csv', training)
    write_csv(args.output / 'train_diagnostic_predictions.csv', diagnostics)
    write_csv(args.output / 'candidate_losses.csv', losses)
    write_json(args.output / 'metrics.json', metric_rows)
    write_json(args.output / 'selection.json', selection)
    write_json(args.output / 'warnings.json', warning_log)
    print(json.dumps(dict(status='fresh_fit_complete', models=all_models, samples=len(y), OOF_records=len(oof))))


def audit(path):
    protocol = json.loads((path / 'protocol.json').read_text())
    assignments = read_csv(path / 'outer_assignments.csv')
    mapping = {r['sequence_id']: r for r in assignments}
    if len(mapping) != protocol['n'] or len(assignments) != len(mapping):
        raise ValueError('Duplicate or missing source assignment.')
    models, n = protocol['models'], protocol['n']
    expected_keys = {(model, identity) for model in models for identity in mapping}
    oof = read_csv(path / 'oof_predictions.csv')
    train = read_csv(path / 'training_fit_predictions.csv')
    diagnostic = read_csv(path / 'train_diagnostic_predictions.csv')
    if len(oof) != len(expected_keys) or {(r['model'], r['sequence_id']) for r in oof} != expected_keys:
        raise ValueError('OOF must have exactly one record per model/sample.')
    if len(diagnostic) != len(expected_keys) or {(r['model'], r['sequence_id']) for r in diagnostic} != expected_keys:
        raise ValueError('Training diagnostics must cover every model/sample once.')
    expected_train = {(m, s, str(f)) for m, s in expected_keys for f in range(1, 6) if str(f) != mapping[s]['outer_fold']}
    if len(train) != len(expected_train) or {(r['model'], r['sequence_id'], r['outer_fold']) for r in train} != expected_train:
        raise ValueError('Training-fit rows do not match the four eligible outer fits.')
    for row in oof + train + diagnostic:
        if float(row['target']) != float(mapping[row['sequence_id']]['target']) or not np.isfinite(float(row['prediction'])):
            raise ValueError('Prediction labels or finiteness disagree with input.')
        if protocol['target_mode'] == 'count' and float(row['prediction']) < 0:
            raise ValueError('Count scores must be nonnegative.')
    if any(r['outer_fold'] != mapping[r['sequence_id']]['outer_fold'] for r in oof):
        raise ValueError('OOF fold does not match the held-out assignment.')
    inner = read_csv(path / 'inner_assignments.csv')
    if len(inner) != 4 * n or len({(r['outer_fold'], r['sequence_id']) for r in inner}) != 4 * n:
        raise ValueError('Inner assignments must cover each eligible outer training sample once.')
    if any(int(r['outer_fold']) not in range(1, 6) or int(r['inner_fold']) not in range(1, 4)
           or r['sequence_id'] not in mapping or r['group'] != mapping[r['sequence_id']]['group'] for r in inner):
        raise ValueError('Invalid inner-fold metadata.')
    for fold in range(1, 6):
        eligible = {s for s, r in mapping.items() if int(r['outer_fold']) != fold}
        subset = [r for r in inner if int(r['outer_fold']) == fold]
        if {r['sequence_id'] for r in subset} != eligible:
            raise ValueError('Inner assignment contains outer test samples.')
        for k in range(1, 4):
            validation = {r['sequence_id'] for r in subset if int(r['inner_fold']) == k}
            if not validation or not eligible - validation or {mapping[s]['group'] for s in validation} & {mapping[s]['group'] for s in eligible - validation}:
                raise ValueError('Invalid inner partition or family overlap.')
        if protocol['outer_split'] == 'group' and {mapping[s]['group'] for s in eligible} & {r['group'] for r in assignments if int(r['outer_fold']) == fold}:
            raise ValueError('Outer family overlap in group evaluation.')
    for row in diagnostic:
        fits = [float(r['prediction']) for r in train if r['model'] == row['model'] and r['sequence_id'] == row['sequence_id']]
        if not np.isclose(float(row['prediction']), np.mean(fits), rtol=1e-10, atol=1e-12):
            raise ValueError('Training diagnostic is not the mean of four fits.')
    metric_rows = json.loads((path / 'metrics.json').read_text())
    expected_metric = {(m, split, 0) for m in models for split in ('OOF', 'train_diagnostic', 'unweighted_test_fold_mean')} | {(m, split, f) for m in models for split in ('test_fold', 'train_fold') for f in range(1, 6)}
    if len(metric_rows) != len(expected_metric) or {(r['model'], r['split'], r.get('outer_fold', 0)) for r in metric_rows} != expected_metric:
        raise ValueError('Missing or duplicated metric rows.')
    for record in metric_rows:
        if record['split'] == 'unweighted_test_fold_mean':
            folds = [r for r in metric_rows if r['model'] == record['model'] and r['split'] == 'test_fold']
            expected = {key: float(np.mean([r[key] for r in folds])) if all(r[key] is not None for r in folds) else None for key in record if key not in ('model', 'split')}
        else:
            pool = diagnostic if record['split'] == 'train_diagnostic' else train if record['split'] == 'train_fold' else oof
            selected = [r for r in pool if r['model'] == record['model'] and ('outer_fold' not in record or int(r['outer_fold']) == record['outer_fold'])]
            expected = metrics([float(r['target']) for r in selected], [float(r['prediction']) for r in selected], protocol['target_mode'])
        for key, value in expected.items():
            if (value is None and record[key] is not None) or (value is not None and not np.isclose(record[key], value, rtol=1e-10, atol=1e-12)):
                raise ValueError('Saved metric arithmetic disagrees with predictions.')
    print(json.dumps(dict(status='audit_passed', models=models, samples=n, OOF_records=len(oof), no_training=True)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path)
    parser.add_argument('--features', type=Path)
    parser.add_argument('--target-mode', choices=['count', 'regression'], default='count')
    parser.add_argument('--target-description')
    parser.add_argument('--feature-provenance', default='user-supplied fixed features; encoder provenance not supplied')
    parser.add_argument('--outer-split', choices=['within-library', 'group'], default='within-library')
    parser.add_argument('--strata-column')
    parser.add_argument('--seed', type=int, default=20261003)
    parser.add_argument('--pca-components', type=int, default=8)
    parser.add_argument('--models', nargs='+', choices=NAMES, default=NAMES[:-1])
    parser.add_argument('--tabpfn-checkpoint', type=Path)
    parser.add_argument('--check-inputs', action='store_true')
    parser.add_argument('--fit', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--audit-run', type=Path)
    args = parser.parse_args()
    try:
        if args.audit_run:
            if args.fit or args.check_inputs:
                raise ValueError('Audit and fitting/checking are separate actions.')
            audit(args.audit_run)
        else:
            if not args.data or not args.features or not args.target_description or args.pca_components < 1:
                raise ValueError('Supply --data, --features, --target-description and positive PCA components.')
            if len(args.models) != len(set(args.models)) or (args.fit and args.check_inputs):
                raise ValueError('Use unique model names and one execution mode.')
            run(args)
    except (ValueError, KeyError, FileNotFoundError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
