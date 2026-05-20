import os
import json
import httpx
import boto3
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from pii_filter import redactar_pii
import redis.asyncio as aioredis

app = FastAPI(title='OmniBank NLP Agent', version='1.0.0')

# Exponer métricas para Prometheus en /metrics
Instrumentator().instrument(app).expose(app)

# ── Configuración desde variables de entorno ──────────
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
LLM_MODEL  = os.getenv('LLM_MODEL', 'gpt-3.5-turbo')

# ── Conexión Redis ────────────────────────────────────
pool = aioredis.ConnectionPool.from_url(
    f'redis://{REDIS_HOST}:{REDIS_PORT}',
    max_connections=20
)
redis_client = aioredis.Redis(connection_pool=pool)

# ── Obtener API Key de Secrets Manager ───────────────
def obtener_api_key() -> str:
    try:
        sm = boto3.client('secretsmanager', region_name=AWS_REGION)
        secret = sm.get_secret_value(SecretId='omnibank/llm-api-key')
        return json.loads(secret['SecretString'])['api_key']
    except Exception:
        return os.getenv('LLM_API_KEY', '')   # fallback para desarrollo local

LLM_API_KEY = obtener_api_key()

# ── Endpoints ─────────────────────────────────────────
@app.get('/health')
async def health():
    return {'status': 'ok', 'service': 'omnibank-agent', 'version': '1.0.0'}

@app.post('/chat')
async def chat(request: Request):
    body = await request.json()
    session_id  = body.get('session_id', 'anonimo')
    mensaje_raw = body.get('message', '').strip()

    if not mensaje_raw:
        raise HTTPException(status_code=400, detail='El campo message es requerido')

    # ❶ REDACTAR PII — siempre antes del LLM
    redaccion = redactar_pii(mensaje_raw)
    mensaje_seguro = redaccion.texto_redactado

    # ❷ Recuperar historial de Redis (TTL 15 min)
    clave_historial = f'sesion:{session_id}:historial'
    historial_raw = await redis_client.get(clave_historial)
    historial = json.loads(historial_raw) if historial_raw else []

    # ❸ Llamar al LLM con el texto ya limpio
    mensajes = [
        {'role': 'system', 'content': 'Eres el asistente virtual de OmniBank. Responde en español de manera clara y concisa sobre productos bancarios.'},
        *historial,
        {'role': 'user', 'content': mensaje_seguro},
    ]

    async with httpx.AsyncClient(timeout=15.0) as cliente:
        respuesta = await cliente.post(
            'https://api.openai.com/v1/chat/completions',
            headers={'Authorization': f'Bearer {LLM_API_KEY}'},
            json={'model': LLM_MODEL, 'messages': mensajes, 'max_tokens': 400},
        )
    respuesta.raise_for_status()
    respuesta_texto = respuesta.json()['choices'][0]['message']['content']

    # ❹ Guardar en Redis (últimos 10 turnos, TTL 15 min)
    historial.append({'role': 'user',      'content': mensaje_seguro})
    historial.append({'role': 'assistant', 'content': respuesta_texto})
    await redis_client.setex(clave_historial, 900, json.dumps(historial[-10:]))

    return {
        'respuesta':    respuesta_texto,
        'session_id':   session_id,
        'pii_redactada': redaccion.pii_encontrada,
        'tipos_pii':    redaccion.tipos_removidos,
    }
