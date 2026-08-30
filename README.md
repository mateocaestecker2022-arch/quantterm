# QuantTerm — Terminal quant

Un terminal d'analyse quantitative qui vit **dans le terminal**, façon Bloomberg
Terminal en version texte. Données de marché, graphiques, indicateurs techniques,
backtesting de stratégies et screener d'univers.

## Fonctionnalités

- **Données marché** — cours OHLCV via [yfinance](https://github.com/ranaroussi/yfinance), avec cache local (parquet).
- **Graphiques** — chandeliers + moyennes mobiles directement dans le terminal ([plotext](https://github.com/piccolomo/plotext)).
- **Indicateurs** — SMA, EMA, RSI, MACD, Bollinger, volatilité (module `indicators`).
- **Backtesting** — moteur vectorisé léger avec métriques (rendement, CAGR, Sharpe, max drawdown, win rate).
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

Onglets : **Graphique** (chandeliers + SMA), **Backtest** (equity + métriques),
**Screener** (tableau triable). Saisis un ticker, choisis la période et la
stratégie dans les menus. `r` rafraîchit, `q` quitte.

### En ligne de commande

```bash
python -m quantterm quote AAPL
python -m quantterm backtest AAPL --strategy sma --period 2y
python -m quantterm screen --period 1y
```

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
