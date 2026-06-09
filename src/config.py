"""Configuration helpers for CapitalPilot."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "capitalpilot.duckdb"
CONFIG_DIR = ROOT_DIR / "config"


def load_yaml_config(filename: str) -> dict[str, Any]:
    """Load a YAML file from the config directory."""
    path = CONFIG_DIR / filename
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected {path} to contain a YAML mapping.")
    return data


def load_watchlist() -> list[dict[str, Any]]:
    """Return configured watchlist entries."""
    data = load_yaml_config("watchlist.yaml")
    entries = data.get("watchlist", [])
    if not isinstance(entries, list):
        raise ValueError("config/watchlist.yaml must contain a watchlist list.")
    return entries


def load_macro_series() -> list[dict[str, Any]]:
    """Return configured macro series entries."""
    data = load_yaml_config("macro_series.yaml")
    entries = data.get("series", [])
    if not isinstance(entries, list):
        raise ValueError("config/macro_series.yaml must contain a series list.")
    return entries


def load_valuation_config() -> dict[str, Any]:
    """Return valuation configuration."""
    return load_yaml_config("valuation_config.yaml")


def load_future_mcp_tools() -> dict[str, Any]:
    """Return planned Phase 2 MCP tool contract configuration."""
    return load_yaml_config("future_mcp_tools.yaml")


def get_secret(name: str, default: str | None = None) -> str | None:
    """Read a secret from environment variables, then Streamlit secrets if available."""
    value = os.getenv(name)
    if value:
        return value

    try:
        import streamlit as st

        if name in st.secrets:
            secret_value = st.secrets[name]
            if secret_value:
                return str(secret_value)
    except Exception:
        pass

    return default

