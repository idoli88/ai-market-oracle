
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from oracle.config import settings
from oracle.prompts import SYSTEM_PROMPT, generate_user_prompt
from openai import OpenAI
from oracle.schemas import AnalysisResponse
from pydantic import ValidationError

logger = logging.getLogger(__name__)

class AnalysisGate:
    @staticmethod
    def should_trigger_llm(ticker: str, current_data: Dict, snapshot: Optional[Dict]) -> tuple[bool, str]:
        """
        Decide if we need to call LLM.
        Returns: (should_run, reason_trigger)
        """
        if not snapshot:
            logger.info(f"Gate OPEN for {ticker}: First run/No snapshot")
            return True, "FIRST_RUN"
        
        # 0. Cooldown Check
        last_at = snapshot.get("last_trigger_at")
        if last_at and isinstance(last_at, str):
            try:
                # Parse if string (sqlite returns string)
                last_at = datetime.fromisoformat(last_at)
            except ValueError:
                pass # Trigger anyway if parse fails
        
        if last_at and isinstance(last_at, datetime):
             # Ensure last_at is offset-naive or aware matching datetime.now()
             # SQLite usually naïve.
             delta = datetime.now() - last_at
             if delta.total_seconds() < (settings.COOLDOWN_HOURS * 3600):
                 logger.info(f"Gate CLOSED for {ticker}: Cooldown active (Last: {last_at})")
                 return False, None

        triggers = []
        
        # 1. Price Change
        last_price = snapshot.get("last_price")
        if last_price:
            pct_change = abs((current_data["current_price"] - last_price) / last_price) * 100
            if pct_change >= settings.PRICE_CHANGE_TRIGGER_PCT:
                triggers.append(f"Price Change {pct_change:.2f}%")
        
        # 2. RSI Extreme
        rsi = current_data.get("rsi", 50)
        if rsi >= settings.RSI_OVERBOUGHT:
            triggers.append(f"RSI Overbought {rsi}")
        elif rsi <= settings.RSI_OVERSOLD:
            triggers.append(f"RSI Oversold {rsi}")
            
        # 3. RSI Delta (Spike)
        last_rsi = snapshot.get("last_rsi")
        if last_rsi:
            rsi_delta = abs(rsi - last_rsi)
            if rsi_delta >= settings.RSI_DELTA_TRIGGER:
                triggers.append(f"RSI Delta {rsi_delta:.1f}")

        # 4. Volume Spike
        vol = current_data.get("current_volume", 0)
        vol_sma = current_data.get("volume_sma", 0)
        if vol_sma > 0 and vol > (vol_sma * settings.VOL_SPIKE_MULTIPLIER):
             triggers.append(f"Volume Spike ({vol} > {settings.VOL_SPIKE_MULTIPLIER}x Avg)")

        # 5. EMA Cross (Price vs EMA50) - simplified
        # Real cross requires checking previous state. We have snapshot['last_price'] and snapshot['last_ema'].
        # Bullish Cross: Last Price < Last EMA AND Curr Price > Curr EMA
        c_price = current_data["current_price"]
        c_ema = current_data["ema_short"]
        l_price = snapshot.get("last_price")
        l_ema = snapshot.get("last_ema_short")
        
        if l_price and l_ema:
            if l_price < l_ema and c_price > c_ema:
                triggers.append("Bullish EMA50 Cross")
            elif l_price > l_ema and c_price < c_ema:
                triggers.append("Bearish EMA50 Cross")
        
        if triggers:
            reason = ", ".join(triggers)
            logger.info(f"Gate OPEN for {ticker}: {reason}")
            return True, reason
            
        logger.info(f"Gate CLOSED for {ticker}")
        return False, None

class LLMClient:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
    def analyze_ticker(self, ticker: str, data: Dict, context: str = "", diff_context: str = "", plan: str = "basic") -> Dict:
        """
        Send data to LLM and get JSON response.
        Routing:
        - If plan='pro' AND (Price Change > 3% OR Volume Spike), use HQ Model.
        - Else use Basic Model.
        """
        model = settings.MODEL_BASIC
        
        # Routing Logic
        price_change = abs(data.get('price_change_pct', 0))
        is_major_event = price_change > settings.MAJOR_EVENT_THRESHOLD_PCT or "Volume" in context
        
        if plan == "pro" and is_major_event:
            model = settings.MODEL_HQ
            logger.info(f"Using HQ Model ({model}) for {ticker} (Plan: Pro, Event: Major)")
        else:
            logger.info(f"Using Basic Model ({model}) for {ticker}")

        user_prompt = f"""
        Analyze {ticker} for a swing trader.
        
        Data:
        Price: {data.get('current_price')}
        Change: {data.get('price_change_pct')}%
        RSI: {data.get('rsi')}
        EMA50: {data.get('ema_short')}
        EMA200: {data.get('ema_long')}
        ATR: {data.get('atr')}
        
        Changes since last:
        {diff_context}
        
        Context/Trigger:
        {context}
        
        Output Schema (JSON):
        {{
            "action": "BUY" | "SELL" | "HOLD",
            "emoji": "🚀" | "⚠️" | "📉" | "👀",
            "confidence": 0.0-1.0,
            "summary_he": "Short summary in Hebrew",
            "key_points_he": ["Point 1", "Point 2"... max 5],
            "invalidation_he": "Price level or condition to invalidate",
            "risk_note_he": "Risk management note"
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a professional market analyst. Output valid JSON only."},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from LLM")
                
            # Validation
            validated = AnalysisResponse.model_validate_json(content)
            return validated.model_dump()
            
        except (ValidationError, Exception) as e:
            logger.error(f"LLM Analysis Failed for {ticker}: {e}")
            return self._fallback_response(ticker, data)

    def _fallback_response(self, ticker: str, data: Dict) -> Dict:
        """Return safe fallback response on failure."""
        return {
            "ticker": ticker,
            "action": "HOLD",
            "confidence": 0,
            "summary_he": f"לא ניתן היה לבצע ניתוח מלא. נתונים טכניים: RSI={data.get('rsi')}",
            "key_points_he": ["שגיאה בניתוח", "אנא בדוק מאוחר יותר"],
            "invalidation_he": "N/A",
            "risk_note_he": "N/A"
        }
