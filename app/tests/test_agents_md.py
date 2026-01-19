from pathlib import Path


def test_agents_md_documents_pipeline_and_registry() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    content = (repo_root / "AGENTS.md").read_text()
    assert "Search" in content
    assert "Verify" in content
    assert "Fetch" in content
    assert "Extract" in content
    assert "Sync" in content
    assert "AcquisitionIssue" in content or "uncapturable" in content
