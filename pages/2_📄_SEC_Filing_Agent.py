"""SEC Filing Agent placeholder dashboard."""

from __future__ import annotations

import streamlit as st

from src.config import load_future_mcp_tools

st.set_page_config(page_title="SEC Filing Agent", page_icon="📄", layout="wide")

EXAMPLE_QUERIES = [
    "帮我查一下 NVDA 最近三次 10-Q 里 risk factors 有什么变化",
    "找出 watchlist 里最近 30 天有 8-K 的公司",
    "比较 MRVL 和 AVGO 的 revenue growth、FCF yield 和最近 filing 风险",
    "帮我基于 filings 和 valuation 生成一份本周 research brief",
]

PLANNED_CAPABILITIES = [
    "Recent SEC filing monitor",
    "10-K / 10-Q / 8-K filtering",
    "Risk factor diffing",
    "Company facts extraction",
    "Thesis impact analysis",
    "MCP-powered AI research assistant",
    "Weekly research brief generation",
]

ROADMAP = [
    "Add SEC EDGAR ingestion jobs",
    "Add raw SEC filings and company facts tables",
    "Add dbt SEC staging/intermediate/marts",
    "Add filing text extraction and section parsing",
    "Add risk factor diffing",
    "Build read-only MCP server",
    "Add AI agent chat UI to Streamlit",
    "Cache AI research outputs",
    "Generate weekly research brief",
]


st.title("SEC Filing Agent")
st.caption("Phase 2 planned: SEC EDGAR + MCP-powered AI research assistant")

st.warning(
    "This page is a placeholder in Phase 1. Full SEC ingestion, filing text extraction, "
    "risk factor diffing, and MCP AI-agent querying will be implemented in Phase 2."
)

st.subheader("Planned Capabilities")
cap_cols = st.columns(3)
for idx, capability in enumerate(PLANNED_CAPABILITIES):
    with cap_cols[idx % 3]:
        st.markdown(f"**{capability}**")
        st.write("Planned for Phase 2")

st.subheader("Example AI Queries")
for query in EXAMPLE_QUERIES:
    st.code(query, language="text")

st.subheader("AI Research Prompt")
prompt = st.chat_input("Phase 2 SEC research prompt")
st.button("Phase 2 coming soon", disabled=True)

if prompt:
    with st.chat_message("user"):
        st.write(prompt)
    with st.chat_message("assistant"):
        st.write("AI SEC research agent is planned for Phase 2. This input is not executed yet.")

mcp_config = load_future_mcp_tools()
with st.expander("Future MCP Tool Contract Preview", expanded=False):
    st.write(mcp_config.get("summary", "Planned read-only MCP tools."))
    for tool in mcp_config.get("tools", []):
        st.markdown(f"**{tool.get('name')}**")
        st.write(tool.get("description", ""))
        st.caption(f"Inputs: {', '.join(tool.get('inputs', []))}")
        st.caption(f"Output: {tool.get('output', '')}")
    guardrails = mcp_config.get("guardrails", [])
    if guardrails:
        st.markdown("**Guardrails**")
        for guardrail in guardrails:
            st.write(f"- {guardrail}")

st.subheader("Technical Roadmap")
for index, item in enumerate(ROADMAP, start=1):
    st.write(f"{index}. {item}")

