"""Airflow DAG that rebuilds the RAG index and runs evaluation on a schedule.

This DAG shells out to the project CLI so the same code path used locally
also runs under Airflow. Adjust `PROJECT_ROOT` for your deployment.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

try:
    from airflow import DAG
    from airflow.operators.bash import BashOperator
except ImportError:  # pragma: no cover - Airflow optional at install time
    DAG = None  # type: ignore
    BashOperator = None  # type: ignore

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = "python"

default_args = {
    "owner": "platform-data",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

if DAG is not None:
    with DAG(
        dag_id="rag_document_pipeline",
        default_args=default_args,
        description="Rebuild RAG knowledge index and evaluate retrieval quality",
        schedule_interval="0 6 * * 1",
        start_date=datetime(2025, 1, 6),
        catchup=False,
        tags=["rag", "knowledge"],
    ) as dag:
        build_index = BashOperator(
            task_id="build_index",
            bash_command=f"cd {PROJECT_ROOT} && {PYTHON} -m src.pipeline run --stage index",
        )
        run_eval = BashOperator(
            task_id="run_eval",
            bash_command=f"cd {PROJECT_ROOT} && {PYTHON} -m src.pipeline run --stage eval",
        )
        build_index >> run_eval
