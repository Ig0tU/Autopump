"""
Ollama AI provider implementation.
"""

import json
from typing import Any, Dict

import aiohttp

from interfaces.core import TokenInfo
from utils.logger import get_logger

from .base import AIProvider, AIResponse

logger = get_logger(__name__)


class OllamaProvider(AIProvider):
    """Ollama local AI provider."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Ollama provider.
        
        Args:
            config: Configuration with 'url', 'model', and optional 'timeout'
        """
        super().__init__(config)
        self.base_url = config.get("url", "http://localhost:11434")
        self.model = config.get("model", "llama3.2")
        self.timeout = config.get("timeout", 30)
        
    async def analyze_token(self, token_info: TokenInfo, market_data: Dict[str, Any] = None) -> AIResponse:
        """Analyze token using Ollama."""
        try:
            prompt = self.format_token_prompt(token_info, market_data)
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9,
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Ollama API error: {response.status} - {error_text}")
                        return AIResponse(success=False, analysis=f"API Error: {error_text}")
                    
                    result = await response.json()
                    analysis_text = result.get("response", "")
                    
                    return self._parse_analysis_response(analysis_text)
                    
        except Exception as e:
            logger.exception("Ollama analysis failed")
            return AIResponse(success=False, analysis=f"Error: {str(e)}")
    
    async def analyze_market_conditions(self, market_data: Dict[str, Any]) -> AIResponse:
        """Analyze market conditions using Ollama."""
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
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    result = await response.json()
                    analysis_text = result.get("response", "")
                    
                    return self._parse_analysis_response(analysis_text)
                    
        except Exception as e:
            logger.exception("Ollama market analysis failed")
            return AIResponse(success=False, analysis=f"Error: {str(e)}")
    
    async def health_check(self) -> bool:
        """Check Ollama health."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
        except Exception:
            return False
    
    def _parse_analysis_response(self, text: str) -> AIResponse:
        """Parse AI response text into structured format."""
        try:
            # Simple parsing - look for key indicators
            text_lower = text.lower()
            
            # Extract recommendation
            recommendation = "hold"
            if "buy" in text_lower and "recommend" in text_lower:
                recommendation = "buy"
            elif "sell" in text_lower and "recommend" in text_lower:
                recommendation = "sell"
            
            # Extract confidence (look for percentages or confidence indicators)
            confidence = 0.5
            if "high confidence" in text_lower:
                confidence = 0.8
            elif "low confidence" in text_lower:
                confidence = 0.3
            elif "very confident" in text_lower:
                confidence = 0.9
            
            # Extract risk score
            risk_score = 0.5
            if "high risk" in text_lower:
                risk_score = 0.8
            elif "low risk" in text_lower:
                risk_score = 0.2
            elif "very risky" in text_lower or "extremely risky" in text_lower:
                risk_score = 0.9
            
            # Extract reasoning points
            reasoning = []
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith(('-', '•', '*')) or any(word in line.lower() for word in ['because', 'due to', 'reason']):
                    reasoning.append(line)
            
            return AIResponse(
                success=True,
                analysis=text,
                confidence=confidence,
                recommendation=recommendation,
                risk_score=risk_score,
                reasoning=reasoning[:5],  # Limit to top 5 reasons
                metadata={"provider": "ollama", "model": self.model}
            )
            
        except Exception as e:
            logger.exception("Failed to parse AI response")
            return AIResponse(
                success=True,
                analysis=text,
                metadata={"provider": "ollama", "model": self.model, "parse_error": str(e)}
            )