"""
CLI commands for bot management.
"""

import asyncio
from pathlib import Path

import click

from bot_runner import start_bot
from config_loader import validate_all_platform_configs


@click.group()
def bot():
    """Bot management commands."""
    pass


@bot.command()
@click.argument('config_path', type=click.Path(exists=True))
def start(config_path):
    """Start a bot with the specified configuration."""
    click.echo(f"Starting bot with config: {config_path}")
    
    try:
        asyncio.run(start_bot(config_path))
    except KeyboardInterrupt:
        click.echo("\nBot stopped by user")
    except Exception as e:
        click.echo(f"Error starting bot: {e}")


@bot.command()
def list():
    """List all available bot configurations."""
    try:
        results = validate_all_platform_configs()
        
        click.echo("Available Bot Configurations:")
        click.echo("=" * 50)
        
        for config in results["valid_configs"]:
            status = "✅ Enabled" if config["enabled"] else "❌ Disabled"
            click.echo(f"{config['name']}: {status}")
            click.echo(f"  Platform: {config['platform']}")
            click.echo(f"  Listener: {config['listener']}")
            click.echo(f"  File: {config['file']}")
            click.echo()
        
        if results["invalid_configs"]:
            click.echo("Invalid Configurations:")
            click.echo("-" * 30)
            for invalid in results["invalid_configs"]:
                click.echo(f"❌ {invalid['file']}: {invalid['error']}")
        
        click.echo(f"\nSummary:")
        click.echo(f"  Valid: {len(results['valid_configs'])}")
        click.echo(f"  Invalid: {len(results['invalid_configs'])}")
        click.echo(f"  Platform distribution: {results['platform_distribution']}")
        
    except Exception as e:
        click.echo(f"Error listing configurations: {e}")


@bot.command()
@click.argument('config_path', type=click.Path(exists=True))
def validate(config_path):
    """Validate a bot configuration file."""
    try:
        from config_loader import load_bot_config, print_config_summary
        
        config = load_bot_config(config_path)
        click.echo(f"✅ Configuration is valid: {config_path}")
        click.echo()
        print_config_summary(config)
        
    except Exception as e:
        click.echo(f"❌ Configuration is invalid: {e}")


@bot.command()
def status():
    """Show status of all bots."""
    # This would show running bot processes
    click.echo("Bot Status:")
    click.echo("-" * 20)
    click.echo("No running bots detected")
    click.echo()
    click.echo("Use 'pump_bot bot list' to see available configurations")
    click.echo("Use 'pump_bot bot start <config>' to start a bot")


if __name__ == "__main__":
    bot()