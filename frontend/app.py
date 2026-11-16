"""IncidentOps — Streamlit Web Client (A8).

Thin async client that submits incident alerts to the FastAPI backend,
polls run status asynchronously, and renders advisory recommendations,
verified citations, and escalation paths.
"""

import os
import time
from typing import Any

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="IncidentOps Triage Assistant",
    page_icon="🛡️",
    layout="wide",
)

st.title("🛡️ IncidentOps — Production Incident Triage Assistant")
st.caption(
    "Advisory Multi-Agent SRE Assistant (F1-F8, A1-A8). Proposes cause classes and verified first-response steps. Never executes remediations."
)

tab_triage, tab_quarantine, tab_health = st.tabs(
    ["🚨 Incident Triage", "🛑 Quarantine Log", "🩺 System Health"]
)

with tab_triage:
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Submit Incident Alert")

        # Quick preset buttons
        sec41_pressed = st.button(
            "Load Section 4.1 Benchmark Scenario (Replication Slot WAL Accumulation)"
        )
        default_alert_name = (
            "PostgresWalAccumulationWarning" if sec41_pressed else "PostgresReplicationLagHigh"
        )
        default_note = (
            "Disk usage on primary is climbing steadily in /pg_wal. Table and index sizes are not growing. Standby replica standby_1 had network blip earlier."
            if sec41_pressed
            else "Disk usage on primary climbing rapidly, unused replication slot suspected."
        )
        default_metrics = (
            '{\n  "disk_utilization": 88.5,\n  "replication_lag_bytes": 104857600.0,\n  "active_connections": 42.0\n}'
            if sec41_pressed
            else '{\n  "replication_lag_bytes": 52428800.0,\n  "disk_utilization": 82.0\n}'
        )

        with st.form("alert_form"):
            alert_name = st.text_input("Alert Name", value=default_alert_name)
            source = st.text_input("Source", value="prometheus")
            pg_version = st.text_input("PostgreSQL Version", value="18.0")
            severity_hint = st.selectbox("Severity Hint", ["CRITICAL", "WARNING", "INFO"], index=0)
            metrics_str = st.text_area("Metrics (JSON)", value=default_metrics, height=120)
            on_call_note = st.text_area("On-Call Note", value=default_note, height=100)

            submitted = st.form_submit_button("Submit Alert for Multi-Agent Triage", type="primary")

    with col2:
        st.subheader("Diagnostic Advisory Output")

        if submitted:
            try:
                import json

                metrics_dict = json.loads(metrics_str)

                payload: dict[str, Any] = {
                    "alert_name": alert_name,
                    "source": source,
                    "fired_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "metrics": metrics_dict,
                    "pg_version": pg_version,
                    "severity_hint": severity_hint,
                    "on_call_note": on_call_note,
                    "tags": {"environment": "production"},
                }

                with st.spinner("Submitting to API boundary..."):
                    res = httpx.post(f"{API_URL}/runs", json=payload, timeout=10.0)

                if res.status_code == 202:
                    data = res.json()
                    run_id = data["run_id"]
                    st.success(f"Alert accepted! Run ID: `{run_id}` (Status: QUEUED)")

                    # Poll for run completion
                    status_placeholder = st.empty()
                    result_placeholder = st.empty()

                    max_polls = 40
                    poll_interval = 2.0
                    completed = False

                    for _ in range(max_polls):
                        status_res = httpx.get(f"{API_URL}/runs/{run_id}", timeout=10.0)
                        if status_res.status_code == 200:
                            run_info = status_res.json()
                            status = run_info.get("status")
                            status_placeholder.info(
                                f"Execution Status: **{status.upper()}** (Polling...)"
                            )

                            if status in ["completed", "escalated", "failed"]:
                                completed = True
                                status_placeholder.empty()

                                if status == "completed":
                                    st.success(f"Run Finished: **{status.upper()}**")
                                elif status == "escalated":
                                    st.warning(
                                        f"Run Finished: **{status.upper()}** (Escalated to Human)"
                                    )
                                else:
                                    st.error(f"Run Finished: **{status.upper()}**")

                                out = run_info.get("result")
                                if out:
                                    # Cause and Route Summary
                                    c1, c2, c3 = st.columns(3)
                                    c1.metric(
                                        "Cause Class", out.get("cause_class", "unknown").upper()
                                    )
                                    c2.metric(
                                        "Severity",
                                        f"{out.get('severity', 'UNKNOWN')} ({out.get('severity_basis', '')[:30]})",
                                    )
                                    c3.metric("Assigned Route", out.get("route", "unknown").upper())

                                    if out.get("escalation_reason"):
                                        st.error(
                                            f"**Escalation Reason:** {out.get('escalation_reason')}"
                                        )

                                    st.markdown("### 📋 First-Response Guidance")
                                    for step in out.get("first_response_steps", []):
                                        st.markdown(f"- {step}")

                                    st.markdown("### 🔍 Verified Grounded Citations")
                                    citations = out.get("citations", [])
                                    if citations:
                                        for idx, c in enumerate(citations, 1):
                                            st.markdown(
                                                f"**[{idx}] Section `{c.get('section_id')}`**"
                                            )
                                            st.info(f'"{c.get("quoted_span")}"')
                                    else:
                                        st.write("No citations attached (or run was escalated).")

                                    with st.expander("Audit Trace & Agent Steps"):
                                        for tr in out.get("trace", []):
                                            st.text(tr)

                                    with st.expander("Retrieved Documentation Passages"):
                                        for p in out.get("retrieved_passages", []):
                                            st.markdown(
                                                f"**Header:** `{p.get('header_path', 'N/A')}` | **Section:** `{p.get('section_id', 'N/A')}`"
                                            )
                                            st.caption(p.get("content", "")[:350] + "...")
                                break

                        time.sleep(poll_interval)

                    if not completed:
                        st.warning(
                            "Run is taking longer than expected. Continue polling via GET /runs/{run_id}."
                        )

                elif res.status_code == 422:
                    q_data = res.json()
                    st.error("❌ Request Rejected by Ingestion Boundary & Quarantined")
                    st.write(f"**Quarantine ID:** `{q_data.get('quarantine_id')}`")
                    for err in q_data.get("errors", []):
                        st.markdown(f"- **Field:** `{err.get('field')}`: {err.get('message')}")
                else:
                    st.error(f"API Error ({res.status_code}): {res.text}")

            except Exception as e:  # noqa: BLE001 - UI error boundary
                st.error(f"Failed to submit or poll: {e}")

