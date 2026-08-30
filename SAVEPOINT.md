# 🗿 Point de sauvegarde — QuantTerm

> État du projet au **30/08/2026**. Ce fichier résume où on en est, comment
> relancer, et ce qui reste à faire — pour reprendre le travail sans rien perdre.

---

## 📍 Où on en est

Terminal quant fonctionnel en Python, avec interface TUI (Textual) style
**Bloomberg** et accès CLI. 8 commits en place, tout tourne sur **Python 3.14**
dans `.venv`.

| Brique | État | Notes |
|---|---|---|
| Données marché (yfinance + cache parquet) | ✅ | testé, réseau OK |
| Indicateurs techniques (21 au total) | ✅ | validés sur données réelles |
| Moteur de backtest vectorisé | ✅ | 7 stratégies d'exemple |
| Screener d'univers + filtres | ✅ | 13 actifs par défaut |
| **Challenge prop firm** | ✅ | verdict RÉUSSI/ÉCHOUÉ, 4 presets |
| Graphiques terminal (textual-plotext) | ✅ | widgets auto-dimensionnés |
| TUI Textual (dense, mono-écran) | ✅ | montage + interactions testés |
| CLI (`quote`/`backtest`/`screen`/`prop`) | ✅ | testé |
| Tests unitaires (pytest) | ✅ | 35 tests, hors-ligne, `tests/` |

---

## 🚀 Relancer le projet

```bash
cd "C:/Users/mateo/Documents/CODE PROJET/Terminal"

# Interface TUI complète (à lancer dans un vrai terminal ; Windows Terminal conseillé)
.venv/Scripts/python.exe -m quantterm

# CLI
.venv/Scripts/python.exe -m quantterm quote AAPL
.venv/Scripts/python.exe -m quantterm backtest MSFT --strategy macd --period 2y
.venv/Scripts/python.exe -m quantterm screen --period 1y
.venv/Scripts/python.exe -m quantterm prop AAPL --strategy macd --preset 1step
.venv/Scripts/python.exe -m quantterm prop NVDA --scan   # combos qui valident

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
├── app.py          # application Textual (interface dense « Bloomberg »)
├── widgets.py      # widgets graphiques textual-plotext (Price/Oscillator/Equity)
├── data.py         # récupération yfinance + cache disque (.cache/*.parquet, TTL 1h)
├── indicators.py   # 21 indicateurs techniques
├── backtest.py     # moteur vectorisé + 7 stratégies + métriques
├── propfirm.py     # évaluation challenge prop firm (règles + presets)
├── screener.py     # scan d'univers + filtres
└── charts.py       # ancien rendu plotext texte (conservé, plus utilisé par la TUI)
```

**Conventions clés :**
- Une *stratégie* = fonction `df -> position cible` (1 = long, 0 = cash, -1 = short).
- Le backtest applique la position à la barre **t+1** (pas de look-ahead), coûts inclus.
- Les indicateurs « prix » prennent une `Series` ; ceux qui ont besoin de
  High/Low/Volume prennent le **DataFrame OHLCV** complet.
- Les graphiques de la TUI sont des **widgets `PlotextPlot`** : ils se dimensionnent
  seuls. NE PAS revenir à du texte plotext dans un `Static` (ça débordait — cf. pièges).

---

## 🖥️ Interface (style Bloomberg, mono-écran)

- **Barre haut** : ticker (input), période, stratégie, oscillateur, preset prop firm.
- **Colonne gauche** : courbe de prix (clôture + SMA20/50), oscillateur, courbe d'equity.
- **Colonne droite** : cotation (prix/variation/H-L-Vol), watchlist **cliquable**
  (un clic charge le ticker), métriques de backtest, verdict prop firm.
- **Raccourcis** : `f` focus ticker · `r` rafraîchit · `s` re-scan · `q` quitte.
- Thème noir + accents ambre, vert/rouge directionnels.

---

## 📊 Contenu détaillé

**Indicateurs** (`indicators.py`)
- Tendance/prix : `sma`, `ema`, `wma`, `macd`, `bollinger`, `keltner`, `donchian`
- Oscillateurs : `rsi`, `stochastic`, `williams_r`, `cci`, `mfi`, `roc`, `momentum`, `zscore`
- Volatilité/volume : `atr`, `true_range`, `volatility`, `obv`, `vwap`
- Force de tendance : `adx` (+DI / -DI / ADX) · Utilitaires : `returns`

**Stratégies** (`backtest.STRATEGIES`)
`sma`, `rsi`, `macd`, `bollinger`, `donchian`, `adx`, `hold`

**Oscillateurs affichables dans la TUI** (`widgets.OSCILLATORS`)
`rsi`, `macd`, `stochastic`, `atr`, `cci`, `mfi`, `williams`, `adx`

**Presets prop firm** (`propfirm.PRESETS`) — ⚠️ valeurs d'exemple, à ajuster
`2step-p1` (8%/5%/10%) · `2step-p2` (5%/5%/10%) · `1step` (10%/5%/6% trailing) ·
`instant` (6%/4%/8% trailing)

---

## ⚠️ Pièges connus / décisions

- **Graphiques TUI = widgets `textual-plotext`**, jamais du texte plotext fixe dans
  un `Static` : ça débordait et rendait l'écran illisible (bug corrigé, commit e3639fc).
- **plotext épinglé `<6`** : la 6.0.0 a une API totalement incompatible.
- **pandas 3.0** : `fillna(method=...)` supprimé → utiliser `.ffill()`/`.bfill()`.
- Console Windows en cp1252 : accents mal rendus en CLI brute → `PYTHONIOENCODING=utf-8`.
  La TUI n'est pas concernée. **Windows Terminal** > vieux `cmd.exe` pour le rendu.
- SMA200 indisponible sur périodes courtes → le screener retombe sur la SMA50.
- Prop firm : perte journalière approximée **de clôture à clôture** (pas d'intraday).

---

## 🎯 Prochaines étapes possibles

- [ ] Perte journalière **intraday** (via High/Low) pour un verdict prop firm plus réaliste
- [ ] Ajouter les **règles exactes** de ta prop firm comme preset
- [ ] Colonnes ATR / ADX / stochastique dans le **screener**
- [ ] **Comparaison de stratégies** côte à côte (equity superposées vs buy & hold)
- [ ] **Watchlists** personnalisables (univers de screener sauvegardé)
- [ ] **Optimisation de paramètres** (grid search sur les stratégies)
- [x] **Tests unitaires** pytest (35 tests hors-ligne dans `tests/`)
- [x] **Refonte interface** style Bloomberg + graphiques auto-dimensionnés
- [x] **Challenge prop firm** (module + CLI + TUI)

---

## 🧾 Historique git

```
139b59c  Ajout evaluation challenge prop firm
f03ad77  Graphique de prix en courbe (cloture + SMA) au lieu de chandeliers
e3639fc  Fix majeur: graphiques via textual-plotext (fin des debordements)
3ef1143  Refonte interface style Bloomberg (dense, multi-panneaux)
bfa12d8  Fix: graphiques adaptatifs a la taille de la fenetre
82a788d  Ajout suite de tests pytest hors-ligne + point de sauvegarde
a649964  Ajout de 15 indicateurs, 4 stratégies et panneau oscillateur TUI
4258199  Initial commit: terminal quant
```
