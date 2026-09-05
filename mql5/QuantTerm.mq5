//+------------------------------------------------------------------+
//|  QuantTerm.mq5                                                    |
//|  Expert Advisor — portage fidèle des stratégies QuantTerm.       |
//|                                                                  |
//|  Deux modes (un EA, deux graphiques) :                           |
//|    MOMENTUM_ICHIMOKU  -> or (XAUUSD)  : Ichimoku 20/60/120,       |
//|                          SL k_stop ATR + TP k_target ATR.         |
//|    MEANREV_RSI        -> nasdaq (NAS100) : RSI 25/75 fade,        |
//|                          SL protectif, sortie au RETOUR MOYENNE.  |
//|                                                                  |
//|  Sizing : risque fixe (1% du capital) via valeur du tick broker. |
//|  Décision sur BARRE CLÔTURÉE (shift 1), entrée sur TRANSITION     |
//|  (pas de ré-entrée en boucle après un stop). DryRun par défaut.   |
//|  Magic dédié (770077) : ne touche pas aux autres EA.             |
//|                                                                  |
//|  ⚠ Démo. Edge mesuré sur GC=F/NQ=F (futures) ; XAUUSD/NAS100      |
//|  (broker) sont corrélés mais différents -> à confirmer sur ce     |
//|  feed avant tout réel.                                            |
//+------------------------------------------------------------------+
#property copyright "QuantTerm"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

enum StrategyMode
  {
   MOMENTUM_ICHIMOKU = 0,   // Or : suivi de tendance Ichimoku
   MEANREV_RSI       = 1    // Nasdaq : mean-reversion RSI
  };

input StrategyMode Mode        = MOMENTUM_ICHIMOKU; // Stratégie (selon le graphique)
input double       RiskPct     = 1.0;   // Risque par trade (% du capital)
input double       KStop       = 2.0;   // Stop en multiples d'ATR
input double       KTarget     = 3.0;   // Target en ATR (momentum uniquement)
input int          ATRPeriod   = 14;    // Période ATR
// -- Ichimoku (momentum) --
input int          Tenkan      = 20;    // Tenkan
input int          Kijun       = 60;    // Kijun (= décalage des spans)
input int          SenkouB     = 120;   // Senkou B
// -- RSI (mean-reversion) --
input int          RSIPeriod   = 14;    // Période RSI
input double       RSILow      = 25.0;  // Seuil survente (long)
input double       RSIHigh     = 75.0;  // Seuil surachat (short)
input double       RSIMid      = 50.0;  // Médiane (sortie mean-rev)
// -- Exécution --
input long         Magic       = 770077; // Magic number dédié
input double       MaxLot      = 0.0;    // Plafond de lot (0 = désactivé)
input int          Slippage    = 20;     // Déviation max (points)
input bool         DryRun      = true;   // true = LOGGE sans envoyer d'ordre

CTrade         trade;
int            atrHandle = INVALID_HANDLE;
int            rsiHandle = INVALID_HANDLE;
datetime       lastBar   = 0;
const int      NO_EVENT  = -100;         // marqueur "pas d'événement" (ffill)

//+------------------------------------------------------------------+
int OnInit()
  {
   trade.SetExpertMagicNumber(Magic);
   trade.SetDeviationInPoints(Slippage);
   trade.SetTypeFillingBySymbol(_Symbol);

   atrHandle = iATR(_Symbol, _Period, ATRPeriod);
   if(atrHandle == INVALID_HANDLE)
     { Print("iATR échec"); return(INIT_FAILED); }

   if(Mode == MEANREV_RSI)
     {
      rsiHandle = iRSI(_Symbol, _Period, RSIPeriod, PRICE_CLOSE);
      if(rsiHandle == INVALID_HANDLE)
        { Print("iRSI échec"); return(INIT_FAILED); }
     }

   PrintFormat("QuantTerm démarré — %s mode=%s risque=%.2f%% magic=%d DryRun=%s",
               _Symbol, (Mode==MOMENTUM_ICHIMOKU?"ICHIMOKU":"RSI_MEANREV"),
               RiskPct, (int)Magic, (DryRun?"OUI":"NON"));
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   if(atrHandle != INVALID_HANDLE) IndicatorRelease(atrHandle);
   if(rsiHandle != INVALID_HANDLE) IndicatorRelease(rsiHandle);
  }

