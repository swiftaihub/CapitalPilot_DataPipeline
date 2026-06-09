from src.macro import calculate_cpi_yoy, calculate_macro_regime_score, label_macro_regime


def test_calculate_macro_regime_score_supportive_conditions():
    score = calculate_macro_regime_score(
        fed_funds_3m_change=-0.25,
        cpi_yoy_3m_change=-0.01,
        unemployment_3m_change=0.0,
        ten_two_spread=0.5,
        vix=15.0,
        dollar_3m_change_pct=0.0,
    )

    assert score == 2
    assert label_macro_regime(score) == "Risk-on / Easing-supportive"


def test_calculate_macro_regime_score_pressure_conditions():
    score = calculate_macro_regime_score(
        fed_funds_3m_change=0.25,
        cpi_yoy_3m_change=0.01,
        unemployment_3m_change=0.5,
        ten_two_spread=-0.3,
        vix=30.0,
        dollar_3m_change_pct=0.08,
    )

    assert score == -4
    assert label_macro_regime(score) == "Risk-off / Macro pressure"


def test_calculate_cpi_yoy():
    assert calculate_cpi_yoy(310.0, 300.0) == 310.0 / 300.0 - 1.0
    assert calculate_cpi_yoy(310.0, 0.0) is None
    assert calculate_cpi_yoy(None, 300.0) is None

