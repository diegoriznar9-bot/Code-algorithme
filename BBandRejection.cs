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
    public class BBandRejection : Strategy
    {
        // ───────────────────────────────────────────
        // VARIABLES
        // ───────────────────────────────────────────
        private Bollinger bb;
        private bool tradeTakenThisSession;
        private DateTime lastSessionDate;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description                     = "BB Rejection Strategy — Entre sur rejet d'une bande extrême Bollinger. 1 seul trade par session.";
                Name                            = "BBandRejection";
                Calculate                       = Calculate.OnEachTick;
                EntriesPerDirection             = 1;
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
                BBPeriod                        = 20;
                BBStdDev                        = 2.0;

                // ── Risk Management ──
                StopLossPoints                  = 5;
                TakeProfitPoints                = 5;
                Quantity                        = 1;

                // ── Time Filter (Exchange Time = US Eastern pour MNQ/CME) ──
                // Paris 15:30:30 = New York 09:30:30 ET
                // Paris 15:35:00 = New York 09:35:00 ET
                StartHour                       = 9;
                StartMinute                     = 30;
                StartSecond                     = 30;
                EndHour                         = 9;
                EndMinute                       = 35;
                EndSecond                       = 0;
            }
            else if (State == State.Configure)
            {
                // SL et TP en ticks : 1 point MNQ = 4 ticks (tick size = 0.25)
                SetStopLoss(CalculationMode.Ticks, StopLossPoints * 4);
                SetProfitTarget(CalculationMode.Ticks, TakeProfitPoints * 4);
            }
            else if (State == State.DataLoaded)
            {
                bb = Bollinger(BBStdDev, BBPeriod);
                bb.Plots[0].Brush = Brushes.DodgerBlue;    // Upper Band
                bb.Plots[1].Brush = Brushes.Gray;           // Middle Band
                bb.Plots[2].Brush = Brushes.DodgerBlue;    // Lower Band
                AddChartIndicator(bb);

                tradeTakenThisSession = false;
                lastSessionDate       = DateTime.MinValue;
            }
        }

        protected override void OnBarUpdate()
        {
            // ── Attendre assez de barres pour le calcul BB ──
            if (CurrentBars[0] < BBPeriod)
                return;

            // ───────────────────────────────────────────
            // RESET DU FLAG "TRADE PRIS" À CHAQUE NOUVELLE SESSION
            // ───────────────────────────────────────────
            if (Bars.IsFirstBarOfSession || Time[0].Date != lastSessionDate)
            {
                tradeTakenThisSession = false;
                lastSessionDate       = Time[0].Date;
            }

            // ───────────────────────────────────────────
            // FILTRE HORAIRE
            // ───────────────────────────────────────────
            TimeSpan startTime   = new TimeSpan(StartHour, StartMinute, StartSecond);
            TimeSpan endTime     = new TimeSpan(EndHour, EndMinute, EndSecond);
            TimeSpan currentTime = Time[0].TimeOfDay;

            if (currentTime < startTime || currentTime > endTime)
                return;

            // ───────────────────────────────────────────
            // CONDITIONS DE BLOCAGE
            // ───────────────────────────────────────────
            // Un seul trade par session
            if (tradeTakenThisSession)
                return;

            // Pas de signal si déjà en position
            if (Position.MarketPosition != MarketPosition.Flat)
                return;

            // ───────────────────────────────────────────
            // DÉTECTION DU SIGNAL SUR BARRE COMPLÉTÉE
            // On attend le premier tick de la nouvelle barre
            // pour analyser la barre [1] qui vient de clôturer
            // ───────────────────────────────────────────
            if (!IsFirstTickOfBar)
                return;

            double upperBB  = bb.Upper[1];
            double lowerBB  = bb.Lower[1];
            double barHigh  = High[1];
            double barLow   = Low[1];
            double barClose = Close[1];
            double barOpen  = Open[1];

            // ───────────────────────────────────────────
            // LOGIQUE DE REJET
            //
            // Rejet Upper Band (signal SHORT) :
            //   - Le High a touché ou dépassé la bande supérieure
            //   - La bougie clôture EN DESSOUS de la bande supérieure
            //   - Confirmation : close < open (bougie baissière)
            //
            // Rejet Lower Band (signal LONG) :
            //   - Le Low a touché ou franchi la bande inférieure
            //   - La bougie clôture AU DESSUS de la bande inférieure
            //   - Confirmation : close > open (bougie haussière)
            // ───────────────────────────────────────────

            bool touchedUpper   = barHigh >= upperBB;
            bool rejectedUpper  = barClose < upperBB && barClose < barOpen;

            bool touchedLower   = barLow <= lowerBB;
            bool rejectedLower  = barClose > lowerBB && barClose > barOpen;

            // ── ENTRÉE SHORT : Rejet de la bande supérieure ──
            if (touchedUpper && rejectedUpper)
            {
                EnterShort(Quantity, "BBRej_Short");
                tradeTakenThisSession = true;

                if (TraceOrders)
                    Print(String.Format("{0} | SIGNAL SHORT — High={1} >= UpperBB={2}, Close={3} < UpperBB, Bearish candle",
                        Time[1], barHigh, upperBB, barClose));
            }
            // ── ENTRÉE LONG : Rejet de la bande inférieure ──
            else if (touchedLower && rejectedLower)
            {
                EnterLong(Quantity, "BBRej_Long");
                tradeTakenThisSession = true;

                if (TraceOrders)
                    Print(String.Format("{0} | SIGNAL LONG — Low={1} <= LowerBB={2}, Close={3} > LowerBB, Bullish candle",
                        Time[1], barLow, lowerBB, barClose));
            }
        }

        // ───────────────────────────────────────────
        // PARAMÈTRES EXPOSÉS DANS L'ANALYZER
        // Tous modifiables via Strategy Analyzer
        // ───────────────────────────────────────────

        #region Properties — Bollinger Bands

        [NinjaScriptProperty]
        [Range(2, int.MaxValue)]
        [Display(Name = "BB Period", Description = "Période de la moyenne mobile des Bollinger Bands",
            Order = 1, GroupName = "1. Bollinger Bands")]
        public int BBPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, 10.0)]
        [Display(Name = "BB Std Dev Multiplier", Description = "Multiplicateur d'écart-type pour les bandes",
            Order = 2, GroupName = "1. Bollinger Bands")]
        public double BBStdDev { get; set; }

        #endregion

        #region Properties — Risk Management

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "Stop Loss (Points)", Description = "Stop Loss en points (1 point = 4 ticks sur MNQ)",
            Order = 1, GroupName = "2. Risk Management")]
        public int StopLossPoints { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "Take Profit (Points)", Description = "Take Profit en points (1 point = 4 ticks sur MNQ)",
            Order = 2, GroupName = "2. Risk Management")]
        public int TakeProfitPoints { get; set; }

        [NinjaScriptProperty]
        [Range(1, 50)]
        [Display(Name = "Quantity", Description = "Nombre de contrats par entrée",
            Order = 3, GroupName = "2. Risk Management")]
        public int Quantity { get; set; }

        #endregion

        #region Properties — Time Filter

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "Start Hour", Description = "Heure de début (Exchange Time / US Eastern pour CME)",
            Order = 1, GroupName = "3. Time Filter")]
        public int StartHour { get; set; }

        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "Start Minute", Order = 2, GroupName = "3. Time Filter")]
        public int StartMinute { get; set; }

        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "Start Second", Order = 3, GroupName = "3. Time Filter")]
        public int StartSecond { get; set; }

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "End Hour", Description = "Heure de fin (Exchange Time / US Eastern pour CME)",
            Order = 4, GroupName = "3. Time Filter")]
        public int EndHour { get; set; }

        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "End Minute", Order = 5, GroupName = "3. Time Filter")]
        public int EndMinute { get; set; }

        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "End Second", Order = 6, GroupName = "3. Time Filter")]
        public int EndSecond { get; set; }

        #endregion
    }
}
