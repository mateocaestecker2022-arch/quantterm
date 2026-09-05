#!/bin/bash
# mt5_keeper.sh — maintient les 3 terminaux MT5 vivants sur le VPS.
#
# CONTEXTE (VPS IONOS, infra existante, RIEN à voir avec le code QuantTerm) :
# les services systemd mt5/mt5b/mt5c sont bogués — le lanceur MT5 DÉTACHE le vrai
# terminal, donc le service croit qu'il est mort et entre en boucle de redémarrage
# qui tue les terminaux non encore "échappés". En attendant un vrai correctif des
# services, ce keeper lance/relance les terminaux EN DÉTACHÉ (hors cgroup de service),
# donc rien ne peut les tuer, et les relance s'ils tombent.
#
# À appeler via cron :   */2 * * * *   +   @reboot sleep 60
# Suppose que les écrans Xvfb (:99, :100) et x11vnc tournent (services enabled).

set -u

launch_if_dead() {
  local prefix="$1" script="$2" p
  for p in $(pgrep -f terminal64.exe 2>/dev/null); do
    if grep -qz "WINEPREFIX=$prefix" "/proc/$p/environ" 2>/dev/null; then
      return 0   # terminal déjà vivant pour ce prefix
    fi
  done
  # Pas de terminal pour ce prefix -> on relance SON script, détaché (setsid+nohup).
  runuser -u mt5 -- setsid bash -c "nohup '$script' >/dev/null 2>&1 </dev/null &"
  logger -t mt5keeper "relance $script (prefix $prefix etait mort)"
  sleep 20   # laisse le terminal s'établir avant de tester le suivant
}

launch_if_dead /opt/mt5/wineprefix  /opt/mt5/start_mt5.sh
launch_if_dead /opt/mt5b/wineprefix /opt/mt5b/start_mt5.sh
launch_if_dead /opt/mt5c/wineprefix /opt/mt5c/start_mt5c.sh
