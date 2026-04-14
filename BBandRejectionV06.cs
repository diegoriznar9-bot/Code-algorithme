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
    public class BBandRejectionV06 : Strategy
    {
        // ───────────────────────────────────────────
        // VARIABLES
        // ───────────────────────────────────────────
        private Bollinger bb;
        private bool tradeTakenThisSession;
        private DateTime lastSessionDate;
        private TimeZoneInfo parisTz;     // Europe/Paris (CET/CEST)

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description                     = "BB Rejection — Filtre horaire en HEURE DE PARIS (CET/CEST). Robuste : fonctionne peu importe le fuseau du PC, du chart ou du template de session. Défaut 15h30:30 → 15h35 Paris = NY open.";
                Name                            = "BBandRejectionV06";
                Calculate                       = Calculate.OnBarClose;
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

                // ── Time Filter (EXPRIMÉ EN HEURE DE PARIS) ──
                // 15:30 Paris (hiver CET ou été CEST) = 9:30 NY (EST ou EDT)
                StartHour                       = 15;
                StartMinute                     = 30;
                StartSecond                     = 30;
                EndHour                         = 15;
                EndMinute                       = 35;
                EndSecond                       = 0;
            }
            else if (State == State.Configure)
            {
                // SL fixe en ticks : 1 point MNQ = 4 ticks (tick size = 0.25)
                SetStopLoss(CalculationMode.Ticks, StopLossPoints * 4);

                // Fuseau Paris (gère automatiquement CET ↔ CEST)
                // "Romance Standard Time" sur Windows / "Europe/Paris" sur Linux
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
            // CONVERSION DE Time[0] EN HEURE DE PARIS
            //
            // Time[0] est dans le fuseau de la session de l'instrument
            // (Bars.TradingHours.TimeZoneInfo). On le convertit
            // explicitement en heure de Paris → le filtre horaire
            // fonctionne quelque soit :
            //   - le fuseau du PC qui héberge la stratégie
            //   - le fuseau d'affichage du chart
            //   - le template de session utilisé
            // Gestion automatique CET (hiver) ↔ CEST (été).
            // ───────────────────────────────────────────
            DateTime barTimeParis = TimeZoneInfo.ConvertTime(
                Time[0],
                Bars.TradingHours.TimeZoneInfo,
                parisTz);

            // ───────────────────────────────────────────
            // RESET SESSION (basé sur la date Paris)
            // ───────────────────────────────────────────
            if (Bars.IsFirstBarOfSession || barTimeParis.Date != lastSessionDate)
            {
                tradeTakenThisSession = false;
                lastSessionDate       = barTimeParis.Date;
            }

            // ───────────────────────────────────────────
            // 1. GESTION DU TP — BANDE OPPOSÉE
            // ───────────────────────────────────────────
            if (Position.MarketPosition == MarketPosition.Long)
            {
                if (High[0] >= bb.Upper[0])
                {
                    ExitLong("TP_OppBand", "BBRej_Long");
                    if (TraceOrders)
                        Print(String.Format("{0} Paris | EXIT LONG — High[0]={1} touché UpperBB={2}",
                            barTimeParis, High[0], bb.Upper[0]));
                }
                return;
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                if (Low[0] <= bb.Lower[0])
                {
                    ExitShort("TP_OppBand", "BBRej_Short");
                    if (TraceOrders)
                        Print(String.Format("{0} Paris | EXIT SHORT — Low[0]={1} touché LowerBB={2}",
                            barTimeParis, Low[0], bb.Lower[0]));
                }
                return;
            }

            // ───────────────────────────────────────────
            // 2. FILTRE HORAIRE (HEURE DE PARIS)
            // ───────────────────────────────────────────
            TimeSpan startTime   = new TimeSpan(StartHour, StartMinute, StartSecond);
            TimeSpan endTime     = new TimeSpan(EndHour, EndMinute, EndSecond);
            TimeSpan currentTime = barTimeParis.TimeOfDay;

            if (currentTime < startTime || currentTime > endTime)
                return;

            // ───────────────────────────────────────────
            // 3. BLOCAGE : 1 SEUL TRADE PAR SESSION
            // ───────────────────────────────────────────
            if (tradeTakenThisSession)
                return;

            // ───────────────────────────────────────────
            // 4. LOGIQUE D'ENTRÉE — BARRE QUI VIENT DE CLÔTURER [0]
            //
            // Dominance de mèche :
            //   wickHigh = High[0] - Max(Open[0], Close[0])
            //   wickLow  = Min(Open[0], Close[0]) - Low[0]
            //
            //   LONG  : Low[0]  <= LowerBB[0] && wickLow  > wickHigh
            //   SHORT : High[0] >= UpperBB[0] && wickHigh > wickLow
            // ───────────────────────────────────────────
            double upperBB  = bb.Upper[0];
            double lowerBB  = bb.Lower[0];
            double barHigh  = High[0];
            double barLow   = Low[0];
            double barOpen  = Open[0];
            double barClose = Close[0];

            double wickHigh = barHigh - Math.Max(barOpen, barClose);
            double wickLow  = Math.Min(barOpen, barClose) - barLow;

            // ── SIGNAL LONG ──
            if (barLow <= lowerBB && wickLow > wickHigh)
            {
                EnterLong(Quantity, "BBRej_Long");
                tradeTakenThisSession = true;

                if (TraceOrders)
                    Print(String.Format("{0} Paris | SIGNAL LONG — Low={1} <= LowerBB={2}, wickLow={3:F2} > wickHigh={4:F2}",
                        barTimeParis, barLow, lowerBB, wickLow, wickHigh));
                return;
            }

            // ── SIGNAL SHORT ──
            if (barHigh >= upperBB && wickHigh > wickLow)
            {
                EnterShort(Quantity, "BBRej_Short");
                tradeTakenThisSession = true;

                if (TraceOrders)
                    Print(String.Format("{0} Paris | SIGNAL SHORT — High={1} >= UpperBB={2}, wickHigh={3:F2} > wickLow={4:F2}",
                        barTimeParis, barHigh, upperBB, wickHigh, wickLow));
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

        #region Properties — Time Filter (Heure de Paris)

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "Start Hour (Paris)", Description = "Heure de début en heure de Paris (CET/CEST). 15 = 15h Paris = NY open",
            Order = 1, GroupName = "3. Time Filter (Paris)")]
        public int StartHour { get; set; }

        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "Start Minute (Paris)", Order = 2, GroupName = "3. Time Filter (Paris)")]
        public int StartMinute { get; set; }

        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "Start Second (Paris)", Order = 3, GroupName = "3. Time Filter (Paris)")]
        public int StartSecond { get; set; }

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "End Hour (Paris)", Description = "Heure de fin en heure de Paris (CET/CEST)",
            Order = 4, GroupName = "3. Time Filter (Paris)")]
        public int EndHour { get; set; }

        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "End Minute (Paris)", Order = 5, GroupName = "3. Time Filter (Paris)")]
        public int EndMinute { get; set; }

        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "End Second (Paris)", Order = 6, GroupName = "3. Time Filter (Paris)")]
        public int EndSecond { get; set; }

        #endregion
    }
}
