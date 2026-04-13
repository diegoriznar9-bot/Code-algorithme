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
    public class BBandRejectionV03 : Strategy
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
                Description                     = "BB Rejection — Entre sur rejet confirmé d'une bande extrême Bollinger. TP sur touche de la bande opposée à la clôture. 1 seul trade par session.";
                Name                            = "BBandRejectionV03";
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
                StopLossPoints                  = 30;
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
                // SL fixe en ticks : 1 point MNQ = 4 ticks (tick size = 0.25)
                // PAS de SetProfitTarget — le TP est géré manuellement (bande opposée)
                SetStopLoss(CalculationMode.Ticks, StopLossPoints * 4);
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
            // RESET SESSION
            // ───────────────────────────────────────────
            if (Bars.IsFirstBarOfSession || Time[0].Date != lastSessionDate)
            {
                tradeTakenThisSession = false;
                lastSessionDate       = Time[0].Date;
            }

            // ───────────────────────────────────────────
            // ON TRAVAILLE SUR LA BARRE COMPLÉTÉE [1]
            // On attend le premier tick de la nouvelle barre
            // ───────────────────────────────────────────
            if (!IsFirstTickOfBar)
                return;

            // ───────────────────────────────────────────
            // 1. GESTION DU TP — BANDE OPPOSÉE
            //
            // LONG  → la barre [1] a touché la bande supérieure ?
            //         OUI → on clôture au market (= au plus proche
            //         du close de [1])
            //
            // SHORT → la barre [1] a touché la bande inférieure ?
            //         OUI → on clôture au market
            // ───────────────────────────────────────────
            if (Position.MarketPosition == MarketPosition.Long)
            {
                if (High[1] >= bb.Upper[1])
                {
                    ExitLong("TP_OppBand", "BBRej_Long");
                    if (TraceOrders)
                        Print(String.Format("{0} | EXIT LONG — High[1]={1} touché UpperBB={2}",
                            Time[1], High[1], bb.Upper[1]));
                }
                return; // En position → pas de nouveau signal
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                if (Low[1] <= bb.Lower[1])
                {
                    ExitShort("TP_OppBand", "BBRej_Short");
                    if (TraceOrders)
                        Print(String.Format("{0} | EXIT SHORT — Low[1]={1} touché LowerBB={2}",
                            Time[1], Low[1], bb.Lower[1]));
                }
                return; // En position → pas de nouveau signal
            }

            // ───────────────────────────────────────────
            // 2. FILTRE HORAIRE (entrées uniquement)
            // ───────────────────────────────────────────
            TimeSpan startTime   = new TimeSpan(StartHour, StartMinute, StartSecond);
            TimeSpan endTime     = new TimeSpan(EndHour, EndMinute, EndSecond);
            TimeSpan currentTime = Time[0].TimeOfDay;

            if (currentTime < startTime || currentTime > endTime)
                return;

            // ───────────────────────────────────────────
            // 3. BLOCAGE : 1 SEUL TRADE PAR SESSION
            // ───────────────────────────────────────────
            if (tradeTakenThisSession)
                return;

            // ───────────────────────────────────────────
            // 4. LOGIQUE D'ENTRÉE — BARRE COMPLÉTÉE [1]
            //
            // ÉTAPE 1 : La bougie [1] a-t-elle TOUCHÉ une bande ?
            //   → Non → on ne fait rien
            //   → Oui → étape 2
            //
            // ÉTAPE 2 : Dominance de mèche
            //   wickHigh = High[1] - Max(Open[1], Close[1])
            //   wickLow  = Min(Open[1], Close[1]) - Low[1]
            //
            //   Rejet Lower Band → signal LONG :
            //     Touche :  Low[1]  <= LowerBB[1]
            //     Rejet  :  wickLow > wickHigh  (mèche basse dominante)
            //     → ACHAT
            //
            //   Rejet Upper Band → signal SHORT :
            //     Touche :  High[1] >= UpperBB[1]
            //     Rejet  :  wickHigh > wickLow  (mèche haute dominante)
            //     → VENTE
            // ───────────────────────────────────────────

            double upperBB  = bb.Upper[1];
            double lowerBB  = bb.Lower[1];
            double barHigh  = High[1];
            double barLow   = Low[1];
            double barOpen  = Open[1];
            double barClose = Close[1];

            double wickHigh = barHigh - Math.Max(barOpen, barClose);
            double wickLow  = Math.Min(barOpen, barClose) - barLow;

            // ── SIGNAL LONG : Touche lower + mèche basse dominante ──
            if (barLow <= lowerBB && wickLow > wickHigh)
            {
                EnterLong(Quantity, "BBRej_Long");
                tradeTakenThisSession = true;

                if (TraceOrders)
                    Print(String.Format("{0} | SIGNAL LONG — Low={1} <= LowerBB={2}, wickLow={3:F2} > wickHigh={4:F2}",
                        Time[1], barLow, lowerBB, wickLow, wickHigh));
                return;
            }

            // ── SIGNAL SHORT : Touche upper + mèche haute dominante ──
            if (barHigh >= upperBB && wickHigh > wickLow)
            {
                EnterShort(Quantity, "BBRej_Short");
                tradeTakenThisSession = true;

                if (TraceOrders)
                    Print(String.Format("{0} | SIGNAL SHORT — High={1} >= UpperBB={2}, wickHigh={3:F2} > wickLow={4:F2}",
                        Time[1], barHigh, upperBB, wickHigh, wickLow));
                return;
            }
        }

        // ───────────────────────────────────────────
        // PARAMÈTRES — STRATEGY ANALYZER
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
        [Range(1, 200)]
        [Display(Name = "Stop Loss (Points)", Description = "Stop Loss en points (1 pt = 4 ticks MNQ). Défaut = 30 pts",
            Order = 1, GroupName = "2. Risk Management")]
        public int StopLossPoints { get; set; }

        [NinjaScriptProperty]
        [Range(1, 50)]
        [Display(Name = "Quantity", Description = "Nombre de contrats par entrée",
            Order = 2, GroupName = "2. Risk Management")]
        public int Quantity { get; set; }

        #endregion

        #region Properties — Time Filter

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "Start Hour", Description = "Heure de début (Exchange Time / US Eastern)",
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
        [Display(Name = "End Hour", Description = "Heure de fin (Exchange Time / US Eastern)",
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
