#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.SuperDom;
using NinjaTrader.Gui.Tools;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class BBandRejectionV07 : Strategy
    {
        // ───────────────────────────────────────────
        // VARIABLES
        // ───────────────────────────────────────────
        private Bollinger bb;
        private TimeZoneInfo parisTz;

        // État session
        private bool sessionActive;
        private bool cooldownActive;
        private bool setupReady;
        private bool inPosition;
        private bool scaleInDone;
        private bool sessionDone;

        // Cooldown
        private int barsWithoutContact;

        // Position tracking
        private bool entry1Active;
        private bool entry2Active;
        private int direction;           // 1 = long, -1 = short

        // Prix de gestion
        private double entry1Price;
        private double entry2Price;
        private double tp1Price;
        private double tp2Price;
        private double slPrice;

        // Anti-doublon : dernier bar traité pour entrée/cooldown
        private int lastBarProcessed;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description                     = "BB Rejection Open V07 — Cooldown + Scale-in + TP/SL manuels. Bougies 1000 volumes, OnEachTick. Filtre horaire heure de Paris.";
                Name                            = "BBandRejectionV07";
                Calculate                       = Calculate.OnEachTick;
                EntriesPerDirection             = 2;       // Entry1 + ScaleIn
                EntryHandling                   = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy    = true;
                ExitOnSessionCloseSeconds       = 30;
                IsFillLimitOnTouch              = false;
                MaximumBarsLookBack             = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution             = OrderFillResolution.Standard;
                Slippage                        = 0;
                StartBehavior                   = StartBehavior.WaitUntilFlat;
                TimeInForce                     = TimeInForce.Gtc;
                TraceOrders                     = false;
                RealtimeErrorHandling           = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling              = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade             = 20;

                // ── Bollinger Bands ──
                BandPeriod                      = 20;
                BandStdDev                      = 2.0;

                // ── Risk / Targets ──
                TP_Points                       = 30;
                SL_Points                       = 30;
                ScaleIn_Points                  = 15;

                // ── Cooldown ──
                CooldownBars                    = 5;

                // ── Time Filter (HEURE DE PARIS) ──
                // 15:30 Paris = 9:30 NY = US Open
                SessionStartHour                = 15;
                SessionStartMinute              = 30;
                SessionStartSecond              = 0;
                SessionEndHour                  = 15;
                SessionEndMinute                = 45;
                SessionEndSecond                = 0;

                // ── Quantity ──
                Quantity                        = 1;
            }
            else if (State == State.Configure)
            {
                // PAS de SetStopLoss / SetProfitTarget : gestion manuelle
                try
                {
                    parisTz = TimeZoneInfo.FindSystemTimeZoneById("Romance Standard Time");
                }
                catch (TimeZoneNotFoundException)
                {
                    parisTz = TimeZoneInfo.FindSystemTimeZoneById("Europe/Paris");
                }
            }
            else if (State == State.DataLoaded)
            {
                bb = Bollinger(BandStdDev, BandPeriod);
                bb.Plots[0].Brush = Brushes.DodgerBlue;
                bb.Plots[1].Brush = Brushes.Gray;
                bb.Plots[2].Brush = Brushes.DodgerBlue;
                AddChartIndicator(bb);

                ResetSession();
                lastBarProcessed = -1;
            }
        }

        private void ResetSession()
        {
            sessionActive       = false;
            cooldownActive      = false;
            setupReady          = false;
            inPosition          = false;
            scaleInDone         = false;
            sessionDone         = false;
            entry1Active        = false;
            entry2Active        = false;
            direction           = 0;
            barsWithoutContact  = 0;
            entry1Price         = 0;
            entry2Price         = 0;
            tp1Price            = 0;
            tp2Price            = 0;
            slPrice             = 0;
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBars[0] < BandPeriod)
                return;

            // ───────────────────────────────────────────
            // CONVERSION HEURE DE PARIS
            // ───────────────────────────────────────────
            DateTime barTimeParis = TimeZoneInfo.ConvertTime(
                Time[0],
                Bars.TradingHours.TimeZoneInfo,
                parisTz);

            TimeSpan currentTime = barTimeParis.TimeOfDay;
            TimeSpan sessionStart = new TimeSpan(SessionStartHour, SessionStartMinute, SessionStartSecond);
            TimeSpan sessionEnd   = new TimeSpan(SessionEndHour, SessionEndMinute, SessionEndSecond);

            // ───────────────────────────────────────────
            // ÉTAPE 1 : ACTIVATION / RESET SESSION
            // ───────────────────────────────────────────
            if (currentTime >= sessionStart && currentTime <= sessionEnd)
            {
                if (!sessionActive)
                {
                    ResetSession();
                    sessionActive      = true;
                    cooldownActive     = true;
                    barsWithoutContact = 0;
                }
            }
            else
            {
                if (sessionActive && !inPosition)
                {
                    sessionActive = false;
                    sessionDone   = true;
                }
                if (!inPosition)
                    return;
                // Si on est en position hors fenêtre, on continue la gestion TP/SL
            }

            // Si session terminée et plus en position → rien à faire
            if (sessionDone && !inPosition)
                return;

            // ───────────────────────────────────────────
            // GESTION DE POSITION (CHAQUE TICK)
            // ───────────────────────────────────────────
            if (inPosition)
            {
                double currentPrice = Close[0];

                // ── SL COMMUN ──
                bool slHit = (direction == 1 && currentPrice <= slPrice)
                          || (direction == -1 && currentPrice >= slPrice);

                if (slHit)
                {
                    if (direction == 1)
                    {
                        if (entry1Active) ExitLong("SL", "BBRej_Entry1");
                        if (entry2Active) ExitLong("SL", "BBRej_ScaleIn");
                    }
                    else
                    {
                        if (entry1Active) ExitShort("SL", "BBRej_Entry1");
                        if (entry2Active) ExitShort("SL", "BBRej_ScaleIn");
                    }

                    entry1Active = false;
                    entry2Active = false;
                    inPosition   = false;
                    sessionDone  = true;

                    if (TraceOrders)
                        Print(String.Format("{0} Paris | SL HIT @ {1}", barTimeParis, currentPrice));
                    return;
                }

                // ── SCALE-IN (avant check TP pour éviter trigger immédiat) ──
                if (!scaleInDone)
                {
                    bool scaleInTrigger = (direction == 1 && currentPrice <= entry1Price - ScaleIn_Points)
                                       || (direction == -1 && currentPrice >= entry1Price + ScaleIn_Points);

                    if (scaleInTrigger)
                    {
                        entry2Price = currentPrice;

                        if (direction == 1)
                        {
                            EnterLong(Quantity, "BBRej_ScaleIn");
                            tp1Price = entry2Price;
                            tp2Price = entry2Price + TP_Points;
                            slPrice  = entry2Price - SL_Points;
                        }
                        else
                        {
                            EnterShort(Quantity, "BBRej_ScaleIn");
                            tp1Price = entry2Price;
                            tp2Price = entry2Price - TP_Points;
                            slPrice  = entry2Price + SL_Points;
                        }

                        entry2Active = true;
                        scaleInDone  = true;

                        if (TraceOrders)
                            Print(String.Format("{0} Paris | SCALE-IN @ {1}, new TP1={2}, TP2={3}, SL={4}",
                                barTimeParis, entry2Price, tp1Price, tp2Price, slPrice));
                        return; // Skip TP checks this tick
                    }
                }

                // ── TP1 : ferme position 1 ──
                if (entry1Active)
                {
                    bool tp1Hit = (direction == 1 && currentPrice >= tp1Price)
                               || (direction == -1 && currentPrice <= tp1Price);

                    if (tp1Hit)
                    {
                        if (direction == 1)
                            ExitLong("TP1", "BBRej_Entry1");
                        else
                            ExitShort("TP1", "BBRej_Entry1");

                        entry1Active = false;

                        if (TraceOrders)
                            Print(String.Format("{0} Paris | TP1 HIT @ {1}", barTimeParis, currentPrice));

                        // Si pas de scale-in, c'était la seule position → fin
                        if (!entry2Active)
                        {
                            inPosition  = false;
                            sessionDone = true;
                            return;
                        }
                    }
                }

                // ── TP2 : ferme position 2 (ou unique si pas de scale-in avant TP1) ──
                if (entry2Active)
                {
                    bool tp2Hit = (direction == 1 && currentPrice >= tp2Price)
                               || (direction == -1 && currentPrice <= tp2Price);

                    if (tp2Hit)
                    {
                        if (direction == 1)
                            ExitLong("TP2", "BBRej_ScaleIn");
                        else
                            ExitShort("TP2", "BBRej_ScaleIn");

                        entry2Active = false;
                        inPosition   = false;
                        sessionDone  = true;

                        if (TraceOrders)
                            Print(String.Format("{0} Paris | TP2 HIT @ {1}", barTimeParis, currentPrice));
                        return;
                    }
                }

                return; // En position → pas de nouveau setup
            }

            // ───────────────────────────────────────────
            // LOGIQUE D'ENTRÉE (SUR CLÔTURE DE BOUGIE UNIQUEMENT)
            // IsFirstTickOfBar = la barre [1] vient de clôturer
            // ───────────────────────────────────────────
            if (!IsFirstTickOfBar || CurrentBar == lastBarProcessed)
                return;

            lastBarProcessed = CurrentBar;

            // ── ÉTAPE 2 : COOLDOWN ──
            if (cooldownActive)
            {
                bool barTouchedBand = High[1] >= bb.Upper[1] || Low[1] <= bb.Lower[1];

                if (barTouchedBand)
                    barsWithoutContact = 0;
                else
                    barsWithoutContact++;

                if (barsWithoutContact >= CooldownBars)
                {
                    cooldownActive = false;
                    setupReady     = true;

                    if (TraceOrders)
                        Print(String.Format("{0} Paris | COOLDOWN TERMINÉ — setup prêt", barTimeParis));
                }
                return; // Pendant cooldown, pas d'entrée
            }

            // ── ÉTAPE 3 : DÉTECTION DU SIGNAL ──
            if (!setupReady || sessionDone)
                return;

            double upperBB  = bb.Upper[1];
            double lowerBB  = bb.Lower[1];
            double barHigh  = High[1];
            double barLow   = Low[1];
            double barOpen  = Open[1];
            double barClose = Close[1];

            // CAS LONG : touche bande basse + clôture verte
            if (barLow <= lowerBB && barClose > barOpen)
            {
                entry1Price = barClose;
                tp1Price    = entry1Price + TP_Points;
                slPrice     = entry1Price - SL_Points;
                tp2Price    = double.MaxValue; // Pas encore défini

                EnterLong(Quantity, "BBRej_Entry1");
                direction    = 1;
                inPosition   = true;
                entry1Active = true;
                scaleInDone  = false;
                entry2Active = false;

                if (TraceOrders)
                    Print(String.Format("{0} Paris | ENTRY LONG @ {1}, TP1={2}, SL={3}",
                        barTimeParis, entry1Price, tp1Price, slPrice));
                return;
            }

            // CAS SHORT : touche bande haute + clôture rouge
            if (barHigh >= upperBB && barClose < barOpen)
            {
                entry1Price = barClose;
                tp1Price    = entry1Price - TP_Points;
                slPrice     = entry1Price + SL_Points;
                tp2Price    = double.MinValue; // Pas encore défini

                EnterShort(Quantity, "BBRej_Entry1");
                direction    = -1;
                inPosition   = true;
                entry1Active = true;
                scaleInDone  = false;
                entry2Active = false;

                if (TraceOrders)
                    Print(String.Format("{0} Paris | ENTRY SHORT @ {1}, TP1={2}, SL={3}",
                        barTimeParis, entry1Price, tp1Price, slPrice));
                return;
            }
        }

        // ───────────────────────────────────────────
        // PARAMÈTRES — STRATEGY ANALYZER
        // ───────────────────────────────────────────

        #region Properties — Bollinger Bands

        [NinjaScriptProperty]
        [Range(2, int.MaxValue)]
        [Display(Name = "Band Period", Description = "Période Bollinger Bands",
            Order = 1, GroupName = "1. Bollinger Bands")]
        public int BandPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, 10.0)]
        [Display(Name = "Band Std Dev", Description = "Multiplicateur écart-type",
            Order = 2, GroupName = "1. Bollinger Bands")]
        public double BandStdDev { get; set; }

        #endregion

        #region Properties — Risk Management

        [NinjaScriptProperty]
        [Range(1, 200)]
        [Display(Name = "TP (Points)", Description = "Take Profit en points. Défaut = 30",
            Order = 1, GroupName = "2. Risk Management")]
        public int TP_Points { get; set; }

        [NinjaScriptProperty]
        [Range(1, 200)]
        [Display(Name = "SL (Points)", Description = "Stop Loss en points. Défaut = 30",
            Order = 2, GroupName = "2. Risk Management")]
        public int SL_Points { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "Scale-In (Points)", Description = "Seuil de perte pour déclencher le scale-in. Défaut = 15",
            Order = 3, GroupName = "2. Risk Management")]
        public int ScaleIn_Points { get; set; }

        [NinjaScriptProperty]
        [Range(1, 50)]
        [Display(Name = "Quantity", Description = "Contrats par entrée",
            Order = 4, GroupName = "2. Risk Management")]
        public int Quantity { get; set; }

        #endregion

        #region Properties — Cooldown

        [NinjaScriptProperty]
        [Range(0, 50)]
        [Display(Name = "Cooldown Bars", Description = "Nombre de bougies consécutives sans contact bande requis avant setup",
            Order = 1, GroupName = "3. Cooldown")]
        public int CooldownBars { get; set; }

        #endregion

        #region Properties — Time Filter (Heure de Paris)

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "Session Start Hour (Paris)", Order = 1, GroupName = "4. Time Filter (Paris)")]
        public int SessionStartHour { get; set; }

        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "Session Start Minute (Paris)", Order = 2, GroupName = "4. Time Filter (Paris)")]
        public int SessionStartMinute { get; set; }

        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "Session Start Second (Paris)", Order = 3, GroupName = "4. Time Filter (Paris)")]
        public int SessionStartSecond { get; set; }

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "Session End Hour (Paris)", Order = 4, GroupName = "4. Time Filter (Paris)")]
        public int SessionEndHour { get; set; }

        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "Session End Minute (Paris)", Order = 5, GroupName = "4. Time Filter (Paris)")]
        public int SessionEndMinute { get; set; }

        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "Session End Second (Paris)", Order = 6, GroupName = "4. Time Filter (Paris)")]
        public int SessionEndSecond { get; set; }

        #endregion
    }
}
