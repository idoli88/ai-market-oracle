import pandas as pd
import ta
import os
from datetime import datetime
from pathlib import Path
from typing import Dict
from oracle.logger import setup_logger

logger = setup_logger(__name__)

class TechnicalAnalyst:
    def process(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """
        Apply technical indicators to the dataframes.
        
        Args:
            data_map (Dict[str, pd.DataFrame]): Dictionary of ticker data.
            
        Returns:
            Dict[str, pd.DataFrame]: Dictionary with added indicators.
        """
        processed_data = {}
        logger.info("Starting technical analysis processing")
        
        for ticker, df in data_map.items():
            if df.empty or len(df) < 50:
                logger.warning(f"Skipping {ticker}: Not enough data for analysis (rows={len(df)})")
                continue
                
            # Create a copy to avoid SettingWithCopy warnings
            df = df.copy()
            
            # Ensure 'Close' is available.
            column_names = [str(c).lower() for c in df.columns]
            if 'close' not in column_names and 'Close' not in df.columns:
                 logger.error(f"Missing 'Close' column for {ticker}. Columns: {df.columns}")
                 continue

            try:
                # Ensure Close is a Series (handle potential DataFrame from yfinance)
                close_series = df['Close'] if 'Close' in df.columns else df['close']
                if isinstance(close_series, pd.DataFrame):
                    close_series = close_series.squeeze()

                # Add RSI (14)
                df['RSI'] = ta.momentum.RSIIndicator(close=close_series, window=14).rsi()
                
                # Add EMA (50) - Short/Medium term trend
                df['EMA_50'] = ta.trend.EMAIndicator(close=close_series, window=50).ema_indicator()
                
                # Add EMA (200) - Long term trend
                df['EMA_200'] = ta.trend.EMAIndicator(close=close_series, window=200).ema_indicator()
                
                processed_data[ticker] = df
                logger.debug(f"Calculated indicators for {ticker}")
            except Exception as e:
                logger.error(f"Error calculating indicators for {ticker}: {e}", exc_info=True)
                
        return processed_data

    def summarize_last_state(self, processed_data: Dict[str, pd.DataFrame]) -> str:
        """
        Create a text summary of the latest technical state for the LLM.
        """
        summary_lines = []
        for ticker, df in processed_data.items():
            try:
                last_row = df.iloc[-1]
                
                # extract scalar values safely
                close_val = self._get_scalar(last_row.get('Close', last_row.get('close')))
                rsi_val = self._get_scalar(last_row.get('RSI'))
                ema50_val = self._get_scalar(last_row.get('EMA_50'))
                ema200_val = self._get_scalar(last_row.get('EMA_200'))
                
                summary_lines.append(f"--- {ticker} ---")
                summary_lines.append(f"Price: {close_val:.2f}")
                summary_lines.append(f"RSI (14): {rsi_val:.2f}")
                summary_lines.append(f"EMA (50): {ema50_val:.2f}")
                summary_lines.append(f"EMA (200): {ema200_val:.2f}")
                
                # Simple trend context
                trend = "Bullish" if close_val > ema200_val else "Bearish"
                summary_lines.append(f"Trend (vs EMA200): {trend}")
                
                summary_lines.append("") # Empty line separator
            except Exception as e:
                logger.error(f"Error summarizing {ticker}: {e}")

        return "\n".join(summary_lines)

    def _get_scalar(self, val):
        if isinstance(val, pd.Series):
            return val.iloc[0]
        return val

    def generate_html_report(self, processed_data: Dict[str, pd.DataFrame]) -> str:
        """
        Generate a simple HTML report of the latest data and save it locally.
        
        Returns:
            str: Path to the generated report.
        """
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = reports_dir / f"oracle_report_{timestamp}.html"
        
        html_content = f"""
        <html>
        <head>
            <title>Oracle Report - {timestamp}</title>
            <style>
                body {{ font-family: sans-serif; margin: 20px; }}
                h1 {{ color: #2c3e50; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .bullish {{ color: green; font-weight: bold; }}
                .bearish {{ color: red; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>Oracle Market Report ({timestamp})</h1>
        """
        
        for ticker, df in processed_data.items():
            if df.empty:
                continue
                
            last_row = df.iloc[-1]
            close_val = self._get_scalar(last_row.get('Close', last_row.get('close')))
            rsi_val = self._get_scalar(last_row.get('RSI'))
            ema50_val = self._get_scalar(last_row.get('EMA_50'))
            ema200_val = self._get_scalar(last_row.get('EMA_200'))
            
            trend = "Bullish" if close_val > ema200_val else "Bearish"
            trend_class = trend.lower()
            
            html_content += f"""
            <h2>{ticker}</h2>
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Price</td><td>{close_val:.2f}</td></tr>
                <tr><td>RSI (14)</td><td>{rsi_val:.2f}</td></tr>
                <tr><td>EMA (50)</td><td>{ema50_val:.2f}</td></tr>
                <tr><td>EMA (200)</td><td>{ema200_val:.2f}</td></tr>
                <tr><td>Trend (vs EMA200)</td><td class="{trend_class}">{trend}</td></tr>
            </table>
            """
            
        html_content += """
        </body>
        </html>
        """
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        logger.info(f"Generated HTML report at: {filename}")
        return str(filename)
