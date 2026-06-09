# Future MCP Integration

CapitalPilot Phase 2 will add a read-only MCP server.

The MCP server will expose research tools to an AI agent.

The AI agent will be able to answer questions such as:

- 帮我查一下 NVDA 最近三次 10-Q 里 risk factors 有什么变化
- 找出 watchlist 里最近 30 天有 8-K 的公司
- 比较 MRVL 和 AVGO 的 revenue growth、FCF yield 和最近 filing 风险
- 帮我基于 filings 和 valuation 生成一份本周 research brief

## Planned Architecture

```text
Streamlit AI Chat UI
        |
AI Agent
        |
MCP Client
        |
CapitalPilot MCP Server
        |
Read-only tools
        |
MotherDuck marts
```

## Planned MCP Tools

- `search_sec_filings`
- `get_recent_10q_risk_factor_changes`
- `find_watchlist_8k_filings`
- `compare_companies_research_snapshot`
- `generate_weekly_research_brief`
- `get_macro_snapshot`
- `get_valuation_snapshot`

## Guardrails

- Read-only only
- No trading
- No portfolio execution
- No database writes from AI agent
- No deterministic buy/sell recommendations
- Must say insufficient data if data is missing
- Must distinguish source data from interpretation

## Phase 1 Status

No MCP server, MCP dependencies, autonomous tool calling, or live LLM execution is implemented in Phase 1.

