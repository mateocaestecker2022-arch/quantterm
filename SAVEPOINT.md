# 🗿 Point de sauvegarde — QuantTerm

> État du projet au **30/08/2026**. Ce fichier résume où on en est, comment
> relancer, et ce qui reste à faire — pour reprendre le travail sans rien perdre.

---

## 📍 Où on en est

Terminal quant fonctionnel en Python, avec interface TUI (Textual) et accès CLI.
Deux commits en place, tout tourne sur **Python 3.14** dans `.venv`.

| Brique | État | Notes |
|---|---|---|
| Données marché (yfinance + cache parquet) | ✅ | testé, réseau OK |
| Indicateurs techniques (21 au total) | ✅ | validés sur données réelles |
| Moteur de backtest vectorisé | ✅ | 7 stratégies d'exemple |
| Screener d'univers + filtres | ✅ | 13 actifs par défaut |
| Graphiques terminal (plotext 5.3.2) | ✅ | chandeliers + oscillateurs |
| TUI Textual (3 onglets) | ✅ | montage testé headless |
| CLI (`quote` / `backtest` / `screen`) | ✅ | testé |
| Tests unitaires (pytest) | ✅ | 27 tests, hors-ligne, `tests/` |

---

## 🚀 Relancer le projet

```bash
cd "C:/Users/mateo/Documents/CODE PROJET/Terminal"

# Interface TUI complète (à lancer dans un vrai terminal)
.venv/Scripts/python.exe -m quantterm

# CLI
.venv/Scripts/python.exe -m quantterm quote AAPL
.venv/Scripts/python.exe -m quantterm backtest MSFT --strategy macd --period 2y
.venv/Scripts/python.exe -m quantterm screen --period 1y

# Tests (hors-ligne, ~0.5 s)
.venv/Scripts/python.exe -m pytest
```

Si l'environnement est à recréer :
```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pip install pytest   # pour les tests
```

---

## 🧱 Architecture

```
quantterm/
├── __main__.py     # point d'entrée : TUI par défaut, ou sous-commandes CLI
├── app.py          # application Textual (onglets Graphique / Backtest / Screener)
├── data.py         # récupération yfinance + cache disque (.cache/*.parquet, TTL 1h)
├── indicators.py   # 21 indicateurs techniques
├── backtest.py     # moteur vectorisé + 7 stratégies + métriques
├── screener.py     # scan d'univers + filtres
└── charts.py       # rendu plotext (price_chart, line_chart, oscillator_chart)
```

**Conventions clés :**
- Une *stratégie* = fonction `df -> position cible` (1 = long, 0 = cash, -1 = short).
- Le backtest applique la position à la barre **t+1** (pas de look-ahead), coûts inclus.
- Les indicateurs « prix » prennent une `Series` ; ceux qui ont besoin de
  High/Low/Volume prennent le **DataFrame OHLCV** complet.

---

## 📊 Contenu détaillé

**Indicateurs** (`indicators.py`)
- Tendance/prix : `sma`, `ema`, `wma`, `macd`, `bollinger`, `keltner`, `donchian`
- Oscillateurs : `rsi`, `stochastic`, `williams_r`, `cci`, `mfi`, `roc`, `momentum`, `zscore`
- Volatilité/volume : `atr`, `true_range`, `volatility`, `obv`, `vwap`
- Force de tendance : `adx` (+DI / -DI / ADX)
- Utilitaires : `returns`

**Stratégies** (`backtest.STRATEGIES`)
`sma`, `rsi`, `macd`, `bollinger`, `donchian`, `adx`, `hold`

**Oscillateurs affichables dans la TUI** (`charts.OSCILLATORS`)
`rsi`, `macd`, `stochastic`, `atr`, `cci`, `mfi`, `williams`, `adx`

---

## ⚠️ Pièges connus / décisions

- **plotext épinglé `<6`** : la 6.0.0 a une API totalement incompatible (pas de
  `clf`/`candlestick`/`build`). Ne pas mettre à jour sans réécrire `charts.py`.
- **pandas 3.0** : `fillna(method=...)` est supprimé → utiliser `.ffill()`/`.bfill()`.
- Console Windows en cp1252 : les accents s'affichent mal en CLI brute. Utiliser
  `PYTHONIOENCODING=utf-8` ; la TUI n'est pas concernée.
- SMA200 indisponible sur périodes courtes → le screener retombe sur la SMA50
  pour la tendance (sinon `n/a`).

---

## 🎯 Prochaines étapes possibles

- [ ] Colonnes ATR / ADX / stochastique dans le **screener**
- [ ] **Comparaison de stratégies** côte à côte (equity superposées vs buy & hold)
- [ ] **Watchlists** personnalisables (univers de screener sauvegardé)
- [ ] **Optimisation de paramètres** (grid search sur les stratégies)
- [x] **Tests unitaires** pytest (27 tests hors-ligne dans `tests/`)
- [ ] Paramétrage des stratégies depuis la TUI

---

## 🧾 Historique git

```
a649964  Ajout de 15 indicateurs, 4 stratégies et panneau oscillateur TUI
4258199  Initial commit: terminal quant (data, indicateurs, backtest, screener, TUI)
```
