"""Generate three profile-specific, restart-safe Google Colab notebooks."""

# ruff: noqa: E501 - long strings are intentionally emitted as readable notebook cells.

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
                f"# GraphTrust large run: {label}\n\n"
                "This CPU/high-RAM run generates and analyzes one 227,000-node, "
                "2.5-million-edge SEIB-2026 enterprise graph. It writes an immutable "
                "run directory and a receipt that records whether execution occurred in Colab.\n"
            ),
            code(
                "import os\n"
                "import platform\n"
                "import shutil\n"
                "import subprocess\n"
                "import sys\n"
                "from pathlib import Path\n\n"
                f"PROFILE = {profile!r}\n"
                "SEED = 2750159\n"
                "REPO = 'https://github.com/sronters/graph.git'\n"
                "ROOT = Path('/content/graphtrust')\n"
                "print({\n"
                "    'profile': PROFILE,\n"
                "    'colab_release': os.getenv('COLAB_RELEASE_TAG'),\n"
                "    'python': sys.version,\n"
                "    'platform': platform.platform(),\n"
                "    'cpus': os.cpu_count(),\n"
                "})\n"
            ),
            markdown("## 1. Locked environment and provenance"),
            code(
                "if not (ROOT / 'pyproject.toml').exists():\n"
                "    subprocess.run(['git', 'clone', '--depth', '1', REPO, str(ROOT)], check=True)\n"
                "os.chdir(ROOT)\n"
                "subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'uv'], check=True)\n"
                "subprocess.run(['uv', 'sync', '--frozen', '--all-extras'], check=True)\n"
                "commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()\n"
                "print({'git_commit': commit})\n"
            ),
            markdown("## 2. Capacity gate and large deterministic generation"),
            code(
                "import psutil\n\n"
                "available_gib = psutil.virtual_memory().available / 2**30\n"
                "assert available_gib >= 10, (\n"
                "    'Use a Colab high-RAM runtime; only '\n"
                "    f'{available_gib:.1f} GiB available'\n"
                ")\n"
                "dataset = ROOT / 'data/generated' / PROFILE / 'large' / str(SEED) / 'injected_mixed'\n"
                "if not (dataset / 'checksums.sha256').exists():\n"
                "    subprocess.run(\n"
                "        [\n"
                "            'uv', 'run', 'graphtrust', 'generate',\n"
                "            '--profile', PROFILE, '--scale', 'large',\n"
                "            '--seed', str(SEED), '--variants', 'injected_mixed',\n"
                "        ],\n"
                "        check=True,\n"
                "    )\n"
                "print(dataset)\n"
            ),
            markdown("## 3. Immutable large GraphTrust run"),
            code(
                "subprocess.run(\n"
                "    [\n"
                "        'uv', 'run', 'python', 'scripts/run_large_profiles.py',\n"
                "        '--profile', PROFILE, '--seed', str(SEED),\n"
                "        '--config', 'configs/large.yaml',\n"
                "        '--output', 'artifacts/large_runs',\n"
                "    ],\n"
                "    check=True,\n"
                ")\n"
                "receipt = Path('artifacts/large_runs/large_run_receipt.json')\n"
                "print(receipt.read_text())\n"
            ),
            markdown("## 4. Verify checksums and export the complete evidence package"),
            code(
                "import json\n\n"
                "from google.colab import files\n\n"
                "receipt_data = json.loads(Path('artifacts/large_runs/large_run_receipt.json').read_text())\n"
                "assert receipt_data['is_google_colab'], (\n"
                "    'Receipt is not from a Google Colab runtime'\n"
                ")\n"
                "assert all(item['verified'] for item in receipt_data['profiles'])\n"
                "archive = shutil.make_archive(\n"
                "    f'/content/graphtrust-large-{PROFILE}-{SEED}',\n"
                "    'zip',\n"
                "    'artifacts/large_runs',\n"
                ")\n"
                "print({\n"
                "    'archive': archive,\n"
                "    'verified_profiles': len(receipt_data['profiles']),\n"
                "})\n"
                "files.download(archive)\n"
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
