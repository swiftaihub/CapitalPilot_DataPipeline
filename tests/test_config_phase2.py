from src.config import (
    load_accumulation_rules_config,
    load_news_categories_config,
    load_news_sources_config,
    load_officials_watchlist_config,
    load_options_config,
    load_sec_forms_config,
    load_technical_indicators_config,
)


def test_phase2_configs_load_as_mappings():
    assert "default_forms" in load_sec_forms_config()
    assert "providers" in load_news_sources_config()
    assert "categories" in load_news_categories_config()
    assert "officials" in load_officials_watchlist_config()
    assert "score_rules" in load_accumulation_rules_config()
    assert "provider" in load_options_config()
    assert "indicators" in load_technical_indicators_config()

