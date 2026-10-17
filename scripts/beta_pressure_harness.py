"""Repeatable isolated beta campaign. Run with the repository's dev Python.

Never targets an existing database. Receipts survive failures and interruption.
Each subprocess has a bounded timeout and its own log. A nonzero scorecard case
is a failure even if the historical runner incorrectly exits zero.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    if not __debug__:
        raise RuntimeError('Pressure validation requires assertion-enabled Python.')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--live-models', action='store_true')
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--phase', choices=['baseline', 'extended', 'targeted', 'diagnostics', 'regression', 'models', 'reliability', 'resources', 'http-surface', 'coverage', 'surface', 'interop'], default='baseline')
    parser.add_argument('--artifact-run', type=Path)
    parser.add_argument('--soak-seconds', type=int, default=120)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    os.chmod(output, 0o700)
    (output / 'harness-source').mkdir()
    for script in (ROOT / 'scripts').glob('beta_*.py'):
        shutil.copy2(script, output / 'harness-source' / script.name)
    from aletheia.local_recipe import configure
    configuration = configure('http://127.0.0.1:11434', 'nomic-embed-text:latest', 'llama3.1:8b')
    os.environ['ALETHEIA_SEMANTIC_PROVIDER'] = 'ollama_style'
    os.environ['ALETHEIA_PROTECTED_KEY'] = 'synthetic-beta-pressure-key-not-for-production'
    os.environ['ALETHEIA_FEDERATION_KEY'] = 'synthetic-beta-pressure-federation-key-not-for-production'
    os.environ['ALETHEIA_FEDERATION_RECOVERY_KEY'] = 'synthetic-beta-pressure-recovery-key-not-for-production'
    # Every subcommand inherits deliberate model settings before any validation.
    report = {'started': datetime.now(timezone.utc).isoformat(), 'configuration': configuration,
              'phase': args.phase, 'live_models_requested': args.live_models,
              'steps': [], 'scope': 'Synthetic isolated beta validation; no release publication'}
    def save():
        temporary = output / 'receipt.tmp'
        temporary.write_text(json.dumps(report, indent=2, default=str) + '\n')
        temporary.replace(output / 'receipt.json')
    def step(name, command, *, cwd=ROOT, timeout=None):
        entry = {'name': name, 'command': command, 'cwd': str(cwd), 'status': 'running',
                 'started': datetime.now(timezone.utc).isoformat(), 'log': name + '.log'}
        entry['executed_scripts'] = {}
        for argument in command:
            path = Path(argument)
            path = path if path.is_absolute() else cwd / path
            if path.suffix == '.py' and path.is_file():
                entry['executed_scripts'][str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
                shutil.copy2(path, output / 'harness-source' / (name + '-' + path.name))
        report['steps'].append(entry)
        save()
        print('START', name, flush=True)
        started = time.monotonic()
        with (output / entry['log']).open('w') as stream:
            try:
                process = subprocess.Popen(command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                           start_new_session=True)
                returncode = process.wait(timeout=timeout or args.timeout)
                entry['returncode'] = returncode
                entry['status'] = 'passed' if returncode == 0 else 'failed'
            except subprocess.TimeoutExpired:
                entry['status'] = 'timeout'
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
            except OSError as error:
                entry.update(status='error', error=str(error))
        content = (output / entry['log']).read_text(errors='replace')
        if re.search(r'\[FAIL\]|^\s*FAIL\s', content, re.MULTILINE):
            entry['status'] = 'failed'
            entry['failed_case_marker'] = True
        entry['seconds'] = round(time.monotonic() - started, 3)
        entry['log_sha256'] = hashlib.sha256(content.encode()).hexdigest()
        save()
        print('END', name, entry['status'], entry['seconds'], flush=True)
        return entry
    report['commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    report['tree'] = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True).strip()
    report['working_tree'] = subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True)
    report['source_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for base in ['aletheia', 'scripts', 'tests']
                               for p in sorted((ROOT / base).rglob('*.py'))}
    from aletheia import Memory
    public = {name: str(inspect.signature(method)) for name, method in inspect.getmembers(Memory, callable)
              if not name.startswith('_')}
    (output / 'public-python-inventory.json').write_text(json.dumps(public, indent=2))
    save()
    lock_path = Path(f'/private/tmp/ultron-local-validation-{os.getuid()}.lock')
    # Keep the existing same-owner private inode, never unlink or recreate it.
    descriptor = os.open(lock_path, os.O_RDWR | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise RuntimeError('Shared lock is not a private same-owner regular file')
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            report['status'] = 'resource_deferred'
            save()
            return 75
        report['lock'] = {'path': str(lock_path), 'inode': info.st_ino, 'pid': os.getpid()}
        save()
        py = sys.executable
        if args.live_models:
            # Connection inspection is admission evidence, not an idle-model heuristic.
            clients = subprocess.run(['lsof', '-nP', '-iTCP:11434'], capture_output=True, text=True, timeout=45)
            (output / 'ollama-clients.log').write_text(clients.stdout + clients.stderr)
            if clients.returncode not in (0, 1) or 'ESTABLISHED' in clients.stdout:
                report['status'] = 'resource_deferred'
                save()
                return 75
            if args.phase in {'baseline', 'models'}:
                step('local-model-recipe', [py, '-m', 'aletheia.local_recipe', '--allow-local-models',
                                           '--report', str(output / 'local-models.json')], timeout=600)
            if args.phase != 'baseline':
                step('live-advisory-workflows', [py, 'scripts/beta_live_workflows.py',
                                                 '--output', str(output / 'live-workflows')], timeout=1200)
        if args.phase == 'models':
            if not args.live_models:
                raise ValueError('The models phase requires --live-models.')
        elif args.phase == 'baseline':
            step('pytest', [py, '-m', 'pytest', '--junitxml=' + str(output / 'pytest.xml')])
            scripts = ['live_mvp_scorecard.py', 'live_v0_1_polish_scorecard.py'] + [
                p.name for p in sorted((ROOT / 'scripts').glob('live_m[0-9]*_scorecard.py'))]
            for script in scripts:
                step(Path(script).stem, [py, str(ROOT / 'scripts' / script)])
            step('adversarial-pressure', [py, str(ROOT / 'scripts/beta_pressure_cases.py'),
                                          '--output', str(output / 'pressure')])
            step('release-gate', [py, 'scripts/release_gate.py', '--branch', 'main'])
        elif args.phase == 'surface':
            if not args.artifact_run:
                raise ValueError('Surface coverage requires --artifact-run pointing to baseline coverage.')
            baseline = args.artifact_run.resolve()
            prior = json.loads((baseline / 'receipt.json').read_text())
            for name, digest in prior['source_sha256'].items():
                if name.startswith('aletheia/') and hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
                    raise ValueError('Implementation changed since baseline coverage: ' + name)
            shutil.copyfile(baseline / '.coverage', output / '.coverage')
            report['coverage_baseline'] = str(baseline)
            save()
            step('coverage-surface', [py, '-m', 'coverage', 'run', '--append', '--branch', '--source=aletheia', '--data-file=' + str(output / '.coverage'), '-m', 'pytest', 'tests/test_beta_surface_workflows.py', 'tests/test_beta_sdk_surface.py', 'tests/test_beta_pressure_regressions.py', '--junitxml=' + str(output / 'surface.xml')])
            step('coverage-json', [py, '-m', 'coverage', 'json', '--data-file=' + str(output / '.coverage'), '-o', str(output / 'coverage.json')])
            step('public-body-coverage', [py, 'scripts/beta_coverage_inventory.py', '--coverage', str(output / 'coverage.json'), '--output', str(output / 'public-body-coverage.json')])
        elif args.phase == 'coverage':
            os.environ['ALETHEIA_BETA_HTTP_COVERAGE'] = str(output / 'http-route-coverage.json')
            step('coverage-pytest', [py, '-m', 'coverage', 'run', '--branch', '--source=aletheia', '--data-file=' + str(output / '.coverage'), '-m', 'pytest', '-p', 'scripts.beta_http_coverage', '--junitxml=' + str(output / 'pytest.xml')])
            step('coverage-json', [py, '-m', 'coverage', 'json', '--data-file=' + str(output / '.coverage'), '-o', str(output / 'coverage.json')])
            for script in ['live_mvp_scorecard.py', 'live_v0_1_polish_scorecard.py'] + [p.name for p in sorted((ROOT / 'scripts').glob('live_m[0-9]*_scorecard.py'))]:
                step(Path(script).stem, [py, str(ROOT / 'scripts' / script)])
            step('adversarial-pressure', [py, str(ROOT / 'scripts/beta_pressure_cases.py'), '--output', str(output / 'pressure')])
        elif args.phase == 'interop':
            if not args.artifact_run:
                raise ValueError('Interop requires --artifact-run pointing to a completed extended phase.')
            step('official-mcp-sdk', [py, 'scripts/beta_mcp_interoperability.py', '--server-python', str(args.artifact_run.resolve() / 'installed/bin/python'), '--output', str(output / 'mcp-sdk')])
        elif args.phase == 'http-surface':
            step('http-route-contracts', [py, 'scripts/beta_http_surface.py', '--output', str(output / 'http')], timeout=600)
        elif args.phase == 'resources':
            mode = '--disk-only' if sys.platform == 'darwin' else '--only-memory'
            step('bounded-resource-pressure', [py, 'scripts/beta_resource_pressure.py', '--output', str(output / 'resources'), mode], timeout=240)
        elif args.phase == 'reliability':
            step('reliability-pressure', [py, 'scripts/beta_reliability_pressure.py', '--output', str(output / 'reliability'), '--seconds', str(args.soak_seconds)], timeout=args.soak_seconds + 180)
        elif args.phase == 'regression':
            step('regression', [py, '-m', 'pytest', 'tests/test_beta_pressure_regressions.py',
                'tests/test_beta_surface_workflows.py', 'tests/test_beta_sdk_surface.py',
                'tests/test_v1_5_local_pairing.py::test_cli_registration_shutdown_and_crash_lease',
                'tests/test_m2_memory_integrity.py', 'tests/test_m12_governed_llm_memory.py',
                'tests/test_m6_memory_service.py', 'tests/test_certification_evidence.py',
                '--junitxml=' + str(output / 'regression.xml')])
        elif args.phase == 'extended':
            step('interface-pressure', [py, 'scripts/beta_interface_pressure.py', '--output', str(output / 'interfaces')])
            step('build', ['uv', 'build', '--out-dir', str(output / 'dist')])
            version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
            wheel = output / 'dist' / f'aletheia_memory-{version}-py3-none-any.whl'
            fresh = output / 'installed'
            previous = output / 'previous'
            step('fresh-venv', ['uv', 'venv', str(fresh)])
            step('fresh-install', ['uv', 'pip', 'install', '--python', str(fresh / 'bin/python'), str(wheel)])
            step('artifact-inspection', [py, 'scripts/beta_artifact_inspection.py', '--dist', str(output / 'dist'),
                                         '--python', str(fresh / 'bin/python'), '--output', str(output / 'artifacts.json')])
            step('installed-cli-surface', [py, 'scripts/beta_cli_surface.py', '--python', str(fresh / 'bin/python'), '--output', str(output / 'cli')])
            step('previous-venv', ['uv', 'venv', str(previous)])
            step('previous-install', ['uv', 'pip', 'install', '--python', str(previous / 'bin/python'), 'aletheia-memory==1.6.2'])
            step('installed-onboarding', [py, 'scripts/v1_4_onboarding_check.py', '--python', str(fresh / 'bin/python'), '--typescript'])
            step('installed-recovery', [py, 'scripts/v1_5_install_recovery_check.py', '--python', str(fresh / 'bin/python'),
                                        '--previous-python', str(previous / 'bin/python'), '--expected-version', version,
                                        '--previous-version', '1.6.2'])
            directory = ROOT / 'contracts/typescript'
            for script, target in [('v1_4_discovery_contract.py', 'discovery'), ('v1_4_read_contract.py', 'read'),
                                   ('v1_4_review_contract.py', 'review'), ('v1_4_agent_contract.py', 'onboarding')]:
                step('contract-' + target, [py, 'scripts/' + script, '--output', str(directory / 'generated' / (target + '.json'))])
                step('typescript-generate-' + target, ['npm', 'run', 'generate:' + target], cwd=directory)
            for command in ['check', 'build', 'test']:
                step('typescript-' + command, ['npm', 'run', command], cwd=directory)
            for script in ['v1_4_discovery_contract.py', 'v1_4_read_contract.py', 'v1_4_review_contract.py', 'v1_4_agent_contract.py']:
                step(Path(script).stem, [py, 'scripts/' + script, '--typescript'])
        elif args.phase == 'diagnostics':
            scripts = ['live_mvp_scorecard.py', 'live_v0_1_polish_scorecard.py'] + [
                p.name for p in sorted((ROOT / 'scripts').glob('live_m[0-9]*_scorecard.py'))]
            for script in scripts:
                step(Path(script).stem, [py, 'scripts/beta_scorecard_diagnose.py', '--script', 'scripts/' + script,
                                         '--output', str(output / (Path(script).stem + '-exceptions.json'))])
        else:
            for script in ['live_m10_federated_memory_scorecard.py', 'live_m11_production_semantic_retrieval_scorecard.py']:
                step(Path(script).stem, [py, 'scripts/' + script])
            step('adversarial-pressure', [py, 'scripts/beta_pressure_cases.py', '--output', str(output / 'pressure')])
            step('interface-pressure', [py, 'scripts/beta_interface_pressure.py', '--output', str(output / 'interfaces')])
            if args.artifact_run:
                artifacts = args.artifact_run.resolve()
                step('artifact-inspection', [py, 'scripts/beta_artifact_inspection.py', '--dist', str(artifacts / 'dist'),
                                             '--python', str(artifacts / 'installed/bin/python'),
                                             '--output', str(output / 'artifacts.json')])
        report['status'] = 'failed' if any(s['status'] != 'passed' for s in report['steps']) else 'passed'
        report['finished'] = datetime.now(timezone.utc).isoformat()
        save()
        return 0 if report['status'] == 'passed' else 1
    finally:
        os.close(descriptor)


if __name__ == '__main__':
    raise SystemExit(main())
