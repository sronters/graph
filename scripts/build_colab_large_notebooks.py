"""Generate profile-specific, restart-safe Google Colab notebooks."""

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
            "colab": {"provenance": [], "gpuType": ""},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "cells": [
            markdown(
                f"# GraphTrust verified large run: {label}\n\n"
                "Run every cell from top to bottom in a **CPU high-RAM** Colab runtime. "
                "The notebook persists the generated graph and immutable run under Google Drive, "
                "so reconnecting and running again resumes instead of discarding verified work. "
                "The frozen source/target budgets in `configs/large.yaml` make this a bounded "
                "scalability run, not an exhaustive-recall experiment.\n"
            ),
            markdown("## 0. Settings and persistent workspace"),
            code(
                "import hashlib\n"
                "import json\n"
                "import os\n"
                "import platform\n"
                "import shutil\n"
                "import subprocess\n"
                "import sys\n"
                "from pathlib import Path\n\n"
                "from google.colab import drive, files\n\n"
                f"PROFILE = {profile!r}\n"
                "SEED = 2750159\n"
                "REPO = 'https://github.com/sronters/graph.git'\n"
                "BRANCH = 'main'  # PR #2 must be merged before this run.\n"
                "ROOT = Path('/content/graphtrust')\n"
                "drive.mount('/content/drive')\n"
                "PERSIST = Path('/content/drive/MyDrive/GraphTrustLarge') / PROFILE / str(SEED)\n"
                "DATA_ROOT = PERSIST / 'data'\n"
                "OUTPUT_ROOT = PERSIST / 'artifacts'\n"
                "PERSIST.mkdir(parents=True, exist_ok=True)\n"
                "print({'profile': PROFILE, 'seed': SEED, 'persistent_workspace': str(PERSIST)})\n"
            ),
            markdown("## 1. Clone the final source and install the locked environment"),
            code(
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
                "drive_free_gib = shutil.disk_usage(PERSIST).free / 2**30\n"
                "assert os.getenv('COLAB_RELEASE_TAG'), 'This must run inside Google Colab.'\n"
                "assert available_ram_gib >= 20, f'Choose a high-RAM runtime; only {available_ram_gib:.1f} GiB is available.'\n"
                "assert drive_free_gib >= 15, f'Free at least 15 GiB in Google Drive; only {drive_free_gib:.1f} GiB is available.'\n"
                "subprocess.run(['uv', 'run', 'graphtrust', 'generate', '--profile', PROFILE, '--scale', 'large', '--seed', str(SEED), '--variants', 'injected_mixed', '--dry-run'], check=True)\n"
                "subprocess.run(['uv', 'run', 'pytest', '-q', 'tests/integration/test_experiment_runner.py'], check=True)\n"
                "print({'available_ram_gib': round(available_ram_gib, 1), 'drive_free_gib': round(drive_free_gib, 1), 'smoke_test': 'passed'})\n"
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
                "assert receipt_data['is_google_colab']\n"
                "assert len(receipt_data['profiles']) == 1\n"
                "assert all(item['verified'] for item in receipt_data['profiles'])\n"
                "print(json.dumps(receipt_data, indent=2))\n"
            ),
            markdown("## 5. Build and download the verified evidence ZIP"),
            code(
                "export_root = PERSIST / 'evidence_package'\n"
                "if export_root.exists():\n"
                "    shutil.rmtree(export_root)\n"
                "export_root.mkdir(parents=True, exist_ok=True)\n"
                "shutil.copytree(OUTPUT_ROOT, export_root / 'artifacts', dirs_exist_ok=True)\n"
                "shutil.copy2(dataset / 'dataset_manifest.json', export_root / 'dataset_manifest.json')\n"
                "shutil.copy2(dataset / 'checksums.sha256', export_root / 'dataset_checksums.sha256')\n"
                "shutil.copy2(OUTPUT_ROOT / 'large_run_receipt.json', export_root / 'large_run_receipt.json')\n"
                "profile_receipt = receipt_data['profiles'][0]\n"
                "package_manifest = {'schema_version': '1.0', 'profile': PROFILE, 'seed': SEED, 'git_commit': COMMIT, 'dataset_id': profile_receipt['dataset_id'], 'dataset_checksum': profile_receipt['dataset_checksum'], 'run_id': profile_receipt['run_id'], 'execution_platform': 'google_colab', 'files': {}}\n"
                "for path in sorted(export_root.rglob('*')):\n"
                "    if path.is_file():\n"
                "        digest = hashlib.sha256()\n"
                "        with path.open('rb') as stream:\n"
                "            for chunk in iter(lambda: stream.read(1024 * 1024), b''):\n"
                "                digest.update(chunk)\n"
                "        package_manifest['files'][str(path.relative_to(export_root))] = digest.hexdigest()\n"
                "package_manifest_path = export_root / 'evidence_package_manifest.json'\n"
                "package_manifest_path.write_text(json.dumps(package_manifest, indent=2, sort_keys=True) + '\\n')\n"
                "archive_base = PERSIST / f'GraphTrust_large_{PROFILE}_{SEED}'\n"
                "archive = Path(shutil.make_archive(str(archive_base), 'zip', PERSIST, 'evidence_package'))\n"
                "archive_digest = hashlib.sha256()\n"
                "with archive.open('rb') as stream:\n"
                "    for chunk in iter(lambda: stream.read(1024 * 1024), b''):\n"
                "        archive_digest.update(chunk)\n"
                "archive_sha256 = archive_digest.hexdigest()\n"
                "package_manifest_digest = hashlib.sha256(package_manifest_path.read_bytes()).hexdigest()\n"
                "download_receipt = {'archive': archive.name, 'archive_sha256': archive_sha256, 'package_manifest_sha256': package_manifest_digest, 'git_commit': COMMIT, 'profile': PROFILE, 'seed': SEED, 'dataset_id': profile_receipt['dataset_id'], 'dataset_checksum': profile_receipt['dataset_checksum'], 'run_id': profile_receipt['run_id'], 'execution_platform': 'google_colab'}\n"
                "download_receipt_path = export_root / f'GraphTrust_large_{PROFILE}_{SEED}_download_receipt.json'\n"
                "download_receipt_path.write_text(json.dumps(download_receipt, indent=2, sort_keys=True) + '\\n')\n"
                "print(download_receipt)\n"
                "files.download(str(archive))\n"
                "files.download(str(download_receipt_path))\n"
            ),
            markdown(
                "## What to send back\n\n"
                "Send the downloaded `GraphTrust_large_<profile>_<seed>.zip` and "
                "`GraphTrust_large_<profile>_<seed>_download_receipt.json`. Do not report runtime or memory numbers unless "
                "the receipt says `is_google_colab: true` and every profile says `verified: true`."
            ),
        ],
    }


def main() -> None:
    output = Path("notebooks")
    output.mkdir(parents=True, exist_ok=True)
    for profile, label in PROFILES.items():
        destination = output / f"GraphTrust_Colab_Large_{profile}.ipynb"
        destination.write_text(
            json.dumps(notebook(profile, label), indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(destination)


if __name__ == "__main__":
    main()
