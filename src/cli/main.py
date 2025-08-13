"""
Main CLI interface for the trading bot.
"""

import click

from cli.ai_commands import ai
from cli.bot_commands import bot
from cli.config_commands import config


@click.group()
@click.version_option(version="2.0")
def cli():
    """Pump Bot - Advanced trading bot for pump.fun and letsbonk.fun with AI analysis."""
    pass


# Add command groups
cli.add_command(bot)
cli.add_command(config)
cli.add_command(ai)


@cli.command()
def webui():
    """Start the web UI server."""
    import asyncio
    from webui.server import main
    
    click.echo("Starting web UI server...")
    click.echo("Open http://localhost:8080 in your browser")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        click.echo("\nWeb UI server stopped")


if __name__ == "__main__":
    cli()