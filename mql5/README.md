# QuantTerm — Expert Advisor MQL5 (exécution auto, démo)

Portage de la logique QuantTerm en **EA MQL5**, pour tourner **dans le terminal MT5**
comme tes autres algos (pas de Python/Wine externe). Un seul fichier, deux modes :

| Graphique | `Mode`              | Stratégie                              | Sortie |
|-----------|---------------------|----------------------------------------|--------|
| XAUUSD    | `MOMENTUM_ICHIMOKU` | Ichimoku 20/60/120 (or, momentum)      | SL `KStop`·ATR + TP `KTarget`·ATR |
| NAS100    | `MEANREV_RSI`       | RSI 25/75 fade (nasdaq, mean-reversion)| SL protectif + fermeture au retour à la moyenne |

Sizing **risque fixe** (`RiskPct`, 1 % par défaut) via la valeur du tick du broker —
identique à `quantterm/broker_mt5.py::compute_lot`. Décision **sur barre clôturée**,
entrée **sur transition** (pas de ré-entrée en boucle après un stop). Magic **770077**.

> ⚠️ **Démo.** L'edge a été mesuré sur GC=F/NQ=F (futures yfinance). XAUUSD (spot) et
> NAS100 (CFD) sont corrélés mais **différents** → laisser `DryRun=true` et observer les
> logs avant d'armer. Rien de réel tant que l'edge n'est pas confirmé sur CE feed.

---

## Déploiement sur le VPS (terminal `mt5c` = Blueberry)

Adapte `PREFIX` si besoin (`find / -iname terminal64.exe` t'a donné les chemins) :

```bash
PREFIX=/opt/mt5c/wineprefix
MT5="$PREFIX/drive_c/Program Files/MetaTrader 5"

# 1. Déposer l'EA dans le dossier Experts du terminal
mkdir -p "$MT5/MQL5/Experts/QuantTerm"
cp ~/quantterm/mql5/QuantTerm.mq5 "$MT5/MQL5/Experts/QuantTerm/"

# 2. Compiler .mq5 -> .ex5 (sans GUI) via MetaEditor
WINEPREFIX="$PREFIX" wine "$MT5/MetaEditor64.exe" \
  /compile:"C:\\Program Files\\MetaTrader 5\\MQL5\\Experts\\QuantTerm\\QuantTerm.mq5" /log
#   -> vérifier "0 error(s)" ; le .ex5 apparaît à côté du .mq5
```

## 3. Attacher l'EA (via noVNC : http://87.106.34.128:6080 / :6081)
Dans le terminal `mt5c`, active **Algo Trading** (bouton barre d'outils), puis :
1. Ouvre un graphique **XAUUSD** → glisse `QuantTerm` dessus → onglet *Inputs* :
   `Mode = MOMENTUM_ICHIMOKU`, `DryRun = true`. OK.
2. Ouvre un graphique **NAS100** → glisse `QuantTerm` dessus →
   `Mode = MEANREV_RSI`, `DryRun = true`. OK.
3. Onglet **Experts** (Toolbox) : tu dois voir les lignes de démarrage puis, aux
   transitions de signal, des `[DRY-RUN] OPEN LONG 0.12 lot @ … SL … TP …`.

## 4. Armer (quand le dry-run te convainc)
Sur chaque graphique : propriétés de l'EA → `DryRun = false`. Il enverra alors les
ordres réels (compte démo), toujours sous le magic 770077.

---

## Réglages clés (Inputs)
- `RiskPct` — risque par trade en % du capital (défaut 1.0).
- `KStop` / `KTarget` — stop / target en multiples d'ATR (2 / 3 par défaut).
- `Tenkan/Kijun/SenkouB` — Ichimoku (20/60/120, **params figés** de la recherche).
- `RSIPeriod/RSILow/RSIHigh/RSIMid` — RSI mean-rev (14 / 25 / 75 / 50).
- `MaxLot` — plafond de lot optionnel (0 = off).
- `Magic` — 770077 ; à changer seulement si collision avec un autre EA.

## Notes
- **1 EA par graphique.** Les deux instances vivent dans le même terminal `mt5c` ; le
  filtre par magic + `PositionSelect(_Symbol)` fait que chacune ne gère que son symbole.
- Vérifie que le broker autorise le **trading algo** et que les symboles s'appellent bien
  `XAUUSD` / `NAS100` dans le Market Watch (sinon renomme les graphiques en conséquence).
- Le lot est **arrondi au step inférieur** et **sauté** si `< volume_min` (log `SKIP`).
