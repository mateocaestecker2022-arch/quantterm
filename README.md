# QuantTerm — Terminal quant

Un terminal d'analyse quantitative qui vit **dans le terminal**, façon Bloomberg
Terminal en version texte. Données de marché, graphiques, indicateurs techniques,
backtesting de stratégies et screener d'univers.

## Fonctionnalités

- **Données marché** — cours OHLCV via [yfinance](https://github.com/ranaroussi/yfinance), avec cache local (parquet).
- **Graphiques** — chandeliers + moyennes mobiles directement dans le terminal ([plotext](https://github.com/piccolomo/plotext)).
- **Indicateurs** (module `indicators`) — tendance/prix : SMA, EMA, WMA, MACD, Bollinger, Keltner, Donchian ; oscillateurs : RSI, stochastique, Williams %R, CCI, MFI, ROC, momentum, z-score ; volatilité/volume : ATR, True Range, volatilité annualisée, OBV, VWAP ; force de tendance : ADX/DMI.
- **Backtesting** — moteur vectorisé léger, 7 stratégies d'exemple (SMA, RSI, MACD, Bollinger, Donchian, ADX, buy & hold) et métriques (rendement, CAGR, Sharpe, max drawdown, win rate).
- **Screener** — scan d'un univers d'actifs avec filtres (RSI, tendance, performance).
- **Interface TUI** ([Textual](https://textual.textualize.io/)) + accès **CLI** rapide.

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
```

## Utilisation

### Interface TUI

```bash
python -m quantterm
```

Interface dense « Bloomberg », tout visible en même temps :
- **colonne gauche** : chandeliers + SMA, panneau oscillateur (RSI, MACD,
  stochastique, ATR, CCI, MFI, Williams %R, ADX) et courbe d'equity du backtest ;
- **colonne droite** : cotation (dernier prix / variation / H-L-Vol), **watchlist
  cliquable** (un clic charge le ticker) et métriques de backtest colorées.

Barre du haut : ticker, période, stratégie, oscillateur. Raccourcis : `f` cible
le champ ticker, `r` rafraîchit, `s` relance le scan, `q` quitte.

### En ligne de commande

```bash
python -m quantterm quote AAPL
python -m quantterm backtest AAPL --strategy sma --period 2y
python -m quantterm screen --period 1y
```

## Tests

Suite pytest hors-ligne (données OHLCV synthétiques, aucun appel réseau) :

```bash
pip install -e .[dev]        # ou: pip install pytest
python -m pytest
```

Couvre les indicateurs (bornes, cohérence), le moteur de backtest (absence de
look-ahead, effet des frais, métriques) et le screener (métriques + filtres).

## Architecture

```
quantterm/
├── __main__.py     # point d'entrée : TUI ou sous-commandes CLI
├── app.py          # application Textual (3 onglets)
├── data.py         # récupération yfinance + cache disque
├── indicators.py   # indicateurs techniques (pandas)
├── backtest.py     # moteur vectorisé + stratégies d'exemple
├── screener.py     # scan d'univers + filtres
└── charts.py       # rendu des graphiques plotext
```

## Écrire une stratégie

Une stratégie est une fonction `df -> position cible` (1 = long, 0 = cash, -1 = short) :

```python
from quantterm import backtest, data, indicators as ind

def ma_strategie(df):
    fast = ind.ema(df["Close"], 10)
    slow = ind.ema(df["Close"], 30)
    return (fast > slow).astype(float)

df = data.get_history("MSFT", period="3y")
result = backtest.run(df, ma_strategie)
print(result.summary())
```

## Avertissement

Projet à but éducatif. Les données proviennent de sources gratuites et peuvent
être imprécises ou retardées. **Rien ici ne constitue un conseil en investissement.**
