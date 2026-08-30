"""Évaluation « challenge prop firm » d'une courbe d'equity.

On rejoue la courbe d'equity (base 1.0) jour par jour et on vérifie, dans l'ordre
chronologique, si un objectif de profit est atteint avant qu'une règle de risque
soit enfreinte :

- **objectif de profit** : atteindre `+profit_target` (ex. +10 %) ;
- **perte journalière max** : la perte d'une journée ne doit pas dépasser
  `max_daily_loss` du solde de début de journée (ex. 5 %) ;
- **perte totale max** : l'equity ne doit pas tomber sous un plancher, soit statique
  (depuis le solde initial), soit *trailing* (depuis le plus haut atteint) ;
- **jours de trading minimum** : l'objectif ne compte qu'après `min_trading_days` ;
- **limite de temps** : optionnelle (`max_days`).

⚠️ Les presets fournis sont des valeurs *typiques* à but d'exemple. Les règles réelles
varient d'une prop firm à l'autre (et changent souvent) — ajuste-les à ton challenge.

Note : sur des données journalières on ne dispose que des clôtures de l'equity, donc
la « perte journalière » est approximée de clôture à clôture (pas d'intraday).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class PropFirmRules:
    name: str
    profit_target: float          # objectif, ex. 0.10 pour +10 %
    max_daily_loss: float         # perte journalière max, ex. 0.05
    max_total_loss: float         # perte totale max, ex. 0.10
    min_trading_days: int = 0     # jours de trading minimum avant validation
    max_days: int | None = None   # limite de temps (jours), None = illimité
    trailing: bool = False        # drawdown total mesuré depuis le pic (trailing) ?


# Presets d'exemple — À VÉRIFIER/AJUSTER selon ta prop firm.
PRESETS: dict[str, PropFirmRules] = {
    "2step-p1": PropFirmRules("2 étapes · Phase 1", 0.08, 0.05, 0.10, min_trading_days=4),
    "2step-p2": PropFirmRules("2 étapes · Phase 2", 0.05, 0.05, 0.10, min_trading_days=4),
    "1step": PropFirmRules("1 étape (trailing)", 0.10, 0.05, 0.06, min_trading_days=5, trailing=True),
    "instant": PropFirmRules("Funding direct", 0.06, 0.04, 0.08, min_trading_days=3, trailing=True),
}


@dataclass
class PropFirmResult:
    rules: PropFirmRules
    passed: bool
    reason: str                   # explication du verdict
    target_hit_day: int | None    # indice de barre où l'objectif est atteint
    breach_day: int | None        # indice de barre de la violation
    breach_date: pd.Timestamp | None
    trading_days: int             # jours réellement tradés
    days_elapsed: int             # jours écoulés jusqu'au verdict
    worst_daily_loss: float       # pire perte journalière observée (valeur <= 0)
    max_drawdown: float           # pire drawdown observé (valeur <= 0)
    final_return: float           # rendement au moment du verdict

    @property
    def status(self) -> str:
        return "RÉUSSI" if self.passed else "ÉCHOUÉ"

    def summary(self) -> str:
        r = self.rules
        lines = [
            f"[{r.name}]  ->  {self.status}",
            f"Motif           : {self.reason}",
            f"Objectif        : +{r.profit_target:.0%}   "
            f"(atteint : {'oui' if self.target_hit_day is not None else 'non'})",
            f"Perte j. max    : {r.max_daily_loss:.0%}   (pire jour : {self.worst_daily_loss:+.2%})",
            f"Perte tot. max  : {r.max_total_loss:.0%}{' trailing' if r.trailing else ''}"
            f"   (pire DD : {self.max_drawdown:+.2%})",
            f"Jours tradés    : {self.trading_days} (min {r.min_trading_days})",
            f"Jours écoulés   : {self.days_elapsed}"
            + (f" / {r.max_days} max" if r.max_days else ""),
            f"Rendement final : {self.final_return:+.2%}",
        ]
        return "\n".join(lines)


def evaluate(
    equity: pd.Series,
    rules: PropFirmRules,
    positions: pd.Series | None = None,
) -> PropFirmResult:
    """Évalue une courbe d'``equity`` (base 1.0) contre un jeu de ``rules``.

    ``positions`` (optionnel) sert à compter les jours réellement tradés ; sinon on
    compte les jours à rendement non nul.
    """
    equity = equity.dropna()
    if equity.empty:
        raise ValueError("Courbe d'equity vide.")

    daily_ret = equity.pct_change()
    # Jours de trading : position non nulle, ou à défaut rendement non nul.
    if positions is not None:
        active = positions.reindex(equity.index).fillna(0.0) != 0.0
    else:
        active = daily_ret.fillna(0.0) != 0.0

    target = 1.0 + rules.profit_target
    peak = float(equity.iloc[0])
    trading_days = 0
    worst_daily = 0.0
    worst_dd = 0.0
    target_hit: int | None = None

    for i, (ts, eq) in enumerate(zip(equity.index, equity.to_numpy())):
        eq = float(eq)
        peak = max(peak, eq)

        if bool(active.iloc[i]):
            trading_days += 1

        # --- perte journalière (clôture à clôture) ---
        if i > 0:
            day = eq / float(equity.iloc[i - 1]) - 1.0
            worst_daily = min(worst_daily, day)
            if day <= -rules.max_daily_loss - 1e-12:
                return PropFirmResult(
                    rules, False,
                    f"Perte journalière dépassée ({day:.2%}) le {ts.date()}.",
                    None, i, ts, trading_days, i, worst_daily, worst_dd,
                    eq - 1.0,
                )

        # --- perte totale (statique depuis le solde initial, ou trailing depuis le pic) ---
        floor = peak * (1.0 - rules.max_total_loss) if rules.trailing else (1.0 - rules.max_total_loss)
        dd = eq / peak - 1.0
        worst_dd = min(worst_dd, dd)
        if eq <= floor + 1e-12:
            ref = "trailing" if rules.trailing else "statique"
            return PropFirmResult(
                rules, False,
                f"Perte totale max ({ref}) dépassée le {ts.date()}.",
                None, i, ts, trading_days, i, worst_daily, worst_dd,
                eq - 1.0,
            )

        # --- limite de temps ---
        if rules.max_days is not None and i > rules.max_days:
            return PropFirmResult(
                rules, False,
                f"Objectif non atteint dans le délai ({rules.max_days} jours).",
                None, None, None, trading_days, i, worst_daily, worst_dd,
                eq - 1.0,
            )

        # --- objectif de profit (uniquement après le minimum de jours) ---
        if eq >= target and trading_days >= rules.min_trading_days:
            return PropFirmResult(
                rules, True,
                f"Objectif +{rules.profit_target:.0%} atteint le {ts.date()}.",
                i, None, None, trading_days, i, worst_daily, worst_dd,
                eq - 1.0,
            )
        if eq >= target:
            target_hit = i  # atteint mais min de jours non encore satisfait

    # Fin des données sans breach ni validation.
    final = float(equity.iloc[-1]) - 1.0
    if target_hit is not None:
        reason = (
            f"Objectif atteint mais minimum de {rules.min_trading_days} "
            f"jours de trading non satisfait ({trading_days})."
        )
    else:
        reason = f"Objectif +{rules.profit_target:.0%} non atteint (fin : {final:+.2%})."
    return PropFirmResult(
        rules, False, reason, target_hit, None, None,
        trading_days, len(equity) - 1, worst_daily, worst_dd, final,
    )
