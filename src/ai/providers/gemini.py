"""
Gemini AI provider implementation.
"""

import json
from typing import Any, Dict

import aiohttp

from interfaces.core import TokenInfo
from utils.logger import get_logger

from .base import AIProvider, AIResponse

logger = get_logger(__name__)


class GeminiProvider(AIProvider):
    """Google Gemini AI provider."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Gemini provider.
        
        Args:
            config: Configuration with 'api_key', 'model', and optional 'timeout'
        """
        super().__init__(config)
        self.api_key = config.get("api_key")
        self.model = config.get("model", "gemini-1.5-flash")
        self.timeout = config.get("timeout", 30)
        
        if not self.api_key:
            raise ValueError("Gemini API key is required")
        
    async def analyze_token(self, token_info: TokenInfo, market_data: Dict[str, Any] = None) -> AIResponse:
        """Analyze token using Gemini."""
        try:
            prompt = self.format_token_prompt(token_info, market_data)
            
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": f"You are an expert cryptocurrency trader. {prompt}"
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 500,
                    "topP": 0.9,
                }
            }
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Gemini API error: {response.status} - {error_text}")
                        return AIResponse(success=False, analysis=f"API Error: {error_text}")
                    
                    result = await response.json()
                    
                    if "candidates" not in result or not result["candidates"]:
                        return AIResponse(success=False, analysis="No response from Gemini")
                    
                    analysis_text = result["candidates"][0]["content"]["parts"][0]["text"]
                    
                    return self._parse_analysis_response(analysis_text)
                    
        except Exception as e:
            logger.exception("Gemini analysis failed")
            return AIResponse(success=False, analysis=f"Error: {str(e)}")
    
    async def analyze_market_conditions(self, market_data: Dict[str, Any]) -> AIResponse:
        """Analyze market conditions using Gemini."""
        try:
            prompt = f"""
Analyze current market conditions for meme token trading:

Market Data:
{json.dumps(market_data, indent=2)}

Provide:
1. Overall market sentiment
2. Risk level for new token trading
3. Recommended strategy
4. Key market indicators to watch
"""
            
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": f"You are an expert cryptocurrency market analyst. {prompt}"
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 400,
                }
            }
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    result = await response.json()
                    analysis_text = result["candidates"][0]["content"]["parts"][0]["text"]
                    
                    return self._parse_analysis_response(analysis_text)
                    
        except Exception as e:
            logger.exception("Gemini market analysis failed")
            return AIResponse(success=False, analysis=f"Error: {str(e)}")
    
    async def health_check(self) -> bool:
        """Check Gemini health."""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
        except Exception:
            return False
    
    def _parse_analysis_response(self, text: str) -> AIResponse:
        """Parse AI response text into structured format."""
        try:
            text_lower = text.lower()
            
            # Extract recommendation
            recommendation = "hold"
            if "recommend buy" in text_lower or "should buy" in text_lower:
                recommendation = "buy"
            elif "recommend sell" in text_lower or "should sell" in text_lower:
                recommendation = "sell"
            elif "avoid" in text_lower or "skip" in text_lower:
                recommendation = "sell"
            
            # Extract confidence
            confidence = 0.5
            if "high confidence" in text_lower or "very confident" in text_lower:
                confidence = 0.8
            elif "low confidence" in text_lower or "uncertain" in text_lower:
                confidence = 0.3
            elif "extremely confident" in text_lower:
                confidence = 0.9
            
            # Extract risk score
            risk_score = 0.5
            if "high risk" in text_lower or "risky" in text_lower:
                risk_score = 0.8
            elif "low risk" in text_lower or "safe" in text_lower:
                risk_score = 0.2
            elif "extremely risky" in text_lower:
                risk_score = 0.9
            
            # Extract reasoning points
            reasoning = []
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith(('-', '•', '*', '1.', '2.', '3.', '4.', '5.')):
                    reasoning.append(line)
            
            return AIResponse(
                success=True,
                analysis=text,
                confidence=confidence,
                recommendation=recommendation,
                risk_score=risk_score,
                reasoning=reasoning[:5],
                metadata={"provider": "gemini", "model": self.model}
            )
            
        except Exception as e:
            logger.exception("Failed to parse AI response")
            return AIResponse(
                success=True,
                analysis=text,
                metadata={"provider": "gemini", "model": self.model, "parse_error": str(e)}
            )