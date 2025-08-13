"""
AI-enhanced trader that uses multiple AI providers for trading decisions.
"""

import asyncio
from typing import Dict, Any

from ai.manager import AIManager
from core.client import SolanaClient
from core.priority_fee.manager import PriorityFeeManager
from core.wallet import Wallet
from interfaces.core import TokenInfo
from trading.platform_aware import PlatformAwareBuyer, PlatformAwareSeller
from trading.base import TradeResult
from utils.logger import get_logger

logger = get_logger(__name__)


class AIEnhancedTrader:
    """Trading coordinator that uses AI analysis for decision making."""
    
    def __init__(
        self,
        client: SolanaClient,
        wallet: Wallet,
        priority_fee_manager: PriorityFeeManager,
        ai_config: Dict[str, Any],
        buy_amount: float,
        buy_slippage: float,
        sell_slippage: float,
        max_retries: int = 3,
    ):
        """Initialize AI-enhanced trader.
        
        Args:
            client: Solana RPC client
            wallet: Trading wallet
            priority_fee_manager: Priority fee manager
            ai_config: AI configuration
            buy_amount: Amount to buy in SOL
            buy_slippage: Buy slippage tolerance
            sell_slippage: Sell slippage tolerance
            max_retries: Maximum transaction retries
        """
        self.client = client
        self.wallet = wallet
        self.priority_fee_manager = priority_fee_manager
        self.ai_manager = AIManager(ai_config)
        
        # AI decision thresholds
        self.min_confidence = ai_config.get("min_confidence", 0.7)
        self.max_risk_score = ai_config.get("max_risk_score", 0.6)
        self.require_consensus = ai_config.get("require_consensus", True)
        
        # Create platform-aware traders
        self.buyer = PlatformAwareBuyer(
            client, wallet, priority_fee_manager, buy_amount, buy_slippage, max_retries
        )
        
        self.seller = PlatformAwareSeller(
            client, wallet, priority_fee_manager, sell_slippage, max_retries
        )
        
        logger.info(f"AI-Enhanced Trader initialized with {self.ai_manager.get_provider_count()} AI providers")
        logger.info(f"Decision thresholds: confidence >= {self.min_confidence}, risk <= {self.max_risk_score}")
    
    async def analyze_and_trade(self, token_info: TokenInfo, market_data: Dict[str, Any] = None) -> TradeResult:
        """Analyze token with AI and execute trade if conditions are met.
        
        Args:
            token_info: Token information
            market_data: Optional market data for analysis
            
        Returns:
            Trade result
        """
        try:
            logger.info(f"🧠 Starting AI analysis for {token_info.symbol}")
            
            # Get AI analysis
            if self.require_consensus:
                analysis = await self.ai_manager.get_consensus_analysis(token_info, market_data)
                logger.info(f"📊 Consensus analysis: {analysis.recommendation} (confidence: {analysis.confidence:.2f})")
            else:
                # Use first available provider
                responses = await self.ai_manager.analyze_token(token_info, market_data)
                if not responses:
                    return TradeResult(
                        success=False,
                        platform=token_info.platform,
                        error_message="No AI analysis available"
                    )
                analysis = responses[0]
                logger.info(f"📊 AI analysis: {analysis.recommendation} (confidence: {analysis.confidence:.2f})")
            
            # Log analysis details
            logger.info(f"🎯 Risk score: {analysis.risk_score:.2f}")
            if analysis.reasoning:
                logger.info(f"💭 Key reasoning: {'; '.join(analysis.reasoning[:3])}")
            
            # Check if analysis meets trading criteria
            if not self._should_trade_based_on_analysis(analysis):
                logger.info("❌ AI analysis does not meet trading criteria. Skipping trade.")
                return TradeResult(
                    success=False,
                    platform=token_info.platform,
                    error_message="AI analysis criteria not met"
                )
            
            # Execute trade based on AI recommendation
            if analysis.recommendation == "buy":
                logger.info("✅ AI recommends BUY. Executing purchase...")
                return await self.buyer.execute(token_info)
            elif analysis.recommendation == "sell":
                logger.info("✅ AI recommends SELL. Executing sale...")
                return await self.seller.execute(token_info)
            else:
                logger.info("⏸️ AI recommends HOLD. No action taken.")
                return TradeResult(
                    success=False,
                    platform=token_info.platform,
                    error_message="AI recommends hold"
                )
                
        except Exception as e:
            logger.exception("AI-enhanced trading failed")
            return TradeResult(
                success=False,
                platform=token_info.platform,
                error_message=f"AI trading error: {str(e)}"
            )
    
    def _should_trade_based_on_analysis(self, analysis) -> bool:
        """Determine if trade should be executed based on AI analysis.
        
        Args:
            analysis: AI analysis response
            
        Returns:
            True if trade should be executed
        """
        # Check if analysis was successful
        if not analysis.success:
            logger.warning("❌ AI analysis failed")
            return False
        
        # Check confidence threshold
        if analysis.confidence < self.min_confidence:
            logger.info(f"❌ Confidence too low: {analysis.confidence:.2f} < {self.min_confidence}")
            return False
        
        # Check risk threshold
        if analysis.risk_score > self.max_risk_score:
            logger.info(f"❌ Risk too high: {analysis.risk_score:.2f} > {self.max_risk_score}")
            return False
        
        # Only trade on buy/sell recommendations
        if analysis.recommendation not in ["buy", "sell"]:
            logger.info(f"❌ No clear trading signal: {analysis.recommendation}")
            return False
        
        logger.info("✅ AI analysis meets all trading criteria")
        return True
    
    async def get_market_sentiment(self) -> Dict[str, Any]:
        """Get overall market sentiment from AI providers.
        
        Returns:
            Market sentiment analysis
        """
        try:
            # Gather basic market data (this could be enhanced with real market APIs)
            market_data = {
                "timestamp": asyncio.get_event_loop().time(),
                "sol_price": "N/A",  # Could fetch from CoinGecko API
                "total_volume": "N/A",
                "active_tokens": "N/A"
            }
            
            # Get market analysis from first available provider
            if self.ai_manager.providers:
                provider = self.ai_manager.providers[0]
                analysis = await provider.analyze_market_conditions(market_data)
                
                return {
                    "sentiment": analysis.recommendation,
                    "confidence": analysis.confidence,
                    "risk_level": analysis.risk_score,
                    "analysis": analysis.analysis,
                    "provider": analysis.metadata.get("provider", "unknown")
                }
            
            return {"error": "No AI providers available"}
            
        except Exception as e:
            logger.exception("Market sentiment analysis failed")
            return {"error": str(e)}
    
    async def close(self):
        """Clean up resources."""
        # AI manager doesn't need explicit cleanup currently
        pass