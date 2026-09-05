# 🗿 Point de sauvegarde — QuantTerm

> État du projet au **05/09/2026**. Ce fichier résume où on en est, comment
> relancer, et ce qui reste à faire — pour reprendre le travail sans rien perdre.

---

## 📍 Où on en est

Terminal quant fonctionnel en Python, avec interface TUI (Textual) style
**Bloomberg** et accès CLI. 8 commits en place, tout tourne sur **Python 3.14**
dans `.venv`.

| Brique | État | Notes |
|---|---|---|
| Données marché (yfinance + cache parquet) | ✅ | testé, réseau OK ; intraday 5m/1m OK |
| Indicateurs techniques (22 au total) | ✅ | validés sur données réelles ; +Ichimoku |
| Moteur de backtest vectorisé | ✅ | 8 stratégies d'exemple |
| **Backtest intra-barre (scalp)** | ✅ | `run_intrabar` : stop/target ATR, entrée sur transition |
| Screener d'univers + filtres | ✅ | 13 actifs par défaut |
| **Challenge prop firm** | ✅ | verdict RÉUSSI/ÉCHOUÉ, 4 presets |
| **Dimensionnement contrats** | ✅ | `size_for_challenge` : nb contrats max sous les règles de risque |
| **Signal live (démo/VPS)** | ✅ | `live.py` + CLI `signal --watch` : LONG/SHORT/FLAT + stop/target |
| **Watch multi-actif (démo)** | ✅ | `live.INSTRUMENTS` + CLI `watch --every` : or (Ichimoku) + nasdaq (RSI mean-rev) |
| **Exécution auto MT5 (Python)** | ✅ | `broker_mt5.py` + `trader.py` + CLI `trade` : sizing risque 1 %, dry-run, magic 770077 (setup Windows-MT5) |
| **Exécution auto MT5 (EA MQL5)** | ✅ | `mql5/QuantTerm.mq5` : **voie VPS** (EA dans le terminal, comme les autres algos) |
| **Notifications Telegram** | ✅ | `notify.py` + `signal --telegram` : envoi des signaux frais (dédup), non déployé |
| Graphiques terminal (textual-plotext) | ✅ | widgets auto-dimensionnés |
| TUI Textual (dense, mono-écran) | ✅ | montage + interactions testés |
| CLI (`quote`/`backtest`/`screen`/`prop`/`scalp`/`signal`/`watch`) | ✅ | testé ; UTF-8 forcé, plus besoin de `PYTHONIOENCODING` |
| Tests unitaires (pytest) | ✅ | 43 tests, hors-ligne, `tests/` |

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

# Scalp intra-barre (edge Ichimoku sur l'or, cf. section Recherche scalp)
.venv/Scripts/python.exe -m quantterm scalp GC=F --strategy ichimoku --stop 2 --target 3
.venv/Scripts/python.exe -m quantterm scalp GC=F --strategy ichimoku --prop 2step-p1

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
├── backtest.py     # moteur vectorisé (run) + événementiel intra-barre (run_intrabar) + 8 stratégies
├── propfirm.py     # évaluation challenge prop firm (règles + presets) + dimensionnement contrats
├── live.py         # signal temps réel LONG/SHORT/FLAT (from_df pur + compute réseau) + INSTRUMENTS
├── broker_mt5.py   # pont MetaTrader5 (connexion path+login, rates, ordres) + sizing risque (compute_lot)
├── trader.py       # boucle exécution auto : décision par instrument + dry-run
├── notify.py       # notifications Telegram (TelegramNotifier, config par variables d'env)
├── screener.py     # scan d'univers + filtres
└── charts.py       # ancien rendu plotext texte (conservé, plus utilisé par la TUI)

mql5/
├── QuantTerm.mq5   # Expert Advisor (voie VPS) : Ichimoku (or) + RSI mean-rev (nasdaq)
└── README.md       # compilation MetaEditor + attache aux graphiques XAUUSD/NAS100
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
`sma`, `rsi`, `rsi_meanrev`, `macd`, `bollinger`, `donchian`, `adx`, `ichimoku`, `hold`
- `rsi_meanrev` = mean-reversion indices : **fade** RSI 25/75, **exit au retour à la
  moyenne** (pas de target ATR). Candidat scalp NQ=F (cf. Recherche indices 05/09).

