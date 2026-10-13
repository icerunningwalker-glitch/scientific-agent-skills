#!/usr/bin/env python3
"""Reproduce and audit a TH21-layout checkout without changing reference files."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def snapshot(repo, directories):
    result = {}
    for directory in directories:
        for path in sorted(directory.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                result[path.relative_to(repo).as_posix()] = digest(path)
    return result


def execute(command, cwd, log):
    started = time.perf_counter()
    with log.open('w', encoding='utf-8') as stream:
        process = subprocess.run(command, cwd=cwd, stdout=stream,
                                 stderr=subprocess.STDOUT, text=True)
    return {'command': command, 'exit_code': process.returncode,
            'elapsed_seconds': time.perf_counter() - started,
            'log': log.name}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--python', default=sys.executable,
                        help='Python interpreter containing the model dependencies')
    args = parser.parse_args()
    repo, output = args.repo.resolve(), args.output_dir.resolve()
    source = repo / 'src' / 'transport'
    protected = [source] + [repo / name / 'transport'
                             for name in ('data', 'models', 'logs', 'results')]
    required = [source / 'run_model.py', source / 'verify_results.py',
                repo / 'data' / 'transport' / 'reference_inputs.json',
                repo / 'results' / 'transport' / 'summary.json']
    for path in required:
        if not path.is_file():
            parser.error(f'Missing reference-model file: {path}')
    if any(output.is_relative_to(path) for path in protected):
        parser.error('Choose an output directory outside the protected transport module directories.')
    if output.exists() and any(output.iterdir()):
        parser.error('Output directory must be new or empty.')
    output.mkdir(parents=True, exist_ok=True)
    before = snapshot(repo, protected)
    report = {'status': 'started', 'repository': str(repo),
              'working_directory': str(output), 'reference_sha256': before,
              'helper_sha256': digest(Path(__file__).resolve()), 'runs': []}
    report_path = output / 'reproduction.json'
    try:
        environment_code = (
            'import json,sys,platform,importlib.metadata as m; '
            'print(json.dumps({"python":sys.version,"executable":sys.executable,'
            '"platform":platform.platform(),"packages":'
            '{n:m.version(n) for n in ("numpy","scipy","pandas","matplotlib")}}))'
        )
        process = subprocess.run([args.python, '-B', '-c', environment_code],
                                 cwd=output, capture_output=True, text=True)
        (output / 'environment_stdout.txt').write_text(process.stdout, encoding='utf-8')
        (output / 'environment_stderr.txt').write_text(process.stderr, encoding='utf-8')
        if process.returncode:
            raise RuntimeError('Dependency preflight failed; inspect environment_stderr.txt.')
        report['environment'] = json.loads(process.stdout.strip())
        generated = output / 'generated'
        run = execute([args.python, '-B', str(source / 'run_model.py'),
                       '--output-dir', str(generated)], output, output / 'run.log')
        report['runs'].append(run)
        if run['exit_code']:
            raise RuntimeError('Model run failed; inspect run.log.')
        verification = output / 'validation.json'
        run = execute([args.python, '-B', str(source / 'verify_results.py'),
                       '--generated-dir', str(generated), '--report', str(verification)],
                      output, output / 'verify.log')
        report['runs'].append(run)
        if run['exit_code']:
            raise RuntimeError('Numerical comparison failed; inspect verify.log.')
        report['verification'] = json.loads(verification.read_text(encoding='utf-8'))
        report['generated_sha256'] = {
            path.relative_to(output).as_posix(): digest(path)
            for path in sorted(generated.rglob('*')) if path.is_file()
        }
        report['status'] = 'passed'
    except Exception as error:
        report['status'], report['error'] = 'failed', str(error)
    finally:
        after = snapshot(repo, protected)
        changed = sorted(path for path in before.keys() | after.keys()
                         if before.get(path) != after.get(path))
        report['reference_file_count'] = len(before)
        report['reference_files_unchanged'] = not changed
        report['changed_reference_files'] = changed
        if changed:
            report['status'] = 'failed'
            report['error'] = 'Protected files changed during reproduction.'
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'report': str(report_path),
                      'reference_files_unchanged': report['reference_files_unchanged']}, indent=2))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
