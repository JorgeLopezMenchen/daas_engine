import os
import asyncio
import logging
import uvicorn
from dotenv import load_dotenv
from ingestion.streamer import MarketStreamer
from core.kalman import KalmanRegimeFilter
from api.server import app, estado_mercado

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("MotorDaaS")

async def daas_consumer(queue: asyncio.Queue, radares: dict):
    logger.info("Consumidor Cuantitativo iniciado. Conectando al motor API...")
    
    while True:
        tick = await queue.get()
        
        symbol = tick.get("S")
        price = tick.get("c") 
        
        if symbol in radares:
            radar = radares[symbol]
            precio_real, vel, acel = radar.update(price)
            
            if acel > 0 and vel > 0:
                estado = "🔥 IGNICIÓN"
            elif vel > 0 and acel <= 0:
                estado = "🟢 CRUCERO"
            elif vel < 0 and acel < 0:
                estado = "🚨 COLAPSO"
            else:
                estado = "🔴 DEFENSIVO"
                
            # --- NUEVO: En lugar de solo imprimir, guardamos el estado en la API ---
            # Esto permite a clientes B2B consultar el estado en vivo.
            estado_mercado[symbol] = {
                "precio": round(precio_real, 2),
                "velocidad": round(vel, 3),
                "aceleracion": round(acel, 3),
                "regimen": estado
            }
            
            logger.info(f"[{symbol:<4}] Estado actualizado en la API.")
        
        queue.task_done()

async def run_api_server():
    """Lanza el servidor web Uvicorn de forma asíncrona dentro del mismo loop."""
    config = uvicorn.Config(app=app, host="127.0.0.1", port=8000, log_level="error")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    load_dotenv()
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        logger.error("Credenciales no encontradas.")
        return

    data_queue = asyncio.Queue(maxsize=10000)
    tickers = ["QQQ", "AAPL", "NVDA", "MSFT"]
    radares_gnc = {ticker: KalmanRegimeFilter() for ticker in tickers}

    streamer = MarketStreamer(api_key, secret_key, tickers, data_queue)

    logger.info("Iniciando infraestructura completa (Ingesta + Procesamiento + API)...")
    
    # Levantamos los 3 pilares del negocio concurrentemente
    tarea_ingesta = asyncio.create_task(streamer.start_streaming())
    tarea_procesamiento = asyncio.create_task(daas_consumer(data_queue, radares_gnc))
    tarea_api = asyncio.create_task(run_api_server())

    try:
        await asyncio.gather(tarea_ingesta, tarea_procesamiento, tarea_api)
    except asyncio.CancelledError:
        logger.info("Sistema cancelado.")
    finally:
        streamer.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Apagando DaaS Engine...")