**Oscillateurs affichables dans la TUI** (`widgets.OSCILLATORS`)
`rsi`, `macd`, `stochastic`, `atr`, `cci`, `mfi`, `williams`, `adx`

**Presets prop firm** (`propfirm.PRESETS`) — ⚠️ valeurs d'exemple, à ajuster
`2step-p1` (8%/5%/10%) · `2step-p2` (5%/5%/10%) · `1step` (10%/5%/6% trailing) ·
`instant` (6%/4%/8% trailing)

---

## 🔬 Recherche scalp (31/08/2026) — edge Ichimoku sur l'or

Recherche menée sur **futures/forex en 5 min** (yfinance : 60j de 5m, 7j de 1m).
Méthode anti-illusion : split in-sample/out-of-sample **+ walk-forward** (params figés,
6 tranches chronologiques) **+ sensibilité au coût** **+ exécution intra-barre réaliste**
(stop/target ATR sur High/Low). Coûts round-trip modélisés : ES/NQ ~1 bp, GC ~1.2 bp.

**Enseignement principal — le régime dicte la famille :**
- **Indices (ES, NQ) → mean-reversion** (RSI). Le momentum/Ichimoku s'y fait hacher.
- **Or (GC) → momentum**, et **Ichimoku "full" (20/60/120) est le meilleur** moteur trouvé.

**Edge retenu :** `ichimoku` sur **GC=F 5m, stop 2 ATR / target 3 ATR**.
- Intra-barre + walk-forward : Sharpe/trade positif, **~+4.5 bps net/trade**, ~1 trade/jour,
  **maxDD ~1 %**, 67-83 % des tranches positives (selon la largeur de stop).
- Robuste au coût (tient jusqu'à ~3× l'hypothèse). Les stops **serrés (<1.5 ATR) tuent
  tout** : un edge fin a besoin de respirer.

**Prop firm :** l'edge fait ~+4.5 % en 60j sur le **notionnel** → l'effet de levier des
futures le transforme sur un compte. Sur **10k$ + or (MGC) + règles 8%/5%/10%** :
`size_for_challenge` retient **1 contrat MGC** (levier 4.5x, plafonné par la perte
journalière/totale) → **RÉUSSI** sur le sample (pire jour −3 %, pire DD −7.5 %, sous les
limites 5 %/10 %). 2 MGC ne « passe » que par chance d'ordre (DD complet −15 % > 10 %).
⚠️ Le pire jour observé sous-estime le tail : N stops groupés = N×~1.4 %/compte à 1 MGC.

**Réserves d'honnêteté :** 60 jours = **un seul régime** ; ~100 trades (correct, pas
énorme) ; **qualité data yfinance intraday** approximative (FX bid-only, pas de vrai volume
→ EURUSD sans edge exploitable ici). Scripts de recherche dans le scratchpad de session.

---

## 🧪 Validation robuste (01/09/2026) — verdict : 🟡 hypothèse crédible mais fragile

Batterie de tests **à params FIGÉS** (Ichimoku 20/60/120, stop 2 / target 3 ATR — zéro
ré-optimisation). Comme rien n'est ajusté, chaque tranche est déjà de l'**OOS** : le risque
résiduel n'est pas l'overfitting de paramètres, c'est le **régime** et le **coût réel**.

**1. Stabilité temporelle GC=F 5m (6 tranches chrono)** — 5/6 positives, aucune ne casse
(DD par tranche ~-0.6 à -0.9 %). Gain/trade variable ×4 (0.02→0.08 %) : edge **réel mais mince**.

