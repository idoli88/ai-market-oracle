
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from oracle.config import settings
from oracle.prompts import SYSTEM_PROMPT, generate_user_prompt
from openai import OpenAI

logger = logging.getLogger(__name__)

class AnalysisGate:
    @staticmethod
    def should_trigger_llm(ticker: str, current_data: Dict, snapshot: Optional[Dict]) -> bool:
        """
        Decide if we need to call LLM.
        Triggers:
        1. Price change > threshold vs snapshot
        2. RSI Oversold/Overbought
        3. No snapshot exists (first run)
        4. (Future) New Filings/News
        """
        if not snapshot:
            return True
        
        # 1. Price Change
        last_price = snapshot.get("last_price")
        if last_price:
            pct_change = abs((current_data["current_price"] - last_price) / last_price) * 100
            if pct_change >= settings.PRICE_CHANGE_TRIGGER_PCT:
                logger.info(f"Gate OPEN for {ticker}: Price change {pct_change:.2f}%")
                return True
        
        # 2. RSI
        rsi = current_data.get("rsi", 50)
        if rsi >= settings.RSI_OVERBOUGHT or rsi <= settings.RSI_OVERSOLD:
            logger.info(f"Gate OPEN for {ticker}: RSI Extreme {rsi}")
            return True
            
        logger.info(f"Gate CLOSED for {ticker}")
        return False

class LLMClient:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
    def analyze_ticker(self, ticker: str, data: Dict, context: str = "") -> Dict:
        """
        Send data to LLM and get JSON response.
        """
        user_prompt = f"""
        Analyze {ticker}.
        
        Data:
        Price: {data.get('current_price')}
        RSI: {data.get('rsi')}
        EMA50: {data.get('ema_short')}
        EMA200: {data.get('ema_long')}
        
        Context:
        {context}
        
        Return STRICT JSON.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini", # Use cheaper model as default
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={ "type": "json_object" }
            )
            
            content = response.choices[0].message.content
            parsed = json.loads(content)
            return parsed
        except Exception as e:
            logger.error(f"LLM analysis failed for {ticker}: {e}")
            return self._fallback_response(ticker, data)

    def _fallback_response(self, ticker: str, data: Dict) -> Dict:
        return {
            "ticker": ticker,
            "action": "WAIT",
            "confidence": 0,
            "summary_he": f"לא ניתן היה לבצע ניתוח מלא. נתונים טכניים: RSI={data.get('rsi')}",
            "key_points_he": ["שגיאה בניתוח", "אנא בדוק מאוחר יותר"],
            "invalidation_he": "N/A",
            "risk_note_he": "N/A"
        }
