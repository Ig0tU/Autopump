"""
Base AI provider interface for trading bot analysis.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from interfaces.core import TokenInfo


@dataclass
class AIResponse:
    """Response from AI analysis."""
    
    success: bool
    analysis: str
    confidence: float = 0.0
    recommendation: str = "hold"  # buy, sell, hold
    risk_score: float = 0.5  # 0.0 = low risk, 1.0 = high risk
    reasoning: List[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.reasoning is None:
            self.reasoning = []
        if self.metadata is None:
            self.metadata = {}


class AIProvider(ABC):
    """Abstract base class for AI providers."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize AI provider with configuration.
        
        Args:
            config: Provider-specific configuration
        """
        self.config = config
        self.name = self.__class__.__name__
    
    @abstractmethod
    async def analyze_token(self, token_info: TokenInfo, market_data: Dict[str, Any] = None) -> AIResponse:
        """Analyze a token and provide trading recommendation.
        
        Args:
            token_info: Token information
            market_data: Optional market data for analysis
            
        Returns:
            AI analysis response
        """
        pass
    
    @abstractmethod
    async def analyze_market_conditions(self, market_data: Dict[str, Any]) -> AIResponse:
        """Analyze overall market conditions.
        
        Args:
            market_data: Market data for analysis
            
        Returns:
            Market analysis response
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the AI provider is available and responding.
        
        Returns:
            True if provider is healthy
        """
        pass
    
    def format_token_prompt(self, token_info: TokenInfo, market_data: Dict[str, Any] = None) -> str:
        """Format token information into a prompt for AI analysis.
        
        Args:
            token_info: Token information
            market_data: Optional market data
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""
Analyze this new token for trading potential:

Token Information:
- Name: {token_info.name}
- Symbol: {token_info.symbol}
- Platform: {token_info.platform.value}
- Mint Address: {token_info.mint}
- Creator: {token_info.creator}

"""
        
        if market_data:
            prompt += f"""
Market Data:
- Current Price: {market_data.get('price', 'N/A')} SOL
- Market Cap: {market_data.get('market_cap', 'N/A')} SOL
- Volume: {market_data.get('volume', 'N/A')} SOL
- Liquidity: {market_data.get('liquidity', 'N/A')} SOL
- Age: {market_data.get('age', 'N/A')} seconds

"""
        
        prompt += """
Please provide:
1. Risk assessment (0.0 = low risk, 1.0 = high risk)
2. Trading recommendation (buy/sell/hold)
3. Confidence level (0.0 = no confidence, 1.0 = very confident)
4. Key reasoning points
5. Brief analysis summary

Focus on factors like token name quality, creator history, market conditions, and potential red flags.
"""
        
        return prompt