//+------------------------------------------------------------------+
//| Utilitaires min/max sur tableau série                            |
//+------------------------------------------------------------------+
double HighestVal(const double &a[], int start, int count)
  {
   double m = a[start];
   for(int i = start + 1; i < start + count; i++) if(a[i] > m) m = a[i];
   return m;
  }
double LowestVal(const double &a[], int start, int count)
  {
   double m = a[start];
   for(int i = start + 1; i < start + count; i++) if(a[i] < m) m = a[i];
   return m;
  }

//+------------------------------------------------------------------+
//| Direction Ichimoku instantanée à la barre `s` (série).           |
//| Reproduit quantterm : span_*[t] projeté de Kijun -> calc à t-Kijun|
//| Renvoie 1 / -1, ou NO_EVENT si aucune condition (=> ffill).      |
//+------------------------------------------------------------------+
int IchimokuDirAt(int s, const double &H[], const double &L[], const double &C[])
  {
   double conv = (HighestVal(H, s, Tenkan)       + LowestVal(L, s, Tenkan))       / 2.0;
   double base = (HighestVal(H, s, Kijun)        + LowestVal(L, s, Kijun))        / 2.0;
   int sp = s + Kijun;   // les spans au temps s sont calculés Kijun barres plus tôt
   double convP = (HighestVal(H, sp, Tenkan)     + LowestVal(L, sp, Tenkan))     / 2.0;
   double baseP = (HighestVal(H, sp, Kijun)      + LowestVal(L, sp, Kijun))      / 2.0;
   double spanA = (convP + baseP) / 2.0;
   double spanB = (HighestVal(H, sp, SenkouB)    + LowestVal(L, sp, SenkouB))    / 2.0;
   double top = MathMax(spanA, spanB);
   double bot = MathMin(spanA, spanB);
   double c   = C[s];
   if(conv > base && c > top) return 1;
   if(conv < base && c < bot) return -1;
   return NO_EVENT;
  }

//+------------------------------------------------------------------+
//| Événement RSI mean-rev à la barre `s`. 1/-1 = fade, 0 = sortie   |
//| (retour à la moyenne), NO_EVENT = ffill.                         |
//+------------------------------------------------------------------+
int RsiEventAt(int s, const double &R[])
  {
   double r1 = R[s], r2 = R[s + 1];
   if(r1 < RSILow)  return 1;
   if(r1 > RSIHigh) return -1;
   if(r2 <  RSIMid && r1 >= RSIMid) return 0;  // croise la médiane vers le haut
   if(r2 >  RSIMid && r1 <= RSIMid) return 0;  // ... vers le bas
   return NO_EVENT;
  }

//+------------------------------------------------------------------+
//| État ffill à la barre `s` : remonte jusqu'au 1er événement.      |
//+------------------------------------------------------------------+
int StateAt(int s, const double &H[], const double &L[], const double &C[],
            const double &R[], int lookback)
  {
   for(int k = 0; k < lookback; k++)
     {
      int e = (Mode == MOMENTUM_ICHIMOKU) ? IchimokuDirAt(s + k, H, L, C)
                                          : RsiEventAt(s + k, R);
      if(e != NO_EVENT) return e;   // 1, -1 ou 0
     }
   return 0;
  }

//+------------------------------------------------------------------+
//| Lot en risque fixe (identique à broker_mt5.compute_lot).         |
//+------------------------------------------------------------------+
double ComputeLot(double stopDist)
  {
   double bal      = AccountInfoDouble(ACCOUNT_BALANCE);
   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double vmin     = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vstep    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmax     = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(stopDist <= 0 || tickSize <= 0 || tickVal <= 0 || vstep <= 0 || bal <= 0)
      return 0.0;
   double riskMoney  = bal * RiskPct / 100.0;
   double lossPerLot = (stopDist / tickSize) * tickVal;
   if(lossPerLot <= 0) return 0.0;
   double lot = MathFloor((riskMoney / lossPerLot) / vstep) * vstep;
   if(MaxLot > 0) lot = MathMin(lot, MaxLot);
   lot = MathMin(lot, vmax);
   if(lot < vmin) return 0.0;
   int digits = (int)MathCeil(-MathLog10(vstep));
   return NormalizeDouble(lot, MathMax(digits, 0));
  }