**1b. Horizon long GC=F 1h ~2 ans** (le 5m plafonne à 60 j chez yfinance) — **+17.8 %**,
DD -7.2 %, **6/8 tranches positives** → la tendance momentum-or **persiste multi-régimes**,
donc pas un pur artefact des 60 j. **MAIS** fortement **concentrée** (une tranche jan→mai 2026
porte l'essentiel) et c'est du **1h, pas du 5m** → preuve de concept du *style*, pas validation
du 5m.

**2. Stress coûts/slippage** — **point mort ≈ 5 bps round-trip** (edge brut ~5.2 bps/trade,
en dépense 1, reste ~4). Slippage tick quasi indolore (+5 ticks/côté → +4.35 %→+2.41 %,
car 1 tick ≈ 0.23 bp à 4400 $). **Le tueur = le coût total, pas le slippage.**

**3. Généralisation ES=F / NQ=F (mêmes params)** — **ES -4.9 % (6/6 tranches nég.),
NQ -8.6 % (5/6 nég.)**. Sans appel → l'edge est **propre à l'or** (les indices sont
mean-reverting, le momentum s'y fait hacher). **Ne PAS généraliser.**

**Verdict :** 🟡 **hypothèse crédible mais fragile — GC uniquement.**
Pas un edge validé, pas de généralisation, **pas de prop / pas de réel**.
> **Question falsifiable qui reste :** les **coûts d'exécution réels GC/MGC** laissent-ils
> survivre les ~4 bps/trade ? (le backtest yfinance ne modélise ni spread réel ni slippage réel.)

**Décision de discipline :** on **ne fait PAS** de tuning post-résultat (pas de balayage
stop/target, pas de 15m) — ça fabriquerait l'illusion qu'on cherche à éviter. On teste
l'hypothèse **en démo GC=F uniquement, 1 MGC, params figés**, et on juge sur le coût réel.

Script de validation : `scratchpad/validate.py` (session).

---

## 🔬 Recherche indices (05/09/2026) — scalp mean-reversion NQ/ES

Objectif : trouver un edge scalp sur **Nasdaq (NQ=F)** et **SP500 (ES=F)** pour trader
plus que l'or. Même méthode anti-illusion (params figés, walk-forward, stress coûts).

**Enseignement clé — l'exit compte autant que l'entrée :** un stop/**target ATR** (exit
momentum) **détruit** le mean-reversion. Le bon moteur est `run` avec **exit au retour à
la moyenne** (RSI recroise 50). Avec ça :
- **NQ=F 5m** RSI 25/75 : brut +9.8 %, **point mort ~5.6 bps/côté** (coût réel ~0.5-1 bp
  → grosse marge), Sharpe élevé, **WF 5/6**, et **toute la famille RSI** (20/80…30/70)
  positive → pas un point fragile isolé. **Meilleur candidat scalp indices trouvé.**
- **ES=F 5m** : bien plus faible (point mort ~2 bps, WF 4/6) → **pas retenu**.

**Contrôle robustesse (1h ~2 ans, comme l'or) : 🟡 confirmation faible.**
NQ 1h : RSI 25/75 seulement +4.8 % / WF 4/8, et **30/70 fait -9 %** (sensible aux params) ;
ES 1h l'inverse (+5.8 %, WF 6/8). Quand l'actif gagnant dépend de l'horizon = edge **fin,
proche du bruit**. Rien de comparable à l'or (1h : +17.8 %, WF 6/8).

**Décision :** on câble **NQ=F en DÉMO** (RSI 25/75, params figés) via le watch multi-actif,
**pas de réel** — mêmes règles que l'or. ES en attente. Verdict : 🟡 **candidat démo, non
validé multi-régime.** Scripts : `scratchpad/research_indices*.py` (session).

**Portefeuille démo actuel** (`live.INSTRUMENTS`) : `GC=F`→`ichimoku`, `NQ=F`→`rsi_meanrev`.
Lancer : `python -m quantterm watch --every 60` (ou `--telegram`).

---

## 🤖 Exécution auto MT5 (05/09/2026) — démo, VPS IONOS

**Deux voies d'exécution, même logique/sizing :**
- **VPS IONOS `87.106.34.128` → EA MQL5** (`mql5/QuantTerm.mq5`). C'est la voie retenue :
  le VPS n'a **aucun Python Wine**, ses 2 algos sont des **EA dans le terminal** (services
  systemd `mt5b`/`mt5c`). On attache donc l'EA au terminal **`mt5c` (Blueberry, le compte
  démo)** sur les graphiques **XAUUSD** (mode Ichimoku) et **NAS100** (mode RSI mean-rev).
  Compile + attache : voir `mql5/README.md`. DryRun d'abord, magic 770077.
- **Setup Windows-MT5 → bot Python** (`trade`), ci-dessous, si un jour Python pilote MT5
  directement. Sur le VPS il n'est PAS utilisable (pas de Python Wine).

Bot Python d'exécution des signaux (`python -m quantterm trade`) :

- **Feed cohérent** : le signal est calculé sur les **bougies MT5** (`copy_rates`), pas
  yfinance → signal et exécution sur le **même prix** (cf. piège futures↔CFD ci-dessous).
- **Sizing risque fixe** (`compute_lot`) : lot = `balance × 1 %` / (dist. stop en ATR ×
  valeur du tick). Balance lue dans le compte. Arrondi au step **inférieur**, skip si
  `< volume_min`. Testé (`tests/test_broker_mt5.py`).
- **Sorties** : or (momentum) = **SL+TP ATR** sur l'ordre ; nasdaq (mean-rev) = **SL
  protectif** + fermeture au **retour à la moyenne** (signal FLAT), géré par la boucle.
- **Sécurité** : `dry_run` par défaut (rien envoyé, tout loggé) ; `--live` pour armer.
  **Magic 770077** dédié → ne touche jamais aux 2 autres algos.
- **Config par env** (jamais en CLI) : `QUANTTERM_MT5_PATH` / `_LOGIN` / `_PASSWORD` /
  `_SERVER`. Symboles broker : **XAUUSD** (or), **NAS100** (nasdaq).

Lancer : `python -m quantterm trade` (dry-run) puis `trade --every 60 --live` (armé).

> ⚠️ **Non validé sur le feed broker.** L'edge a été mesuré sur GC=F/NQ=F (futures) ;
> XAUUSD (spot) et NAS100 (CFD) sont **corrélés mais différents** (spread, sessions).
> D'où : **démo uniquement**, observer que l'edge tient sur CE feed avant tout réel.

---

## ⚠️ Pièges connus / décisions

- **Graphiques TUI = widgets `textual-plotext`**, jamais du texte plotext fixe dans
  un `Static` : ça débordait et rendait l'écran illisible (bug corrigé, commit e3639fc).
- **plotext épinglé `<6`** : la 6.0.0 a une API totalement incompatible.
- **pandas 3.0** : `fillna(method=...)` supprimé → utiliser `.ffill()`/`.bfill()`.
- Console Windows en cp1252 : réglé dans le code via `_force_utf8()` en tête de `main()`
  (`sys.stdout/stderr.reconfigure`) → plus besoin de `PYTHONIOENCODING=utf-8` en CLI.
  La TUI n'est pas concernée. **Windows Terminal** > vieux `cmd.exe` pour le rendu.
- **Telegram** : token/chat_id lus dans `QUANTTERM_TG_TOKEN` / `QUANTTERM_TG_CHAT`
  (jamais en argument CLI, pour ne pas fuiter). `signal --telegram` n'envoie que sur
  signal **frais**, dédupliqué par (direction, barre) pour éviter le spam à chaque cycle.
- SMA200 indisponible sur périodes courtes → le screener retombe sur la SMA50.
- Prop firm : perte journalière approximée **de clôture à clôture** (pas d'intraday).
- **`fee` : conventions différentes !** `run()` = coût **par côté** (par changement de
  position) ; `run_intrabar()` = coût **aller-retour** par trade. Défauts : 5 bps (run)
  vs 1 bp (run_intrabar).
- `run_intrabar` n'entre que sur **transition** de signal (nouveau croisement), pas sur
  l'état persistant — sinon ré-entrée en boucle après chaque stop (churning). Bug
  rencontré et corrigé pendant la recherche : Ichimoku passait de 28 à 3000+ trades.
- Pour le verdict prop firm sur du scalp : **rééchantillonner l'equity intra-barre en
  journalier** (`.resample("1D").last()`) avant `propfirm.evaluate` (qui raisonne par jour).
- **MT5 = 1 terminal par processus** : chaque compte a son terminal + son process Python
  (`initialize(path=...) + login(...)`). Le bot tourne dans SON process, magic 770077, et
  `positions_get` est filtré par magic → il ne ferme jamais les trades des autres algos.
- **Feed futures ↔ broker** : GC=F/NQ=F (yfinance, futures) ≠ XAUUSD/NAS100 (broker, spot/CFD).
  Le bot calcule donc le signal sur les **rates MT5**, pas yfinance. Ne PAS mélanger les deux.
- **Mean-reversion ≠ exit ATR** : appliquer un stop/**target ATR** (`run_intrabar`) à une
  stratégie de réversion la fait paraître nulle/négative — l'edge est dans le **retour à
  la moyenne**, pas dans un objectif de continuation. Utiliser `run` avec exit sur retour
  médian. Découvert en cherchant l'edge indices (cf. Recherche indices 05/09).

---

## 🎯 Prochaines étapes possibles

- [ ] Perte journalière **intraday** (via High/Low) pour un verdict prop firm plus réaliste
- [ ] Ajouter les **règles exactes** de ta prop firm comme preset
- [ ] Colonnes ATR / ADX / stochastique dans le **screener**
- [ ] **Comparaison de stratégies** côte à côte (equity superposées vs buy & hold)
- [ ] **Watchlists** personnalisables (univers de screener sauvegardé)
- [ ] **Optimisation de paramètres** (grid search sur les stratégies)
- [x] **Dimensionnement prop firm** (`size_for_challenge` : capital + règles → nb contrats + verdict)
- [x] **Signal live** (`live.py` + CLI `signal --watch`) pour test démo sur VPS
- [x] **Watch multi-actif** (`live.INSTRUMENTS` + CLI `watch`) : or + nasdaq, chacun sa stratégie
- [x] **Recherche edge indices** (NQ/ES mean-rev) → 🟡 NQ démo, cf. Recherche indices 05/09
- [x] **Exécution auto MT5** (`broker_mt5.py` + `trader.py` + CLI `trade`) : démo, sizing risque 1 %, dry-run/magic
- [ ] **Confirmer l'edge sur le feed broker** (XAUUSD/NAS100) avant tout passage réel
- [x] **Validation robuste de l'edge** (stabilité temporelle + stress coûts + ES/NQ) → 🟡 GC seul, fragile (cf. section Validation 01/09)
- [ ] **Valider hors yfinance** (données intraday propres, ex. Binance/broker) — l'edge sur + de régimes
- [ ] Intégrer le scalp intra-barre dans la **TUI** (aujourd'hui CLI + module uniquement)
- [x] **Recherche edge scalp** : Ichimoku sur GC=F 5m (walk-forward + coûts + intra-barre)
- [x] **Backtest événementiel intra-barre** (`run_intrabar`, stop/target ATR) + indicateur Ichimoku
- [x] **Tests unitaires** pytest (40 tests hors-ligne dans `tests/`)
- [x] **Refonte interface** style Bloomberg + graphiques auto-dimensionnés
- [x] **Challenge prop firm** (module + CLI + TUI)

---

## 🧾 Historique git

```
06c866c  Edge indices mean-rev (NQ demo) + watch multi-actif or/nasdaq
6b5aaa1  Mise a jour du point de sauvegarde (Telegram, UTF-8, validation edge)
e514393  Signaux Telegram, fix UTF-8 CLI + validation robuste de l'edge
a7d18e3  Edge scalp Ichimoku (or) : moteur intra-barre, dimensionnement prop firm, signal live
9a211e1  Mise a jour du point de sauvegarde (UI Bloomberg, prop firm, 35 tests)
139b59c  Ajout evaluation challenge prop firm
f03ad77  Graphique de prix en courbe (cloture + SMA) au lieu de chandeliers
e3639fc  Fix majeur: graphiques via textual-plotext (fin des debordements)
3ef1143  Refonte interface style Bloomberg (dense, multi-panneaux)
bfa12d8  Fix: graphiques adaptatifs a la taille de la fenetre
82a788d  Ajout suite de tests pytest hors-ligne + point de sauvegarde
a649964  Ajout de 15 indicateurs, 4 stratégies et panneau oscillateur TUI
4258199  Initial commit: terminal quant
```
