"""Notifications Telegram pour les signaux live.

Envoie un message sur un chat Telegram quand une stratégie produit un signal
frais (nouvelle entrée LONG/SHORT). Tu prends ensuite le trade **à la main** sur
ton compte démo — cet outil ne passe aucun ordre.

Configuration par variables d'environnement (pour ne pas exposer le token dans
la ligne de commande / l'historique shell) :

    QUANTTERM_TG_TOKEN   jeton du bot (donné par @BotFather)
    QUANTTERM_TG_CHAT    id du chat/canal destinataire

Créer un bot : parler à @BotFather -> /newbot -> récupérer le token.
Trouver son chat id : écrire un message au bot puis ouvrir
    https://api.telegram.org/bot<TOKEN>/getUpdates
et lire ``result[].message.chat.id``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import requests

_API = "https://api.telegram.org/bot{token}/sendMessage"


@dataclass
class TelegramNotifier:
    token: str
    chat_id: str
    timeout: float = 10.0

    @classmethod
    def from_env(cls) -> "TelegramNotifier | None":
        """Construit le notifieur depuis l'environnement, ou None si non configuré."""
        token = os.environ.get("QUANTTERM_TG_TOKEN", "").strip()
        chat_id = os.environ.get("QUANTTERM_TG_CHAT", "").strip()
        if not token or not chat_id:
            return None
        return cls(token, chat_id)

    def send(self, text: str) -> bool:
        """Envoie un message. Retourne True si Telegram a accepté, False sinon.

        N'émet jamais d'exception : une notif ratée ne doit pas casser la boucle
        de surveillance.
        """
        try:
            resp = requests.post(
                _API.format(token=self.token),
                data={"chat_id": self.chat_id, "text": text},
                timeout=self.timeout,
            )
            ok = resp.ok and resp.json().get("ok", False)
            if not ok:
                print(f"[telegram] échec envoi : {resp.status_code} {resp.text[:200]}")
            return bool(ok)
        except Exception as exc:  # réseau/API capricieux : on log, on continue
            print(f"[telegram] erreur : {exc}")
            return False
