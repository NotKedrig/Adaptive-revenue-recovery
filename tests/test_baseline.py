"""
tests/test_baseline.py — Tests for the Phase 6 baseline comparison.

Tests:
  1–2.  Endpoint returns 200 / case_count is exactly 40.
  3.    Result is deterministic across repeated calls.
  4.    Both naive and adaptive results are present.
  5.    Recovered revenue values are non-negative.
  6.    Recovery rates are valid.
  7.    Endpoint does NOT mutate the live demo state.
  8.    No external LLM/API dependency is required.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from app.db.state.models import Base


# ---------------------------------------------------------------------------
# Fixtures (matching the pattern used by test_api_queue.py)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'test_baseline.db'}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return url


@pytest.fixture(scope="function")
def seed_db(db_url, monkeypatch):
    import app.db.state.db as db_module

    original_get_engine = db_module.get_engine

    def patched_get_engine(database_url=None):
        return original_get_engine(db_url)

    monkeypatch.setattr(db_module, "get_engine", patched_get_engine)
    db_module._engine = None
    db_module._SessionLocal = None
    yield db_url
    db_module._engine = None
    db_module._SessionLocal = None


@pytest.fixture(scope="function")
def client(seed_db):
    from app.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Unit-level: evaluate directly without HTTP (most reliable)
# ---------------------------------------------------------------------------

def test_run_baseline_comparison_case_count():
    """2. case_count is exactly 40."""
    from app.evaluation.baseline import run_baseline_comparison, EVAL_N
    result = run_baseline_comparison()
    assert result.case_count == EVAL_N == 40


def test_run_baseline_comparison_is_deterministic():
    """3. Two calls produce identical results."""
    from app.evaluation.baseline import run_baseline_comparison
    r1 = run_baseline_comparison()
    r2 = run_baseline_comparison()
    assert r1.model_dump() == r2.model_dump()


def test_run_baseline_comparison_has_naive_and_adaptive():
    """4. Both naive and adaptive results are present."""
    from app.evaluation.baseline import run_baseline_comparison
    result = run_baseline_comparison()
    assert result.naive is not None
    assert result.adaptive is not None
    assert hasattr(result.naive, "recovered_revenue")
    assert hasattr(result.naive, "recovery_rate_percent")
    assert hasattr(result.adaptive, "recovered_revenue")
    assert hasattr(result.adaptive, "recovery_rate_percent")


def test_run_baseline_comparison_revenue_non_negative():
    """5. Recovered revenue values are non-negative."""
    from app.evaluation.baseline import run_baseline_comparison
    result = run_baseline_comparison()
    assert result.naive.recovered_revenue >= 0
    assert result.adaptive.recovered_revenue >= 0
    assert result.total_revenue_at_risk > 0


def test_run_baseline_comparison_rates_are_valid():
    """6. Recovery rates are valid percentages (0 to 100)."""
    from app.evaluation.baseline import run_baseline_comparison
    result = run_baseline_comparison()
    assert 0.0 <= result.naive.recovery_rate_percent <= 100.0
    assert 0.0 <= result.adaptive.recovery_rate_percent <= 100.0


def test_run_baseline_comparison_no_external_llm():
    """8. No external LLM/API dependency; explicitly declared in result."""
    from app.evaluation.baseline import run_baseline_comparison, EVAL_SEED
    result = run_baseline_comparison()
    assert result.external_llm_calls is False
    assert result.simulation_mode == "deterministic"
    assert result.evaluation_seed == EVAL_SEED


def test_run_baseline_improvement_math():
    """Verify improvement_percentage_points and additional_revenue are consistent."""
    from app.evaluation.baseline import run_baseline_comparison
    result = run_baseline_comparison()
    expected_pp = result.adaptive.recovery_rate_percent - result.naive.recovery_rate_percent
    assert abs(result.improvement_percentage_points - expected_pp) < 0.01
    expected_revenue = result.adaptive.recovered_revenue - result.naive.recovered_revenue
    assert abs(result.additional_revenue_recovered - expected_revenue) < 0.01


# ---------------------------------------------------------------------------
# HTTP endpoint tests (using FastAPI TestClient + patched DB)
# ---------------------------------------------------------------------------

def test_baseline_comparison_endpoint_returns_200(client):
    """1. Endpoint returns 200."""
    response = client.get("/api/baseline-comparison")
    assert response.status_code == 200, response.text


def test_baseline_comparison_endpoint_case_count(client):
    """2b. Endpoint response case_count is exactly 40."""
    data = client.get("/api/baseline-comparison").json()
    assert data["case_count"] == 40


def test_baseline_comparison_endpoint_is_deterministic(client):
    """3b. Two HTTP calls produce identical results."""
    r1 = client.get("/api/baseline-comparison").json()
    r2 = client.get("/api/baseline-comparison").json()
    assert r1 == r2


def test_baseline_comparison_endpoint_does_not_mutate_live_cases(client):
    """7. Endpoint does NOT mutate the live demo queue."""
    # Populate queue first so we have a baseline of live cases
    client.post("/api/demo/populate")
    queue_before = client.get("/api/queue").json()
    ids_before = {item["case_id"] for item in queue_before}

    # Call the baseline comparison endpoint
    client.get("/api/baseline-comparison")

    # Queue must be unchanged
    queue_after = client.get("/api/queue").json()
    ids_after = {item["case_id"] for item in queue_after}
    assert ids_before == ids_after, "Baseline comparison must not mutate the live queue"
