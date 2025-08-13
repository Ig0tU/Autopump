"""
AI Manager for coordinating multiple AI providers.
"""

import asyncio
from typing import Any, Dict, List, Optional

from interfaces.core import TokenInfo
from utils.logger import get_logger

from .providers import AIProvider, AIResponse, GeminiProvider, LocalAIProvider, LMStudioProvider, OllamaProvider

logger = get_logger(__name__)


class AIManager:
    """Manages multiple AI providers for token analysis."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize AI manager with provider configurations.
        
        Args:
            config: Configuration dictionary with provider settings
        """
        self.providers: List[AIProvider] = []
        self.config = config
        self._setup_providers()
    
    def _setup_providers(self):
        """Setup AI providers based on configuration."""
        provider_configs = self.config.get("providers", {})
        
        # Setup Ollama
        if "ollama" in provider_configs and provider_configs["ollama"].get("enabled", False):
            try:
                ollama_config = provider_configs["ollama"]
                provider = OllamaProvider(ollama_config)
                self.providers.append(provider)
                logger.info(f"Initialized Ollama provider: {ollama_config.get('model', 'default')}")
            except Exception as e:
                logger.error(f"Failed to initialize Ollama provider: {e}")
        
        # Setup LM Studio
        if "lmstudio" in provider_configs and provider_configs["lmstudio"].get("enabled", False):
            try:
                lmstudio_config = provider_configs["lmstudio"]
                provider = LMStudioProvider(lmstudio_config)
                self.providers.append(provider)
                logger.info(f"Initialized LM Studio provider: {lmstudio_config.get('model', 'default')}")
            except Exception as e:
                logger.error(f"Failed to initialize LM Studio provider: {e}")
        
        # Setup LocalAI
        if "localai" in provider_configs and provider_configs["localai"].get("enabled", False):
            try:
                localai_config = provider_configs["localai"]
                provider = LocalAIProvider(localai_config)
                self.providers.append(provider)
                logger.info(f"Initialized LocalAI provider: {localai_config.get('model', 'default')}")
            except Exception as e:
                logger.error(f"Failed to initialize LocalAI provider: {e}")
        
        # Setup Gemini
        if "gemini" in provider_configs and provider_configs["gemini"].get("enabled", False):
            try:
                gemini_config = provider_configs["gemini"]
                provider = GeminiProvider(gemini_config)
                self.providers.append(provider)
                logger.info(f"Initialized Gemini provider: {gemini_config.get('model', 'default')}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini provider: {e}")
        
        logger.info(f"AI Manager initialized with {len(self.providers)} providers")
    
    async def analyze_token(self, token_info: TokenInfo, market_data: Dict[str, Any] = None) -> List[AIResponse]:
        """Analyze token using all available providers.
        
        Args:
            token_info: Token information
            market_data: Optional market data
            
        Returns:
            List of AI responses from all providers
        """
        if not self.providers:
            logger.warning("No AI providers available for token analysis")
            return []
        
        tasks = []
        for provider in self.providers:
            task = asyncio.create_task(
                self._safe_analyze_token(provider, token_info, market_data)
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and return valid responses
        valid_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                logger.error(f"Provider {self.providers[i].name} failed: {response}")
            elif isinstance(response, AIResponse):
                valid_responses.append(response)
        
        return valid_responses
    
    async def get_consensus_analysis(self, token_info: TokenInfo, market_data: Dict[str, Any] = None) -> AIResponse:
        """Get consensus analysis from multiple providers.
        
        Args:
            token_info: Token information
            market_data: Optional market data
            
        Returns:
            Consensus AI response
        """
        responses = await self.analyze_token(token_info, market_data)
        
        if not responses:
            return AIResponse(
                success=False,
                analysis="No AI providers available for analysis"
            )
        
        # Calculate consensus
        buy_votes = sum(1 for r in responses if r.recommendation == "buy")
        sell_votes = sum(1 for r in responses if r.recommendation == "sell")
        hold_votes = sum(1 for r in responses if r.recommendation == "hold")
        
        # Determine consensus recommendation
        if buy_votes > sell_votes and buy_votes > hold_votes:
            consensus_recommendation = "buy"
        elif sell_votes > buy_votes and sell_votes > hold_votes:
            consensus_recommendation = "sell"
        else:
            consensus_recommendation = "hold"
        
        # Calculate average metrics
        avg_confidence = sum(r.confidence for r in responses) / len(responses)
        avg_risk_score = sum(r.risk_score for r in responses) / len(responses)
        
        # Combine reasoning
        all_reasoning = []
        for response in responses:
            all_reasoning.extend(response.reasoning)
        
        # Create consensus analysis text
        consensus_text = f"""
CONSENSUS ANALYSIS ({len(responses)} providers):

Recommendation: {consensus_recommendation.upper()}
- Buy votes: {buy_votes}
- Sell votes: {sell_votes}  
- Hold votes: {hold_votes}

Average Confidence: {avg_confidence:.2f}
Average Risk Score: {avg_risk_score:.2f}

Individual Provider Analyses:
"""
        
        for i, response in enumerate(responses):
            provider_name = response.metadata.get("provider", f"Provider {i+1}")
            consensus_text += f"\n{provider_name.upper()}:\n"
            consensus_text += f"- Recommendation: {response.recommendation}\n"
            consensus_text += f"- Confidence: {response.confidence:.2f}\n"
            consensus_text += f"- Risk: {response.risk_score:.2f}\n"
            if response.reasoning:
                consensus_text += f"- Key points: {'; '.join(response.reasoning[:2])}\n"
        
        return AIResponse(
            success=True,
            analysis=consensus_text,
            confidence=avg_confidence,
            recommendation=consensus_recommendation,
            risk_score=avg_risk_score,
            reasoning=all_reasoning[:10],  # Top 10 reasoning points
            metadata={
                "provider": "consensus",
                "provider_count": len(responses),
                "individual_responses": responses
            }
        )
    
    async def check_provider_health(self) -> Dict[str, bool]:
        """Check health of all providers.
        
        Returns:
            Dictionary mapping provider names to health status
        """
        health_status = {}
        
        for provider in self.providers:
            try:
                is_healthy = await provider.health_check()
                health_status[provider.name] = is_healthy
            except Exception as e:
                logger.error(f"Health check failed for {provider.name}: {e}")
                health_status[provider.name] = False
        
        return health_status
    
    async def _safe_analyze_token(self, provider: AIProvider, token_info: TokenInfo, market_data: Dict[str, Any] = None) -> AIResponse:
        """Safely analyze token with a provider, handling exceptions.
        
        Args:
            provider: AI provider to use
            token_info: Token information
            market_data: Optional market data
            
        Returns:
            AI response or error response
        """
        try:
            return await provider.analyze_token(token_info, market_data)
        except Exception as e:
            logger.exception(f"Provider {provider.name} analysis failed")
            return AIResponse(
                success=False,
                analysis=f"Provider {provider.name} failed: {str(e)}",
                metadata={"provider": provider.name, "error": str(e)}
            )
    
    def get_provider_names(self) -> List[str]:
        """Get names of all configured providers.
        
        Returns:
            List of provider names
        """
        return [provider.name for provider in self.providers]
    
    def get_provider_count(self) -> int:
        """Get number of configured providers.
        
        Returns:
            Number of providers
        """
        return len(self.providers)