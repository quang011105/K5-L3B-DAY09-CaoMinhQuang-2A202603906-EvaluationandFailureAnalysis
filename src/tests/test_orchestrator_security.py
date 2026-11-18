from pathlib import Path

from lab8.shapes.orchestrator import run_claim


def test_orchestrator_trace_is_sanitized(public_db):
    result = run_claim(
        "C-001",
        seed=11,
        store_path=str(public_db),
    )

    trace = Path(result.trace_path).read_text(encoding="utf-8")

    assert result.status == "resolved"
    assert result.run_id in trace
    assert "CANARY_SECRET_" not in trace
    assert "parent_secret" not in trace
    assert "raw_headers" not in trace
