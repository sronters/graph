"""Generate profile-specific Kaggle notebooks for the hosted large run."""

# ruff: noqa: E501 - notebook cells are kept readable in generated JSON.

from __future__ import annotations

import json
from pathlib import Path

PROFILES = {
    "saas_scaleup": "SaaS Scale-up",
    "regulated_finance": "Regulated Finance",
    "global_hybrid": "Global Hybrid",
}


def markdown(source: str) -> dict[str, object]:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict[str, object]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


def notebook(profile: str, label: str) -> dict[str, object]:
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "cells": [
            markdown(
                f"# GraphTrust verified large run: {label}\n\n"
                "Run every cell from top to bottom in a Kaggle CPU notebook with Internet enabled. "
                "Kaggle writes the reproducible working tree under `/kaggle/working` and the final "
                "receipt/archive under `/kaggle/outputs`; commit a notebook version after completion "
                "to preserve the output files. The frozen budgets in `configs/large.yaml` make this "
                "a bounded scalability run, not an exhaustive-recall experiment.\n"
            ),
            markdown("## 0. Settings and Kaggle workspace"),
            code(
                "import hashlib\n"
                "import json\n"
                "import os\n"
                "import platform\n"
                "import shutil\n"
                "import subprocess\n"
                "import sys\n"
                "from pathlib import Path\n\n"
                f"PROFILE = {profile!r}\n"
                "SEED = 2750159\n"
                "REPO = 'https://github.com/sronters/graph.git'\n"
                "BRANCH = 'main'\n"
                "ROOT = Path('/kaggle/working/graphtrust')\n"
                "PERSIST = Path('/kaggle/working/GraphTrustLarge') / PROFILE / str(SEED)\n"
                "DATA_ROOT = PERSIST / 'data'\n"
                "OUTPUT_ROOT = PERSIST / 'artifacts'\n"
                "KAGGLE_OUTPUT = Path('/kaggle/outputs') / PROFILE / str(SEED)\n"
                "PERSIST.mkdir(parents=True, exist_ok=True)\n"
                "KAGGLE_OUTPUT.mkdir(parents=True, exist_ok=True)\n"
                "print({'profile': PROFILE, 'seed': SEED, 'workspace': str(PERSIST), 'output': str(KAGGLE_OUTPUT)})\n"
            ),
            markdown("## 1. Clone the final source and install the locked environment"),
            code(
                "assert os.getenv('KAGGLE_KERNEL_RUN_TYPE'), 'Run this notebook in Kaggle, not locally.'\n"
                "if not (ROOT / '.git').exists():\n"
                "    subprocess.run(['git', 'clone', '--depth', '1', '--branch', BRANCH, REPO, str(ROOT)], check=True)\n"
                "os.chdir(ROOT)\n"
                "subprocess.run(['git', 'fetch', '--depth', '1', 'origin', BRANCH], check=True)\n"
                "subprocess.run(['git', 'checkout', '--detach', f'origin/{BRANCH}'], check=True)\n"
                "subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'uv'], check=True)\n"
                "subprocess.run(['uv', 'sync', '--frozen', '--all-extras'], check=True)\n"
                "COMMIT = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()\n"
                "print({'git_commit': COMMIT, 'python': sys.version, 'platform': platform.platform()})\n"
            ),
            markdown("## 2. Fail-fast capacity gate and smoke test"),
            code(
                "import psutil\n\n"
                "available_ram_gib = psutil.virtual_memory().available / 2**30\n"
                "disk_free_gib = shutil.disk_usage(PERSIST).free / 2**30\n"
                "assert available_ram_gib >= 20, f'Kaggle runtime has only {available_ram_gib:.1f} GiB RAM; use a high-memory CPU runtime.'\n"
                "assert disk_free_gib >= 15, f'Kaggle working disk has only {disk_free_gib:.1f} GiB free; free at least 15 GiB.'\n"
                "subprocess.run(['uv', 'run', 'graphtrust', 'generate', '--profile', PROFILE, '--scale', 'large', '--seed', str(SEED), '--variants', 'injected_mixed', '--dry-run'], check=True)\n"
                "subprocess.run(['uv', 'run', 'pytest', '-q', 'tests/integration/test_experiment_runner.py'], check=True)\n"
                "print({'available_ram_gib': round(available_ram_gib, 1), 'disk_free_gib': round(disk_free_gib, 1), 'smoke_test': 'passed'})\n"
            ),
            markdown("## 3. Generate or reuse the deterministic 2.5-million-edge graph"),
            code(
                "dataset = DATA_ROOT / PROFILE / 'large' / str(SEED) / 'injected_mixed'\n"
                "if not (dataset / 'checksums.sha256').exists():\n"
                "    subprocess.run(['uv', 'run', 'graphtrust', 'generate', '--profile', PROFILE, '--scale', 'large', '--seed', str(SEED), '--variants', 'injected_mixed', '--output-root', str(DATA_ROOT)], check=True)\n"
                "subprocess.run(['uv', 'run', 'graphtrust', 'validate-data', '--dataset', str(dataset)], check=True)\n"
                "print({'dataset': str(dataset), 'status': 'checksum-verified'})\n"
            ),
            markdown("## 4. Run or resume the immutable bounded analysis"),
            code(
                "subprocess.run(['uv', 'run', 'python', 'scripts/run_large_profiles.py', '--profile', PROFILE, '--seed', str(SEED), '--data-root', str(DATA_ROOT), '--config', 'configs/large.yaml', '--output', str(OUTPUT_ROOT)], check=True)\n"
                "receipt = OUTPUT_ROOT / 'large_run_receipt.json'\n"
                "receipt_data = json.loads(receipt.read_text())\n"
                "assert receipt_data['is_kaggle']\n"
                "assert receipt_data['execution_platform'] == 'kaggle'\n"
                "assert len(receipt_data['profiles']) == 1\n"
                "assert all(item['verified'] for item in receipt_data['profiles'])\n"
                "print(json.dumps(receipt_data, indent=2))\n"
            ),
            markdown("## 5. Build the verified Kaggle output archive"),
            code(
                "export_root = PERSIST / 'export'\n"
                "export_root.mkdir(parents=True, exist_ok=True)\n"
                "shutil.copy2(dataset / 'dataset_manifest.json', export_root / 'dataset_manifest.json')\n"
                "shutil.copy2(dataset / 'checksums.sha256', export_root / 'dataset_checksums.sha256')\n"
                "shutil.copy2(OUTPUT_ROOT / 'large_run_receipt.json', export_root / 'large_run_receipt.json')\n"
                "archive_base = PERSIST / f'GraphTrust_large_{PROFILE}_{SEED}'\n"
                "archive = Path(shutil.make_archive(str(archive_base), 'zip', PERSIST, 'artifacts'))\n"
                "archive_digest = hashlib.sha256()\n"
                "with archive.open('rb') as stream:\n"
                "    for chunk in iter(lambda: stream.read(1024 * 1024), b''):\n"
                "        archive_digest.update(chunk)\n"
                "archive_sha256 = archive_digest.hexdigest()\n"
                "output_archive = KAGGLE_OUTPUT / archive.name\n"
                "shutil.copy2(archive, output_archive)\n"
                "download_receipt = {'archive': output_archive.name, 'archive_sha256': archive_sha256, 'git_commit': COMMIT, 'profile': PROFILE, 'seed': SEED, 'execution_platform': 'kaggle'}\n"
                "download_receipt_path = KAGGLE_OUTPUT / f'GraphTrust_large_{PROFILE}_{SEED}_kaggle_receipt.json'\n"
                "download_receipt_path.write_text(json.dumps(download_receipt, indent=2, sort_keys=True) + '\\n')\n"
                "print(download_receipt)\n"
                "print({'output_archive': str(output_archive), 'receipt': str(download_receipt_path)})\n"
            ),
            markdown(
                "## What to submit back\n\n"
                "Create a Kaggle notebook version and download the ZIP plus the JSON receipt from the Output panel. "
                "Do not report runtime or memory numbers unless `large_run_receipt.json` says "
                "`is_kaggle: true`, `execution_platform: 'kaggle'`, and every profile record has `verified: true`.\n"
            ),
        ],
    }


def main() -> None:
    output = Path("notebooks")
    output.mkdir(parents=True, exist_ok=True)
    for profile, label in PROFILES.items():
        destination = output / f"GraphTrust_Kaggle_Large_{profile}.ipynb"
        destination.write_text(
            json.dumps(notebook(profile, label), indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(destination)


if __name__ == "__main__":
    main()
