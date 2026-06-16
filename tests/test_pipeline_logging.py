from src import db
from src.pipeline_logging import (
    finish_run,
    finish_task,
    log_error,
    record_freshness_check,
    start_run,
    start_task,
)


def test_pipeline_logging_helpers_write_ops_rows(tmp_path, monkeypatch):
    test_db_path = tmp_path / "ops_test.duckdb"
    monkeypatch.setattr(db, "DB_PATH", test_db_path)
    monkeypatch.setenv("CAPITALPILOT_DB_TARGET", "local")

    run_id = start_run("pytest_pipeline", target="local")
    task_id = start_task(run_id, "pytest_task", target="local")
    finish_task(task_id, status="success", target="local", row_count=3)
    log_error(run_id=run_id, task_name="pytest_task", error="sample warning", target="local")
    finish_run(run_id, status="success", target="local")
    freshness = record_freshness_check(domain="macro", table_name="raw.raw_macro_observations", target="local")

    conn = db.get_connection("local")
    try:
        runs = conn.execute("select count(*) from ops.pipeline_runs").fetchone()[0]
        tasks = conn.execute("select count(*) from ops.pipeline_task_runs").fetchone()[0]
        errors = conn.execute("select count(*) from ops.pipeline_errors").fetchone()[0]
    finally:
        conn.close()

    assert runs == 1
    assert tasks == 1
    assert errors == 1
    assert freshness["status"] == "empty"

