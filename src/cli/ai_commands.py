"""
CLI commands for AI functionality.
"""

import asyncio
import json
import os
from typing import Dict, Any

import click

from ai.manager import AIManager
from interfaces.core import Platform, TokenInfo
from utils.logger import get_logger

logger = get_logger(__name__)


@click.group()
def ai():
    """AI analysis commands."""
    pass


@ai.command()
@click.option('--provider', type=click.Choice(['ollama', 'lmstudio', 'localai', 'gemini', 'all']), default='all')
def health(provider):
    """Check AI provider health."""
    async def check_health():
        config = get_ai_config()
        manager = AIManager(config)
        
        if provider == 'all':
            health_status = await manager.check_provider_health()
            click.echo("AI Provider Health Status:")
            click.echo("-" * 30)
            for name, status in health_status.items():
                status_text = "✅ Healthy" if status else "❌ Unhealthy"
                click.echo(f"{name}: {status_text}")
        else:
            # Check specific provider
            health_status = await manager.check_provider_health()
            if provider in health_status:
                status = health_status[provider]
                status_text = "✅ Healthy" if status else "❌ Unhealthy"
                click.echo(f"{provider}: {status_text}")
            else:
                click.echo(f"Provider '{provider}' not found or not configured")
    
    asyncio.run(check_health())


@ai.command()
@click.option('--name', required=True, help='Token name')
@click.option('--symbol', required=True, help='Token symbol')
@click.option('--mint', help='Token mint address')
@click.option('--creator', help='Token creator address')
@click.option('--price', type=float, help='Current token price in SOL')
@click.option('--market-cap', type=float, help='Market cap in SOL')
@click.option('--provider', type=click.Choice(['ollama', 'lmstudio', 'localai', 'gemini', 'consensus']), default='consensus')
def analyze(name, symbol, mint, creator, price, market_cap, provider):
    """Analyze a token using AI."""
    async def run_analysis():
        config = get_ai_config()
        manager = AIManager(config)
        
        # Create token info
        token_info = TokenInfo(
            name=name,
            symbol=symbol,
            uri="",
            mint=mint or "11111111111111111111111111111111",
            platform=Platform.PUMP_FUN,
            creator=creator,
            user=creator
        )
        
        # Prepare market data
        market_data = {}
        if price:
            market_data['price'] = price
        if market_cap:
            market_data['market_cap'] = market_cap
        
        if provider == 'consensus':
            # Get consensus analysis
            analysis = await manager.get_consensus_analysis(token_info, market_data)
            display_analysis(analysis, "Consensus")
        else:
            # Get analysis from specific provider
            responses = await manager.analyze_token(token_info, market_data)
            
            for response in responses:
                provider_name = response.metadata.get('provider', 'Unknown')
                if provider_name.lower() == provider.lower():
                    display_analysis(response, provider_name)
                    return
            
            click.echo(f"No analysis available from provider: {provider}")
    
    asyncio.run(run_analysis())


@ai.command()
def providers():
    """List available AI providers."""
    config = get_ai_config()
    
    click.echo("Available AI Providers:")
    click.echo("-" * 30)
    
    providers_config = config.get("providers", {})
    for name, provider_config in providers_config.items():
        enabled = provider_config.get("enabled", False)
        model = provider_config.get("model", "N/A")
        url = provider_config.get("url", "N/A")
        
        status = "✅ Enabled" if enabled else "❌ Disabled"
        click.echo(f"{name.upper()}: {status}")
        click.echo(f"  Model: {model}")
        click.echo(f"  URL: {url}")
        click.echo()


@ai.command()
@click.option('--provider', required=True, type=click.Choice(['ollama', 'lmstudio', 'localai', 'gemini']))
@click.option('--url', help='Provider URL')
@click.option('--model', help='Model name')
@click.option('--api-key', help='API key (for Gemini)')
@click.option('--enable/--disable', default=True, help='Enable or disable provider')
def configure(provider, url, model, api_key, enable):
    """Configure an AI provider."""
    config = get_ai_config()
    
    if "providers" not in config:
        config["providers"] = {}
    
    if provider not in config["providers"]:
        config["providers"][provider] = {}
    
    provider_config = config["providers"][provider]
    
    if url:
        provider_config["url"] = url
    if model:
        provider_config["model"] = model
    if api_key:
        provider_config["api_key"] = api_key
    
    provider_config["enabled"] = enable
    
    # Save configuration
    save_ai_config(config)
    
    status = "enabled" if enable else "disabled"
    click.echo(f"Provider '{provider}' has been {status}")


def get_ai_config() -> Dict[str, Any]:
    """Get AI configuration from file or create default."""
    config_file = Path("ai_config.json")
    
    if config_file.exists():
        with open(config_file, 'r') as f:
            return json.load(f)
    
    # Default configuration
    return {
        "providers": {
            "ollama": {
                "enabled": True,
                "url": "http://localhost:11434",
                "model": "llama3.2",
                "timeout": 30
            },
            "lmstudio": {
                "enabled": True,
                "url": "http://localhost:1234",
                "model": "local-model", 
                "timeout": 30
            },
            "localai": {
                "enabled": True,
                "url": "http://localhost:8080",
                "model": "gpt-3.5-turbo",
                "timeout": 30
            },
            "gemini": {
                "enabled": bool(os.getenv("GEMINI_API_KEY")),
                "api_key": os.getenv("GEMINI_API_KEY"),
                "model": "gemini-1.5-flash",
                "timeout": 30
            }
        }
    }


def save_ai_config(config: Dict[str, Any]):
    """Save AI configuration to file."""
    config_file = Path("ai_config.json")
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)


def display_analysis(analysis, provider_name):
    """Display AI analysis in a formatted way."""
    click.echo(f"\n🤖 {provider_name} Analysis:")
    click.echo("=" * 50)
    
    if not analysis.success:
        click.echo(f"❌ Analysis failed: {analysis.analysis}")
        return
    
    # Display key metrics
    click.echo(f"Recommendation: {analysis.recommendation.upper()}")
    click.echo(f"Confidence: {analysis.confidence * 100:.1f}%")
    click.echo(f"Risk Score: {analysis.risk_score * 100:.1f}%")
    
    # Display reasoning
    if analysis.reasoning:
        click.echo("\nKey Reasoning:")
        for i, reason in enumerate(analysis.reasoning[:5], 1):
            click.echo(f"  {i}. {reason}")
    
    # Display full analysis
    click.echo(f"\nFull Analysis:")
    click.echo("-" * 30)
    click.echo(analysis.analysis)


if __name__ == "__main__":
    ai()