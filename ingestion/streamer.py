import asyncio
import json
import logging
from typing import List
import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("IngestaDaaS")

class MarketStreamer:
    """Productor Asíncrono de WebSockets."""
    def __init__(self, api_key: str, secret_key: str, tickers: List[str], data_queue: asyncio.Queue):
        self.api_key = api_key
        self.secret_key = secret_key
        self.tickers = tickers
        self.queue = data_queue
        self.ws_url = "wss://stream.data.alpaca.markets/v2/iex"
        self._is_running = False

    async def _authenticate(self, ws) -> bool:
        # 1. Consumir el mensaje automático de bienvenida ("connected")
        welcome_response = await ws.recv()
        welcome_data = json.loads(welcome_response)
        if not (welcome_data[0].get("T") == "success" and welcome_data[0].get("msg") == "connected"):
            logger.error(f"Handshake fallido, servidor no listo: {welcome_data}")
            return False

        # 2. Enviar las credenciales de autorización
        auth_message = {
            "action": "auth",
            "key": self.api_key,
            "secret": self.secret_key
        }
        await ws.send(json.dumps(auth_message))
        
        # 3. Leer la respuesta de la autenticación
        auth_response = await ws.recv()
        auth_data = json.loads(auth_response)
        
        if auth_data[0].get("T") == "success" and auth_data[0].get("msg") == "authenticated":
            logger.info("Autenticación completada con éxito.")
            return True
            
        logger.error(f"Fallo de autenticación: {auth_data}")
        return False

    async def _subscribe(self, ws):
        sub_message = {
            "action": "subscribe",
            "bars": self.tickers
        }
        await ws.send(json.dumps(sub_message))
        response = await ws.recv()
        logger.info(f"Suscripción confirmada: {response}")

    async def start_streaming(self):
        self._is_running = True
        reconnect_delay = 1
        max_delay = 60

        while self._is_running:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    logger.info("🔌 Conexión TCP establecida con Alpaca.")
                    
                    if not await self._authenticate(ws):
                        break
                        
                    await self._subscribe(ws)
                    reconnect_delay = 1

                    while self._is_running:
                        message = await ws.recv()
                        payload = json.loads(message)
                        
                        for tick in payload:
                            if tick.get("T") == "b":
                                try:
                                    self.queue.put_nowait(tick)
                                except asyncio.QueueFull:
                                    logger.warning("⚠️ DROP DE PAQUETE: Cola saturada.")
                                    
            except (ConnectionClosedError, ConnectionClosedOK, OSError) as e:
                logger.error(f"Caída de WebSocket: {e}")
            except Exception as e:
                logger.critical(f"Excepción crítica: {e}", exc_info=True)
            
            if self._is_running:
                logger.info(f"Reconectando en {reconnect_delay} seg...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_delay)

    def stop(self):
        logger.info("Deteniendo streamer...")
        self._is_running = False