with tab_quarantine:
    st.subheader("Rejected & Quarantined Payloads (F2, D1)")
    col_q1, col_q2 = st.columns([5, 1])
    with col_q2:
        st.button("🔄 Refresh")
    try:
        q_res = httpx.get(f"{API_URL}/quarantine?limit=20", timeout=5.0)
        if q_res.status_code == 200:
            q_list = q_res.json()
            total_count = q_list.get("total", 0)
            st.write(f"Total Quarantined Records: **{total_count}**")
            if total_count == 0:
                st.info("No quarantined records yet. Submit an invalid alert in the Triage tab to test quarantine.")
            for item in q_list.get("items", []):
                with st.expander(
                    f"🛑 {item.get('id')} — {item.get('reason')} ({item.get('quarantined_at')})"
                ):
                    st.write(f"**Client Info:** `{item.get('client_info')}`")
                    st.write(f"**Reason:** {item.get('reason')}")
                    st.write("**Field Errors:**", item.get("errors"))
                    st.write("**Raw Payload:**", item.get("raw_payload"))
        else:
            st.error(f"Error querying quarantine store: HTTP {q_res.status_code}")
    except Exception as q_exc:  # noqa: BLE001 - UI error boundary
        st.error(f"Error querying quarantine store: {q_exc}")

with tab_health:
    st.subheader("Service Health & Ingestion Metrics (D2, F8)")
    try:
        h_res = httpx.get(f"{API_URL}/health", timeout=5.0)
        if h_res.status_code == 200:
            st.json(h_res.json())
        m_res = httpx.get(f"{API_URL}/metrics", timeout=5.0)
        if m_res.status_code == 200:
            st.text(m_res.text)
    except Exception as h_exc:  # noqa: BLE001 - UI error boundary
        st.warning(f"Health check endpoint unreachable: {h_exc}")
