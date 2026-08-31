# QuantTerm — Terminal quant

Un terminal d'analyse quantitative qui vit **dans le terminal**, façon Bloomberg
Terminal en version texte. Données de marché, graphiques, indicateurs techniques,
backtesting de stratégies et screener d'univers.

## Fonctionnalités

- **Données marché** — cours OHLCV via [yfinance](https://github.com/ranaroussi/yfinance), avec cache local (parquet).
- **Graphiques** — chandeliers + moyennes mobiles directement dans le terminal ([plotext](https://github.com/piccolomo/plotext)).
- **Indicateurs** (module `indicators`) — tendance/prix : SMA, EMA, WMA, MACD, Bollinger, Keltner, Donchian, **Ichimoku** ; oscillateurs : RSI, stochastique, Williams %R, CCI, MFI, ROC, momentum, z-score ; volatilité/volume : ATR, True Range, volatilité annualisée, OBV, VWAP ; force de tendance : ADX/DMI.
- **Backtesting** — moteur vectorisé léger, 8 stratégies d'exemple (SMA, RSI, MACD, Bollinger, Donchian, ADX, Ichimoku, buy & hold) et métriques (rendement, CAGR, Sharpe, max drawdown, win rate).
- **Backtest intra-barre** (scalp) — moteur événementiel avec entrée sur transition de signal, **stop/target en multiples d'ATR** vérifiés sur High/Low, time-stop et hypothèse conservatrice (stop d'abord). Pensé pour l'intraday (5m/15m).
- **Challenge prop firm** (module `propfirm`) — rejoue la courbe d'equity jour par jour et dit **RÉUSSI / ÉCHOUÉ** contre les règles (objectif de profit, perte journalière max, perte totale max statique ou *trailing*, jours de trading min, limite de temps). Presets d'exemple à ajuster à ta prop firm. Inclut un **simulateur de dimensionnement** (`size_for_challenge`) : combien de contrats futures un capital autorise sans enfreindre les règles de risque.
- **Screener** — scan d'un univers d'actifs avec filtres (RSI, tendance, performance).
- **Signal live** (module `live`) — direction courante **LONG / SHORT / FLAT** d'une stratégie sur les dernières données, avec niveaux de stop/target en ATR. Mode `--watch` pour tourner en boucle sur un VPS (compte démo). Outil d'aide à la décision : **il ne trade pas**.
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

# Challenge prop firm
python -m quantterm prop AAPL --strategy macd --preset 1step --period 2y
python -m quantterm prop NVDA --scan        # toutes les combos qui valident

# Scalp intra-barre (intraday, stop/target en ATR)
python -m quantterm scalp GC=F --strategy ichimoku --interval 5m --stop 2 --target 3
python -m quantterm scalp GC=F --strategy ichimoku --prop 2step-p1   # + verdict prop firm

# Dimensionnement prop firm : nb de contrats optimal pour un capital + des règles
python -m quantterm scalp GC=F --strategy ichimoku --prop 2step-p1 --capital 10000 --contract MGC

# Signal live long/short/flat (démo/VPS) — one-shot ou en boucle
python -m quantterm signal GC=F --strategy ichimoku
python -m quantterm signal GC=F --strategy ichimoku --watch 60   # rafraîchit toutes les 60 s
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
