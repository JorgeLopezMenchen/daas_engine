from fastapi import FastAPI, HTTPException
from typing import Dict, Any

# Instanciamos la aplicación FastAPI
app = FastAPI(
    title="DaaS Engine - B2B API",
    description="API de Señales Cuantitativas y Cinemáticas Filtradas por Kalman",
    version="1.0.0"
)

# Diccionario en memoria para almacenar el último estado procesado de cada activo.
# El Orquestador actualizará este diccionario, y la API lo leerá.
estado_mercado: Dict[str, Any] = {}

@app.get("/")
async def root():
    return {"mensaje": "DaaS Engine Operativo. Consulta /docs para la documentación."}

@app.get("/api/v1/market/state", summary="Obtener estado actual de todos los activos")
async def get_market_state():
    """
    Devuelve el último precio, velocidad, aceleración y clasificación GNC
    de todo el universo cinético que se está monitoreando.
    """
    if not estado_mercado:
        raise HTTPException(status_code=503, detail="Servicio no disponible o sin datos aún.")
    return {"status": "ok", "data": estado_mercado}

@app.get("/api/v1/market/ticker/{ticker}", summary="Obtener estado de un activo específico")
async def get_ticker_state(ticker: str):
    """
    Devuelve la matriz cinemática de un ticker en particular (Ej: NVDA).
    """
    ticker = ticker.upper()
    if ticker not in estado_mercado:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} no monitorizado actualmente.")
    
    return {"status": "ok", "ticker": ticker, "data": estado_mercado[ticker]}