//+------------------------------------------------------------------+
//| Position ouverte par CET EA sur ce symbole ? (filtrée par magic) |
//| Renvoie 1 (long) / -1 (short) / 0 (aucune).                      |
//+------------------------------------------------------------------+
int CurrentPosDir()
  {
   if(!PositionSelect(_Symbol)) return 0;
   if(PositionGetInteger(POSITION_MAGIC) != Magic) return 0;
   return (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
  }

//+------------------------------------------------------------------+
//| Ouvre une position (ou logge en DryRun).                         |
//+------------------------------------------------------------------+
void OpenTrade(int dir, double atr)
  {
   double stopDist = KStop * atr;
   double lot = ComputeLot(stopDist);
   if(lot <= 0)
     { PrintFormat("%s SKIP: lot<volume_min (risque trop petit)", _Symbol); return; }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double entry = (dir == 1) ? ask : bid;
   double sl = entry - dir * stopDist;
   double tp = (Mode == MOMENTUM_ICHIMOKU) ? entry + dir * KTarget * atr : 0.0;

   // Respecte la distance minimale de stop du broker.
   double minDist = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   if(minDist > 0 && MathAbs(entry - sl) < minDist)
      sl = entry - dir * minDist;

   string sens = (dir == 1) ? "LONG" : "SHORT";
   if(DryRun)
     {
      PrintFormat("%s [DRY-RUN] OPEN %s %.2f lot @ %.2f SL %.2f TP %.2f",
                  _Symbol, sens, lot, entry, sl, tp);
      return;
     }
   bool ok = (dir == 1) ? trade.Buy(lot, _Symbol, 0.0, sl, tp, "quantterm")
                        : trade.Sell(lot, _Symbol, 0.0, sl, tp, "quantterm");
   PrintFormat("%s OPEN %s %.2f lot SL %.2f TP %.2f -> %s (ret %d)",
               _Symbol, sens, lot, sl, tp, (ok?"OK":"REJET"), trade.ResultRetcode());
  }

void CloseTrade(string why)
  {
   if(DryRun) { PrintFormat("%s [DRY-RUN] CLOSE (%s)", _Symbol, why); return; }
   bool ok = trade.PositionClose(_Symbol);
   PrintFormat("%s CLOSE (%s) -> %s (ret %d)", _Symbol, why,
               (ok?"OK":"REJET"), trade.ResultRetcode());
  }

//+------------------------------------------------------------------+
//| Boucle principale : décision une fois par barre clôturée.        |
//+------------------------------------------------------------------+
void OnTick()
  {
   datetime t = iTime(_Symbol, _Period, 0);
   if(t == lastBar) return;    // on n'agit qu'à l'ouverture d'une nouvelle barre
   lastBar = t;

   int need = SenkouB + Kijun + 20;
   if(Bars(_Symbol, _Period) < need + 3) return;

   // ATR de la dernière barre clôturée (shift 1).
   double atrBuf[]; ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(atrHandle, 0, 1, 1, atrBuf) < 1) return;
   double atr = atrBuf[0];
   if(atr <= 0) return;

   // Séries de prix / RSI (indexées série : 0 = barre courante).
   double H[], L[], C[], R[];
   ArraySetAsSeries(H, true); ArraySetAsSeries(L, true);
   ArraySetAsSeries(C, true); ArraySetAsSeries(R, true);
   if(CopyHigh(_Symbol, _Period, 0, need + 3, H)  < need) return;
   if(CopyLow(_Symbol, _Period, 0, need + 3, L)   < need) return;
   if(CopyClose(_Symbol, _Period, 0, need + 3, C) < need) return;
   if(Mode == MEANREV_RSI)
      if(CopyBuffer(rsiHandle, 0, 0, need + 3, R) < need) return;

   int lookback = need;
   int stateNow  = StateAt(1, H, L, C, R, lookback);   // barre clôturée
   int statePrev = StateAt(2, H, L, C, R, lookback);   // barre précédente
   bool fresh = (stateNow != statePrev);

   int posDir = CurrentPosDir();

   if(!fresh)
     {
      // Rien de neuf : SL/TP (momentum) gèrent la sortie ; mean-rev tient.
      return;
     }

   // Transition détectée.
   if(stateNow == 0)
     {
      if(posDir != 0) CloseTrade("retour à la moyenne (FLAT)");
      return;
     }

   // stateNow = +1 ou -1
   if(posDir == stateNow) return;             // déjà dans le bon sens
   if(posDir == -stateNow) CloseTrade("signal inverse frais");
   OpenTrade(stateNow, atr);
  }
//+------------------------------------------------------------------+
