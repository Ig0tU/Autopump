"""
Web UI server for the trading bot.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import aiohttp
from aiohttp import web, web_ws
from aiohttp.web import Application, Request, Response, WebSocketResponse

from ai.manager import AIManager
from config_loader import load_bot_config, validate_all_platform_configs
from core.client import SolanaClient
from interfaces.core import Platform
from utils.logger import get_logger

logger = get_logger(__name__)


class TradingBotWebUI:
    """Web UI server for managing the trading bot."""
    
    def __init__(self, host: str = "localhost", port: int = 8080):
        """Initialize the web UI server.
        
        Args:
            host: Server host
            port: Server port
        """
        self.host = host
        self.port = port
        self.app = Application()
        self.websockets: List[WebSocketResponse] = []
        self.ai_manager: AIManager = None
        self.bot_processes: Dict[str, Any] = {}
        self.setup_routes()
        self.setup_ai_manager()
    
    def setup_ai_manager(self):
        """Setup AI manager with default configuration."""
        try:
            ai_config = {
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
            self.ai_manager = AIManager(ai_config)
        except Exception as e:
            logger.error(f"Failed to setup AI manager: {e}")
    
    def setup_routes(self):
        """Setup web routes."""
        # Static files
        self.app.router.add_get("/", self.index_handler)
        self.app.router.add_get("/static/{filename}", self.static_handler)
        
        # API endpoints
        self.app.router.add_get("/api/status", self.status_handler)
        self.app.router.add_get("/api/configs", self.configs_handler)
        self.app.router.add_post("/api/configs/validate", self.validate_config_handler)
        self.app.router.add_post("/api/bot/start", self.start_bot_handler)
        self.app.router.add_post("/api/bot/stop", self.stop_bot_handler)
        self.app.router.add_get("/api/logs", self.logs_handler)
        self.app.router.add_get("/api/trades", self.trades_handler)
        
        # AI endpoints
        self.app.router.add_get("/api/ai/providers", self.ai_providers_handler)
        self.app.router.add_post("/api/ai/analyze", self.ai_analyze_handler)
        self.app.router.add_get("/api/ai/health", self.ai_health_handler)
        
        # WebSocket
        self.app.router.add_get("/ws", self.websocket_handler)
    
    async def index_handler(self, request: Request) -> Response:
        """Serve the main HTML page."""
        html_content = self.get_html_content()
        return Response(text=html_content, content_type="text/html")
    
    async def static_handler(self, request: Request) -> Response:
        """Serve static files."""
        filename = request.match_info["filename"]
        # For now, return empty response for static files
        return Response(text="", content_type="text/plain")
    
    async def status_handler(self, request: Request) -> Response:
        """Get bot status."""
        try:
            # Check RPC health
            rpc_endpoint = os.getenv("SOLANA_NODE_RPC_ENDPOINT")
            rpc_healthy = False
            
            if rpc_endpoint:
                try:
                    client = SolanaClient(rpc_endpoint)
                    health = await client.get_health()
                    rpc_healthy = health == "ok"
                    await client.close()
                except Exception:
                    pass
            
            status = {
                "timestamp": datetime.utcnow().isoformat(),
                "rpc_healthy": rpc_healthy,
                "rpc_endpoint": rpc_endpoint,
                "active_bots": len(self.bot_processes),
                "websocket_connections": len(self.websockets),
                "ai_providers": self.ai_manager.get_provider_count() if self.ai_manager else 0
            }
            
            return web.json_response(status)
            
        except Exception as e:
            logger.exception("Status check failed")
            return web.json_response({"error": str(e)}, status=500)
    
    async def configs_handler(self, request: Request) -> Response:
        """Get bot configurations."""
        try:
            results = validate_all_platform_configs()
            return web.json_response(results)
        except Exception as e:
            logger.exception("Config loading failed")
            return web.json_response({"error": str(e)}, status=500)
    
    async def validate_config_handler(self, request: Request) -> Response:
        """Validate a bot configuration."""
        try:
            data = await request.json()
            config_path = data.get("config_path")
            
            if not config_path:
                return web.json_response({"error": "config_path required"}, status=400)
            
            try:
                config = load_bot_config(config_path)
                return web.json_response({"valid": True, "config": config})
            except Exception as e:
                return web.json_response({"valid": False, "error": str(e)})
                
        except Exception as e:
            logger.exception("Config validation failed")
            return web.json_response({"error": str(e)}, status=500)
    
    async def start_bot_handler(self, request: Request) -> Response:
        """Start a bot."""
        try:
            data = await request.json()
            config_path = data.get("config_path")
            
            if not config_path:
                return web.json_response({"error": "config_path required"}, status=400)
            
            # For now, just simulate starting a bot
            bot_id = f"bot_{len(self.bot_processes)}"
            self.bot_processes[bot_id] = {
                "config_path": config_path,
                "status": "running",
                "started_at": datetime.utcnow().isoformat()
            }
            
            await self.broadcast_message({
                "type": "bot_started",
                "bot_id": bot_id,
                "config_path": config_path
            })
            
            return web.json_response({"success": True, "bot_id": bot_id})
            
        except Exception as e:
            logger.exception("Bot start failed")
            return web.json_response({"error": str(e)}, status=500)
    
    async def stop_bot_handler(self, request: Request) -> Response:
        """Stop a bot."""
        try:
            data = await request.json()
            bot_id = data.get("bot_id")
            
            if bot_id in self.bot_processes:
                self.bot_processes[bot_id]["status"] = "stopped"
                self.bot_processes[bot_id]["stopped_at"] = datetime.utcnow().isoformat()
                
                await self.broadcast_message({
                    "type": "bot_stopped",
                    "bot_id": bot_id
                })
                
                return web.json_response({"success": True})
            else:
                return web.json_response({"error": "Bot not found"}, status=404)
                
        except Exception as e:
            logger.exception("Bot stop failed")
            return web.json_response({"error": str(e)}, status=500)
    
    async def logs_handler(self, request: Request) -> Response:
        """Get recent log entries."""
        try:
            logs_dir = Path("logs")
            if not logs_dir.exists():
                return web.json_response({"logs": []})
            
            # Get most recent log file
            log_files = list(logs_dir.glob("*.log"))
            if not log_files:
                return web.json_response({"logs": []})
            
            latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
            
            # Read last 100 lines
            with open(latest_log, 'r') as f:
                lines = f.readlines()
                recent_lines = lines[-100:] if len(lines) > 100 else lines
            
            return web.json_response({"logs": recent_lines})
            
        except Exception as e:
            logger.exception("Log retrieval failed")
            return web.json_response({"error": str(e)}, status=500)
    
    async def trades_handler(self, request: Request) -> Response:
        """Get recent trades."""
        try:
            trades_file = Path("trades/trades.log")
            if not trades_file.exists():
                return web.json_response({"trades": []})
            
            trades = []
            with open(trades_file, 'r') as f:
                for line in f:
                    try:
                        trade = json.loads(line.strip())
                        trades.append(trade)
                    except json.JSONDecodeError:
                        continue
            
            # Return last 50 trades
            recent_trades = trades[-50:] if len(trades) > 50 else trades
            return web.json_response({"trades": recent_trades})
            
        except Exception as e:
            logger.exception("Trade retrieval failed")
            return web.json_response({"error": str(e)}, status=500)
    
    async def ai_providers_handler(self, request: Request) -> Response:
        """Get AI provider information."""
        try:
            if not self.ai_manager:
                return web.json_response({"providers": []})
            
            providers_info = []
            for provider in self.ai_manager.providers:
                providers_info.append({
                    "name": provider.name,
                    "model": provider.config.get("model", "unknown"),
                    "url": provider.config.get("url", "N/A")
                })
            
            return web.json_response({"providers": providers_info})
            
        except Exception as e:
            logger.exception("AI providers retrieval failed")
            return web.json_response({"error": str(e)}, status=500)
    
    async def ai_analyze_handler(self, request: Request) -> Response:
        """Analyze token with AI."""
        try:
            if not self.ai_manager:
                return web.json_response({"error": "AI manager not available"}, status=503)
            
            data = await request.json()
            
            # Create mock token info for analysis
            from interfaces.core import TokenInfo
            
            token_info = TokenInfo(
                name=data.get("name", "Test Token"),
                symbol=data.get("symbol", "TEST"),
                uri=data.get("uri", ""),
                mint=data.get("mint", "11111111111111111111111111111111"),
                platform=Platform.PUMP_FUN,
                user=data.get("user"),
                creator=data.get("creator")
            )
            
            market_data = data.get("market_data", {})
            
            # Get consensus analysis
            analysis = await self.ai_manager.get_consensus_analysis(token_info, market_data)
            
            return web.json_response({
                "success": analysis.success,
                "analysis": analysis.analysis,
                "recommendation": analysis.recommendation,
                "confidence": analysis.confidence,
                "risk_score": analysis.risk_score,
                "reasoning": analysis.reasoning,
                "metadata": analysis.metadata
            })
            
        except Exception as e:
            logger.exception("AI analysis failed")
            return web.json_response({"error": str(e)}, status=500)
    
    async def ai_health_handler(self, request: Request) -> Response:
        """Check AI provider health."""
        try:
            if not self.ai_manager:
                return web.json_response({"providers": {}})
            
            health_status = await self.ai_manager.check_provider_health()
            return web.json_response({"providers": health_status})
            
        except Exception as e:
            logger.exception("AI health check failed")
            return web.json_response({"error": str(e)}, status=500)
    
    async def websocket_handler(self, request: Request) -> WebSocketResponse:
        """Handle WebSocket connections."""
        ws = web_ws.WebSocketResponse()
        await ws.prepare(request)
        
        self.websockets.append(ws)
        logger.info(f"WebSocket connected. Total connections: {len(self.websockets)}")
        
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self.handle_websocket_message(ws, data)
                    except json.JSONDecodeError:
                        await ws.send_str(json.dumps({"error": "Invalid JSON"}))
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
        except Exception as e:
            logger.exception("WebSocket error")
        finally:
            if ws in self.websockets:
                self.websockets.remove(ws)
            logger.info(f"WebSocket disconnected. Total connections: {len(self.websockets)}")
        
        return ws
    
    async def handle_websocket_message(self, ws: WebSocketResponse, data: Dict[str, Any]):
        """Handle incoming WebSocket messages."""
        try:
            message_type = data.get("type")
            
            if message_type == "ping":
                await ws.send_str(json.dumps({"type": "pong"}))
            elif message_type == "subscribe_logs":
                # Start log streaming for this connection
                await ws.send_str(json.dumps({"type": "log_subscription", "status": "active"}))
            elif message_type == "get_status":
                # Send current status
                status = await self.get_current_status()
                await ws.send_str(json.dumps({"type": "status_update", "data": status}))
            
        except Exception as e:
            logger.exception("WebSocket message handling failed")
            await ws.send_str(json.dumps({"error": str(e)}))
    
    async def broadcast_message(self, message: Dict[str, Any]):
        """Broadcast message to all connected WebSocket clients."""
        if not self.websockets:
            return
        
        message_str = json.dumps(message)
        disconnected = []
        
        for ws in self.websockets:
            try:
                await ws.send_str(message_str)
            except Exception:
                disconnected.append(ws)
        
        # Remove disconnected websockets
        for ws in disconnected:
            if ws in self.websockets:
                self.websockets.remove(ws)
    
    async def get_current_status(self) -> Dict[str, Any]:
        """Get current system status."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "active_bots": len(self.bot_processes),
            "websocket_connections": len(self.websockets),
            "ai_providers": self.ai_manager.get_provider_count() if self.ai_manager else 0
        }
    
    def get_html_content(self) -> str:
        """Get the complete HTML content for the web UI."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pump Bot Trading Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        
        .header h1 {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }
        
        .header p {
            color: #666;
            font-size: 1.1rem;
        }
        
        .status-bar {
            display: flex;
            gap: 16px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }
        
        .status-card {
            background: rgba(255, 255, 255, 0.9);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            padding: 16px;
            flex: 1;
            min-width: 200px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s ease;
        }
        
        .status-card:hover {
            transform: translateY(-2px);
        }
        
        .status-card h3 {
            font-size: 0.9rem;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }
        
        .status-card .value {
            font-size: 1.8rem;
            font-weight: 700;
            color: #333;
        }
        
        .status-card.healthy .value {
            color: #10b981;
        }
        
        .status-card.unhealthy .value {
            color: #ef4444;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 24px;
            margin-bottom: 24px;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        
        .card h2 {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 16px;
            color: #333;
        }
        
        .btn {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px 24px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            margin: 4px;
        }
        
        .btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 16px rgba(102, 126, 234, 0.3);
        }
        
        .btn:active {
            transform: translateY(0);
        }
        
        .btn.danger {
            background: linear-gradient(135deg, #ef4444, #dc2626);
        }
        
        .btn.success {
            background: linear-gradient(135deg, #10b981, #059669);
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        .form-group {
            margin-bottom: 16px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #374151;
        }
        
        .form-group input,
        .form-group select,
        .form-group textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #e5e7eb;
            border-radius: 8px;
            font-size: 1rem;
            transition: border-color 0.2s ease;
        }
        
        .form-group input:focus,
        .form-group select:focus,
        .form-group textarea:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        .log-container {
            background: #1f2937;
            color: #f9fafb;
            border-radius: 8px;
            padding: 16px;
            height: 300px;
            overflow-y: auto;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.9rem;
            line-height: 1.4;
        }
        
        .log-entry {
            margin-bottom: 4px;
            padding: 2px 0;
        }
        
        .log-entry.error {
            color: #fca5a5;
        }
        
        .log-entry.warning {
            color: #fcd34d;
        }
        
        .log-entry.info {
            color: #93c5fd;
        }
        
        .trades-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 16px;
        }
        
        .trades-table th,
        .trades-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }
        
        .trades-table th {
            background: #f9fafb;
            font-weight: 600;
            color: #374151;
        }
        
        .trades-table tr:hover {
            background: #f9fafb;
        }
        
        .ai-analysis {
            background: #f0f9ff;
            border: 2px solid #0ea5e9;
            border-radius: 8px;
            padding: 16px;
            margin-top: 16px;
        }
        
        .ai-analysis h4 {
            color: #0369a1;
            margin-bottom: 8px;
        }
        
        .recommendation {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9rem;
            text-transform: uppercase;
        }
        
        .recommendation.buy {
            background: #dcfce7;
            color: #166534;
        }
        
        .recommendation.sell {
            background: #fee2e2;
            color: #991b1b;
        }
        
        .recommendation.hold {
            background: #fef3c7;
            color: #92400e;
        }
        
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e5e7eb;
            border-radius: 4px;
            overflow: hidden;
            margin: 8px 0;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #10b981, #059669);
            transition: width 0.3s ease;
        }
        
        .config-list {
            max-height: 400px;
            overflow-y: auto;
        }
        
        .config-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            margin-bottom: 8px;
            background: #fafafa;
        }
        
        .config-item.enabled {
            border-color: #10b981;
            background: #f0fdf4;
        }
        
        .config-item.disabled {
            border-color: #ef4444;
            background: #fef2f2;
        }
        
        .config-info {
            flex: 1;
        }
        
        .config-name {
            font-weight: 600;
            color: #374151;
        }
        
        .config-platform {
            font-size: 0.9rem;
            color: #6b7280;
        }
        
        .config-actions {
            display: flex;
            gap: 8px;
        }
        
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .alert {
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 16px;
        }
        
        .alert.success {
            background: #dcfce7;
            color: #166534;
            border: 1px solid #bbf7d0;
        }
        
        .alert.error {
            background: #fee2e2;
            color: #991b1b;
            border: 1px solid #fecaca;
        }
        
        .alert.warning {
            background: #fef3c7;
            color: #92400e;
            border: 1px solid #fed7aa;
        }
        
        .tabs {
            display: flex;
            border-bottom: 2px solid #e5e7eb;
            margin-bottom: 24px;
        }
        
        .tab {
            padding: 12px 24px;
            background: none;
            border: none;
            font-size: 1rem;
            font-weight: 600;
            color: #6b7280;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            transition: all 0.2s ease;
        }
        
        .tab.active {
            color: #667eea;
            border-bottom-color: #667eea;
        }
        
        .tab:hover {
            color: #667eea;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 12px;
            }
            
            .grid {
                grid-template-columns: 1fr;
            }
            
            .status-bar {
                flex-direction: column;
            }
            
            .header h1 {
                font-size: 2rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Pump Bot Trading Dashboard</h1>
            <p>Advanced AI-powered trading bot for pump.fun and letsbonk.fun</p>
        </div>
        
        <div class="status-bar">
            <div class="status-card" id="rpc-status">
                <h3>RPC Status</h3>
                <div class="value">Checking...</div>
            </div>
            <div class="status-card" id="active-bots">
                <h3>Active Bots</h3>
                <div class="value">0</div>
            </div>
            <div class="status-card" id="ai-providers">
                <h3>AI Providers</h3>
                <div class="value">0</div>
            </div>
            <div class="status-card" id="connections">
                <h3>Connections</h3>
                <div class="value">0</div>
            </div>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="showTab('dashboard')">Dashboard</button>
            <button class="tab" onclick="showTab('bots')">Bot Management</button>
            <button class="tab" onclick="showTab('ai')">AI Analysis</button>
            <button class="tab" onclick="showTab('trades')">Trade History</button>
            <button class="tab" onclick="showTab('logs')">Logs</button>
            <button class="tab" onclick="showTab('settings')">Settings</button>
        </div>
        
        <!-- Dashboard Tab -->
        <div id="dashboard" class="tab-content active">
            <div class="grid">
                <div class="card">
                    <h2>📊 System Overview</h2>
                    <div id="system-overview">
                        <p>Loading system information...</p>
                    </div>
                </div>
                
                <div class="card">
                    <h2>🎯 Recent Activity</h2>
                    <div id="recent-activity">
                        <p>No recent activity</p>
                    </div>
                </div>
                
                <div class="card">
                    <h2>💰 Performance Summary</h2>
                    <div id="performance-summary">
                        <p>Loading performance data...</p>
                    </div>
                </div>
                
                <div class="card">
                    <h2>🤖 AI Insights</h2>
                    <div id="ai-insights">
                        <p>AI analysis will appear here</p>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Bot Management Tab -->
        <div id="bots" class="tab-content">
            <div class="card">
                <h2>🤖 Bot Configurations</h2>
                <button class="btn" onclick="refreshConfigs()">Refresh Configs</button>
                <button class="btn success" onclick="startAllBots()">Start All Enabled</button>
                <button class="btn danger" onclick="stopAllBots()">Stop All</button>
                
                <div id="config-list" class="config-list">
                    <p>Loading configurations...</p>
                </div>
            </div>
        </div>
        
        <!-- AI Analysis Tab -->
        <div id="ai" class="tab-content">
            <div class="grid">
                <div class="card">
                    <h2>🧠 AI Providers</h2>
                    <button class="btn" onclick="checkAIHealth()">Check Health</button>
                    <div id="ai-providers-list">
                        <p>Loading AI providers...</p>
                    </div>
                </div>
                
                <div class="card">
                    <h2>🔍 Token Analysis</h2>
                    <div class="form-group">
                        <label>Token Name:</label>
                        <input type="text" id="token-name" placeholder="Enter token name">
                    </div>
                    <div class="form-group">
                        <label>Token Symbol:</label>
                        <input type="text" id="token-symbol" placeholder="Enter token symbol">
                    </div>
                    <div class="form-group">
                        <label>Mint Address:</label>
                        <input type="text" id="token-mint" placeholder="Enter mint address">
                    </div>
                    <button class="btn" onclick="analyzeToken()">Analyze Token</button>
                    
                    <div id="ai-analysis-result"></div>
                </div>
            </div>
        </div>
        
        <!-- Trade History Tab -->
        <div id="trades" class="tab-content">
            <div class="card">
                <h2>📈 Trade History</h2>
                <button class="btn" onclick="refreshTrades()">Refresh</button>
                
                <div id="trades-container">
                    <p>Loading trade history...</p>
                </div>
            </div>
        </div>
        
        <!-- Logs Tab -->
        <div id="logs" class="tab-content">
            <div class="card">
                <h2>📋 System Logs</h2>
                <button class="btn" onclick="refreshLogs()">Refresh</button>
                <button class="btn" onclick="clearLogs()">Clear</button>
                
                <div class="log-container" id="log-container">
                    <div class="log-entry">Connecting to log stream...</div>
                </div>
            </div>
        </div>
        
        <!-- Settings Tab -->
        <div id="settings" class="tab-content">
            <div class="grid">
                <div class="card">
                    <h2>⚙️ AI Configuration</h2>
                    <div class="form-group">
                        <label>Ollama URL:</label>
                        <input type="text" id="ollama-url" value="http://localhost:11434">
                    </div>
                    <div class="form-group">
                        <label>Ollama Model:</label>
                        <input type="text" id="ollama-model" value="llama3.2">
                    </div>
                    <div class="form-group">
                        <label>LM Studio URL:</label>
                        <input type="text" id="lmstudio-url" value="http://localhost:1234">
                    </div>
                    <div class="form-group">
                        <label>Gemini API Key:</label>
                        <input type="password" id="gemini-key" placeholder="Enter Gemini API key">
                    </div>
                    <button class="btn" onclick="saveAISettings()">Save AI Settings</button>
                </div>
                
                <div class="card">
                    <h2>🔧 Trading Configuration</h2>
                    <div class="form-group">
                        <label>Default Buy Amount (SOL):</label>
                        <input type="number" id="buy-amount" value="0.001" step="0.001">
                    </div>
                    <div class="form-group">
                        <label>Default Slippage (%):</label>
                        <input type="number" id="slippage" value="30" step="1">
                    </div>
                    <div class="form-group">
                        <label>Priority Fee (microlamports):</label>
                        <input type="number" id="priority-fee" value="200000" step="1000">
                    </div>
                    <button class="btn" onclick="saveTradingSettings()">Save Trading Settings</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        let ws = null;
        let reconnectInterval = null;
        
        // Initialize WebSocket connection
        function initWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            ws = new WebSocket(wsUrl);
            
            ws.onopen = function() {
                console.log('WebSocket connected');
                updateConnectionStatus(true);
                if (reconnectInterval) {
                    clearInterval(reconnectInterval);
                    reconnectInterval = null;
                }
            };
            
            ws.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    handleWebSocketMessage(data);
                } catch (e) {
                    console.error('Failed to parse WebSocket message:', e);
                }
            };
            
            ws.onclose = function() {
                console.log('WebSocket disconnected');
                updateConnectionStatus(false);
                
                // Attempt to reconnect every 5 seconds
                if (!reconnectInterval) {
                    reconnectInterval = setInterval(() => {
                        console.log('Attempting to reconnect...');
                        initWebSocket();
                    }, 5000);
                }
            };
            
            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
            };
        }
        
        function handleWebSocketMessage(data) {
            switch (data.type) {
                case 'status_update':
                    updateStatusCards(data.data);
                    break;
                case 'bot_started':
                    addLogEntry(`Bot started: ${data.config_path}`, 'info');
                    refreshConfigs();
                    break;
                case 'bot_stopped':
                    addLogEntry(`Bot stopped: ${data.bot_id}`, 'warning');
                    refreshConfigs();
                    break;
                case 'log_entry':
                    addLogEntry(data.message, data.level);
                    break;
                case 'pong':
                    // Handle ping response
                    break;
            }
        }
        
        function updateConnectionStatus(connected) {
            const connectionsCard = document.getElementById('connections');
            if (connectionsCard) {
                const valueEl = connectionsCard.querySelector('.value');
                valueEl.textContent = connected ? 'Connected' : 'Disconnected';
                connectionsCard.className = `status-card ${connected ? 'healthy' : 'unhealthy'}`;
            }
        }
        
        function updateStatusCards(status) {
            // Update RPC status
            const rpcCard = document.getElementById('rpc-status');
            if (rpcCard) {
                const valueEl = rpcCard.querySelector('.value');
                valueEl.textContent = status.rpc_healthy ? 'Healthy' : 'Unhealthy';
                rpcCard.className = `status-card ${status.rpc_healthy ? 'healthy' : 'unhealthy'}`;
            }
            
            // Update active bots
            const botsCard = document.getElementById('active-bots');
            if (botsCard) {
                const valueEl = botsCard.querySelector('.value');
                valueEl.textContent = status.active_bots || 0;
            }
            
            // Update AI providers
            const aiCard = document.getElementById('ai-providers');
            if (aiCard) {
                const valueEl = aiCard.querySelector('.value');
                valueEl.textContent = status.ai_providers || 0;
            }
        }
        
        function showTab(tabName) {
            // Hide all tab contents
            const tabContents = document.querySelectorAll('.tab-content');
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Remove active class from all tabs
            const tabs = document.querySelectorAll('.tab');
            tabs.forEach(tab => tab.classList.remove('active'));
            
            // Show selected tab content
            const selectedContent = document.getElementById(tabName);
            if (selectedContent) {
                selectedContent.classList.add('active');
            }
            
            // Add active class to selected tab
            const selectedTab = event.target;
            selectedTab.classList.add('active');
            
            // Load tab-specific data
            switch (tabName) {
                case 'bots':
                    refreshConfigs();
                    break;
                case 'ai':
                    loadAIProviders();
                    break;
                case 'trades':
                    refreshTrades();
                    break;
                case 'logs':
                    refreshLogs();
                    break;
            }
        }
        
        async function refreshStatus() {
            try {
                const response = await fetch('/api/status');
                const status = await response.json();
                updateStatusCards(status);
            } catch (e) {
                console.error('Failed to refresh status:', e);
            }
        }
        
        async function refreshConfigs() {
            try {
                const response = await fetch('/api/configs');
                const data = await response.json();
                displayConfigs(data);
            } catch (e) {
                console.error('Failed to refresh configs:', e);
                document.getElementById('config-list').innerHTML = '<p class="alert error">Failed to load configurations</p>';
            }
        }
        
        function displayConfigs(data) {
            const container = document.getElementById('config-list');
            if (!container) return;
            
            if (data.valid_configs.length === 0) {
                container.innerHTML = '<p>No valid configurations found</p>';
                return;
            }
            
            let html = '';
            data.valid_configs.forEach(config => {
                const statusClass = config.enabled ? 'enabled' : 'disabled';
                html += `
                    <div class="config-item ${statusClass}">
                        <div class="config-info">
                            <div class="config-name">${config.name}</div>
                            <div class="config-platform">Platform: ${config.platform} | Listener: ${config.listener}</div>
                        </div>
                        <div class="config-actions">
                            ${config.enabled ? 
                                `<button class="btn success" onclick="startBot('${config.file}')">Start</button>` :
                                `<button class="btn" disabled>Disabled</button>`
                            }
                            <button class="btn danger" onclick="stopBot('${config.name}')">Stop</button>
                        </div>
                    </div>
                `;
            });
            
            container.innerHTML = html;
        }
        
        async function startBot(configPath) {
            try {
                const response = await fetch('/api/bot/start', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({config_path: configPath})
                });
                
                const result = await response.json();
                if (result.success) {
                    showAlert('Bot started successfully', 'success');
                } else {
                    showAlert(`Failed to start bot: ${result.error}`, 'error');
                }
            } catch (e) {
                showAlert(`Error starting bot: ${e.message}`, 'error');
            }
        }
        
        async function stopBot(botId) {
            try {
                const response = await fetch('/api/bot/stop', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({bot_id: botId})
                });
                
                const result = await response.json();
                if (result.success) {
                    showAlert('Bot stopped successfully', 'success');
                } else {
                    showAlert(`Failed to stop bot: ${result.error}`, 'error');
                }
            } catch (e) {
                showAlert(`Error stopping bot: ${e.message}`, 'error');
            }
        }
        
        async function loadAIProviders() {
            try {
                const response = await fetch('/api/ai/providers');
                const data = await response.json();
                displayAIProviders(data.providers);
            } catch (e) {
                console.error('Failed to load AI providers:', e);
            }
        }
        
        function displayAIProviders(providers) {
            const container = document.getElementById('ai-providers-list');
            if (!container) return;
            
            if (providers.length === 0) {
                container.innerHTML = '<p>No AI providers configured</p>';
                return;
            }
            
            let html = '';
            providers.forEach(provider => {
                html += `
                    <div class="config-item">
                        <div class="config-info">
                            <div class="config-name">${provider.name}</div>
                            <div class="config-platform">Model: ${provider.model} | URL: ${provider.url}</div>
                        </div>
                    </div>
                `;
            });
            
            container.innerHTML = html;
        }
        
        async function analyzeToken() {
            const name = document.getElementById('token-name').value;
            const symbol = document.getElementById('token-symbol').value;
            const mint = document.getElementById('token-mint').value;
            
            if (!name || !symbol) {
                showAlert('Please enter token name and symbol', 'warning');
                return;
            }
            
            try {
                showAlert('Analyzing token with AI...', 'info');
                
                const response = await fetch('/api/ai/analyze', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        name: name,
                        symbol: symbol,
                        mint: mint || '11111111111111111111111111111111',
                        market_data: {
                            price: 0.001,
                            market_cap: 1000,
                            volume: 500
                        }
                    })
                });
                
                const result = await response.json();
                displayAIAnalysis(result);
                
            } catch (e) {
                showAlert(`AI analysis failed: ${e.message}`, 'error');
            }
        }
        
        function displayAIAnalysis(analysis) {
            const container = document.getElementById('ai-analysis-result');
            if (!container) return;
            
            if (!analysis.success) {
                container.innerHTML = `<div class="alert error">Analysis failed: ${analysis.analysis}</div>`;
                return;
            }
            
            const html = `
                <div class="ai-analysis">
                    <h4>🤖 AI Analysis Result</h4>
                    <p><strong>Recommendation:</strong> <span class="recommendation ${analysis.recommendation}">${analysis.recommendation}</span></p>
                    <p><strong>Confidence:</strong> ${(analysis.confidence * 100).toFixed(1)}%</p>
                    <p><strong>Risk Score:</strong> ${(analysis.risk_score * 100).toFixed(1)}%</p>
                    
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${analysis.confidence * 100}%"></div>
                    </div>
                    
                    <h5>Key Reasoning:</h5>
                    <ul>
                        ${analysis.reasoning.map(reason => `<li>${reason}</li>`).join('')}
                    </ul>
                    
                    <details>
                        <summary>Full Analysis</summary>
                        <pre style="white-space: pre-wrap; margin-top: 8px;">${analysis.analysis}</pre>
                    </details>
                </div>
            `;
            
            container.innerHTML = html;
        }
        
        async function checkAIHealth() {
            try {
                const response = await fetch('/api/ai/health');
                const data = await response.json();
                
                let healthHtml = '<h4>AI Provider Health:</h4>';
                for (const [provider, healthy] of Object.entries(data.providers)) {
                    const status = healthy ? '✅ Healthy' : '❌ Unhealthy';
                    healthHtml += `<p><strong>${provider}:</strong> ${status}</p>`;
                }
                
                document.getElementById('ai-providers-list').innerHTML = healthHtml;
                
            } catch (e) {
                showAlert(`Health check failed: ${e.message}`, 'error');
            }
        }
        
        async function refreshTrades() {
            try {
                const response = await fetch('/api/trades');
                const data = await response.json();
                displayTrades(data.trades);
            } catch (e) {
                console.error('Failed to refresh trades:', e);
            }
        }
        
        function displayTrades(trades) {
            const container = document.getElementById('trades-container');
            if (!container) return;
            
            if (trades.length === 0) {
                container.innerHTML = '<p>No trades found</p>';
                return;
            }
            
            let html = `
                <table class="trades-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Action</th>
                            <th>Symbol</th>
                            <th>Platform</th>
                            <th>Price</th>
                            <th>Amount</th>
                            <th>TX Hash</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            
            trades.reverse().forEach(trade => {
                const time = new Date(trade.timestamp).toLocaleString();
                const txHash = trade.tx_hash ? 
                    `<a href="https://solscan.io/tx/${trade.tx_hash}" target="_blank">${trade.tx_hash.substring(0, 8)}...</a>` :
                    'N/A';
                
                html += `
                    <tr>
                        <td>${time}</td>
                        <td><span class="recommendation ${trade.action}">${trade.action}</span></td>
                        <td>${trade.symbol}</td>
                        <td>${trade.platform}</td>
                        <td>${trade.price ? trade.price.toFixed(8) : 'N/A'} SOL</td>
                        <td>${trade.amount ? trade.amount.toFixed(6) : 'N/A'}</td>
                        <td>${txHash}</td>
                    </tr>
                `;
            });
            
            html += '</tbody></table>';
            container.innerHTML = html;
        }
        
        async function refreshLogs() {
            try {
                const response = await fetch('/api/logs');
                const data = await response.json();
                displayLogs(data.logs);
            } catch (e) {
                console.error('Failed to refresh logs:', e);
            }
        }
        
        function displayLogs(logs) {
            const container = document.getElementById('log-container');
            if (!container) return;
            
            container.innerHTML = '';
            logs.forEach(log => {
                addLogEntry(log.trim(), 'info');
            });
            
            // Scroll to bottom
            container.scrollTop = container.scrollHeight;
        }
        
        function addLogEntry(message, level = 'info') {
            const container = document.getElementById('log-container');
            if (!container) return;
            
            const logEntry = document.createElement('div');
            logEntry.className = `log-entry ${level}`;
            logEntry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
            
            container.appendChild(logEntry);
            
            // Keep only last 200 entries
            while (container.children.length > 200) {
                container.removeChild(container.firstChild);
            }
            
            // Auto-scroll to bottom
            container.scrollTop = container.scrollHeight;
        }
        
        function clearLogs() {
            const container = document.getElementById('log-container');
            if (container) {
                container.innerHTML = '<div class="log-entry">Logs cleared</div>';
            }
        }
        
        function showAlert(message, type = 'info') {
            // Create alert element
            const alert = document.createElement('div');
            alert.className = `alert ${type}`;
            alert.textContent = message;
            
            // Insert at top of container
            const container = document.querySelector('.container');
            container.insertBefore(alert, container.firstChild);
            
            // Remove after 5 seconds
            setTimeout(() => {
                if (alert.parentNode) {
                    alert.parentNode.removeChild(alert);
                }
            }, 5000);
        }
        
        function saveAISettings() {
            // Save AI settings to localStorage for now
            const settings = {
                ollama_url: document.getElementById('ollama-url').value,
                ollama_model: document.getElementById('ollama-model').value,
                lmstudio_url: document.getElementById('lmstudio-url').value,
                gemini_key: document.getElementById('gemini-key').value
            };
            
            localStorage.setItem('ai_settings', JSON.stringify(settings));
            showAlert('AI settings saved', 'success');
        }
        
        function saveTradingSettings() {
            // Save trading settings to localStorage for now
            const settings = {
                buy_amount: document.getElementById('buy-amount').value,
                slippage: document.getElementById('slippage').value,
                priority_fee: document.getElementById('priority-fee').value
            };
            
            localStorage.setItem('trading_settings', JSON.stringify(settings));
            showAlert('Trading settings saved', 'success');
        }
        
        function loadSettings() {
            // Load AI settings
            const aiSettings = localStorage.getItem('ai_settings');
            if (aiSettings) {
                const settings = JSON.parse(aiSettings);
                document.getElementById('ollama-url').value = settings.ollama_url || 'http://localhost:11434';
                document.getElementById('ollama-model').value = settings.ollama_model || 'llama3.2';
                document.getElementById('lmstudio-url').value = settings.lmstudio_url || 'http://localhost:1234';
                document.getElementById('gemini-key').value = settings.gemini_key || '';
            }
            
            // Load trading settings
            const tradingSettings = localStorage.getItem('trading_settings');
            if (tradingSettings) {
                const settings = JSON.parse(tradingSettings);
                document.getElementById('buy-amount').value = settings.buy_amount || '0.001';
                document.getElementById('slippage').value = settings.slippage || '30';
                document.getElementById('priority-fee').value = settings.priority_fee || '200000';
            }
        }
        
        async function startAllBots() {
            showAlert('Starting all enabled bots...', 'info');
            // Implementation would start all enabled bots
        }
        
        async function stopAllBots() {
            showAlert('Stopping all bots...', 'warning');
            // Implementation would stop all running bots
        }
        
        // Initialize everything when page loads
        document.addEventListener('DOMContentLoaded', function() {
            initWebSocket();
            loadSettings();
            refreshStatus();
            
            // Refresh status every 10 seconds
            setInterval(refreshStatus, 10000);
            
            // Send ping every 30 seconds to keep WebSocket alive
            setInterval(() => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({type: 'ping'}));
                }
            }, 30000);
        });
    </script>
</body>
</html>
        """
    
    async def start_server(self):
        """Start the web server."""
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        
        logger.info(f"Web UI server started at http://{self.host}:{self.port}")
        
        # Keep server running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down web server...")
        finally:
            await runner.cleanup()


async def main():
    """Main entry point for the web UI server."""
    server = TradingBotWebUI()
    await server.start_server()


if __name__ == "__main__":
    asyncio.run(main())