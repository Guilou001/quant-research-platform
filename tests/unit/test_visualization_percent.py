"""Les figures en pourcentage et la lisibilité des axes logarithmiques, calculées à la main."""

from __future__ import annotations

import pandas as pd
import pytest

from quantlab.analytics.visualization.figures import cumulative_return_pct, equity_curve


def test_le_rendement_cumule_en_pourcentage_suit_le_calcul_a_la_main() -> None:
    """+10 % puis -10 % finit à -1 %, et une seconde série à +5 % puis +5 % finit à +10,25 %."""
    index = pd.date_range("2020-01-31", periods=2, freq="ME")
    fig, cumul = cumulative_return_pct(
        {"A": pd.Series([0.10, -0.10], index=index), "B": pd.Series([0.05, 0.05], index=index)}
    )
    assert cumul["A"].tolist() == pytest.approx([10.0, -1.0])
    assert cumul["B"].tolist() == pytest.approx([5.0, 10.25])
    assert "%" in fig.axes[0].get_ylabel()
    assert "finit à" in fig.axes[0].get_title()


def test_l_echelle_logarithmique_porte_des_nombres_ordinaires() -> None:
    """Aucune graduation d'une richesse cumulée n'affiche une puissance de dix."""
    index = pd.date_range("2020-01-31", periods=24, freq="ME")
    serie = pd.Series([0.03, -0.05] * 12, index=index)
    fig, _ = equity_curve({"A": serie}, log_scale=True)
    ax = fig.axes[0]
    fig.canvas.draw()
    etiquettes = [t.get_text() for t in ax.yaxis.get_minorticklabels() + ax.yaxis.get_majorticklabels()]
    etiquettes = [e for e in etiquettes if e]
    assert etiquettes, "aucune étiquette rendue"
    assert not any("10^" in e or "e-" in e or "×" in e or "$\\mathdefault" in e for e in etiquettes), (
        etiquettes
    )
