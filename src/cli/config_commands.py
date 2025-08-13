"""
CLI commands for configuration management.
"""

import json
from pathlib import Path

import click
import yaml

from config_loader import validate_all_platform_configs


@click.group()
def config():
    """Configuration management commands."""
    pass


@config.command()
def validate():
    """Validate all bot configurations."""
    try:
        results = validate_all_platform_configs()
        
        click.echo("Configuration Validation Results:")
        click.echo("=" * 40)
        
        # Show valid configs
        if results["valid_configs"]:
            click.echo("✅ Valid Configurations:")
            for config in results["valid_configs"]:
                status = "enabled" if config["enabled"] else "disabled"
                click.echo(f"  • {config['name']} ({config['platform']}) - {status}")
        
        # Show invalid configs
        if results["invalid_configs"]:
            click.echo("\n❌ Invalid Configurations:")
            for invalid in results["invalid_configs"]:
                click.echo(f"  • {invalid['file']}: {invalid['error']}")
        
        # Show summary
        click.echo(f"\nSummary:")
        click.echo(f"  Valid: {len(results['valid_configs'])}")
        click.echo(f"  Invalid: {len(results['invalid_configs'])}")
        click.echo(f"  Platforms: {results['platform_distribution']}")
        click.echo(f"  Listeners: {results['listener_distribution']}")
        
    except Exception as e:
        click.echo(f"Validation failed: {e}")


@config.command()
@click.argument('name')
@click.option('--platform', type=click.Choice(['pump_fun', 'lets_bonk']), default='pump_fun')
@click.option('--listener', type=click.Choice(['logs', 'blocks', 'geyser', 'pumpportal']), default='logs')
@click.option('--buy-amount', type=float, default=0.001)
@click.option('--slippage', type=float, default=0.3)
def create(name, platform, listener, buy_amount, slippage):
    """Create a new bot configuration."""
    try:
        config = {
            "name": name,
            "env_file": ".env",
            "rpc_endpoint": "${SOLANA_NODE_RPC_ENDPOINT}",
            "wss_endpoint": "${SOLANA_NODE_WSS_ENDPOINT}",
            "private_key": "${SOLANA_PRIVATE_KEY}",
            "enabled": True,
            "separate_process": True,
            "platform": platform,
            "trade": {
                "buy_amount": buy_amount,
                "buy_slippage": slippage,
                "sell_slippage": slippage,
                "exit_strategy": "time_based",
                "max_hold_time": 60,
                "extreme_fast_mode": True,
                "extreme_fast_token_amount": 20
            },
            "priority_fees": {
                "enable_dynamic": False,
                "enable_fixed": True,
                "fixed_amount": 200_000,
                "extra_percentage": 0.0,
                "hard_cap": 200_000
            },
            "filters": {
                "match_string": None,
                "bro_address": None,
                "listener_type": listener,
                "max_token_age": 0.001,
                "marry_mode": False,
                "yolo_mode": False
            },
            "retries": {
                "max_attempts": 1,
                "wait_after_creation": 15,
                "wait_after_buy": 15,
                "wait_before_new_token": 15
            },
            "cleanup": {
                "mode": "post_session",
                "force_close_with_burn": False,
                "with_priority_fee": False
            },
            "node": {
                "max_rps": 25
            }
        }
        
        # Add platform-specific configuration
        if platform == "pump_fun" and listener == "geyser":
            config["geyser"] = {
                "endpoint": "${GEYSER_ENDPOINT}",
                "api_token": "${GEYSER_API_TOKEN}",
                "auth_type": "x-token"
            }
        elif listener == "pumpportal":
            config["pumpportal"] = {
                "url": "wss://pumpportal.fun/api/data"
            }
        
        # Save configuration
        config_dir = Path("bots")
        config_dir.mkdir(exist_ok=True)
        
        config_file = config_dir / f"{name}.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        click.echo(f"✅ Created configuration: {config_file}")
        click.echo(f"Platform: {platform}")
        click.echo(f"Listener: {listener}")
        click.echo(f"Buy amount: {buy_amount} SOL")
        click.echo(f"Slippage: {slippage * 100}%")
        
    except Exception as e:
        click.echo(f"Failed to create configuration: {e}")


@config.command()
@click.argument('config_path', type=click.Path(exists=True))
def show(config_path):
    """Show configuration details."""
    try:
        from config_loader import load_bot_config, print_config_summary
        
        config = load_bot_config(config_path)
        click.echo(f"Configuration: {config_path}")
        click.echo("=" * 50)
        print_config_summary(config)
        
        click.echo("\nFull Configuration:")
        click.echo("-" * 30)
        click.echo(yaml.dump(config, default_flow_style=False))
        
    except Exception as e:
        click.echo(f"Failed to load configuration: {e}")


@config.command()
def env():
    """Show environment variable status."""
    required_vars = [
        "SOLANA_NODE_RPC_ENDPOINT",
        "SOLANA_NODE_WSS_ENDPOINT", 
        "SOLANA_PRIVATE_KEY"
    ]
    
    optional_vars = [
        "GEYSER_ENDPOINT",
        "GEYSER_API_TOKEN",
        "GEMINI_API_KEY"
    ]
    
    click.echo("Environment Variables:")
    click.echo("=" * 30)
    
    click.echo("Required:")
    for var in required_vars:
        value = os.getenv(var)
        status = "✅ Set" if value else "❌ Missing"
        click.echo(f"  {var}: {status}")
    
    click.echo("\nOptional:")
    for var in optional_vars:
        value = os.getenv(var)
        status = "✅ Set" if value else "⚪ Not set"
        click.echo(f"  {var}: {status}")


if __name__ == "__main__":
    config()