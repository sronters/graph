"""Hosted large-run receipt platform detection."""

from scripts.run_large_profiles import execution_platform


def test_kaggle_marker_has_priority(monkeypatch) -> None:
    monkeypatch.setenv("COLAB_RELEASE_TAG", "colab")
    monkeypatch.setenv("KAGGLE_KERNEL_RUN_TYPE", "Interactive")
    assert execution_platform() == "kaggle"


def test_colab_marker_is_detected(monkeypatch) -> None:
    monkeypatch.delenv("KAGGLE_KERNEL_RUN_TYPE", raising=False)
    monkeypatch.delenv("KAGGLE_URL_BASE", raising=False)
    monkeypatch.setenv("COLAB_RELEASE_TAG", "release")
    assert execution_platform() == "google_colab"


def test_unhosted_execution_is_local(monkeypatch) -> None:
    monkeypatch.delenv("KAGGLE_KERNEL_RUN_TYPE", raising=False)
    monkeypatch.delenv("KAGGLE_URL_BASE", raising=False)
    monkeypatch.delenv("COLAB_RELEASE_TAG", raising=False)
    assert execution_platform() == "local"
