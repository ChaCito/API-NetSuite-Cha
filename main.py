from fastapi import FastAPI, Response, HTTPException, Query, Request
import os, time, uuid, hmac, hashlib, base64, urllib.parse, requests
from dotenv import load_dotenv
import logging

# 📦 Cargar .env
load_dotenv()

# 📝 Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("netsuite-api")

# 🚀 App FastAPI
app = FastAPI(
    title="API NetSuite Proxy",
    description="Consulta búsquedas guardadas de NetSuite vía RESTlet usando tipo (clientes, ventas...)",
    version="1.0.0"
)

# 🔐 Credenciales desde .env
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
CONSUMER_KEY = os.getenv("CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("CONSUMER_SECRET")
TOKEN_ID = os.getenv("TOKEN_ID")
TOKEN_SECRET = os.getenv("TOKEN_SECRET")

# 🌐 URL RESTlet base
url_base = 'https://9292634.restlets.api.netsuite.com/app/site/hosting/restlet.nl'

# 📋 Diccionario de búsquedas disponibles
BUSQUEDAS = {
    "clientes": {"script": "2582", "deploy": "1", "searchId": "3575"},
    "ventas": {"script": "2582", "deploy": "1", "searchId": "1481"},
    "transacciones": {"script": "2582", "deploy": "1", "searchId": "4041"},
    "cuentasporpagar" : {"script": "2582", "deploy": "1", "searchId": "3685"}
    "cobranza" : {"script": "2582", "deploy": "1", "searchId": "2592"}
}

@app.get("/netsuite/data", summary="Consulta búsqueda guardada por tipo", tags=["NetSuite"])
async def get_netsuite_data(
    request: Request,
    tipo: str = Query(..., description="Nombre de la búsqueda guardada (clientes, ventas, transacciones)")
):
    """
    Devuelve un CSV a partir de una búsqueda guardada de NetSuite,
    identificada por un alias (`tipo`). También registra IP y agente del consumidor.
    """

    # 🔍 Registrar IP y User-Agent
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "desconocido")
    logger.info(f"📥 Petición de tipo='{tipo}' desde IP={client_ip} UA='{user_agent}'")

    if tipo not in BUSQUEDAS:
        logger.warning(f"Tipo inválido solicitado: {tipo}")
        raise HTTPException(status_code=404, detail=f"Tipo '{tipo}' no registrado")

    config = BUSQUEDAS[tipo]
    script, deploy, searchId = config["script"], config["deploy"], config["searchId"]

    logger.info(f"🎯 Ejecutando búsqueda tipo='{tipo}' con searchId={searchId}")

    # 🔐 OAuth
    nonce = uuid.uuid4().hex
    timestamp = str(int(time.time()))

    oauth_params = {
        "oauth_consumer_key": CONSUMER_KEY,
        "oauth_token": TOKEN_ID,
        "oauth_nonce": nonce,
        "oauth_timestamp": timestamp,
        "oauth_signature_method": "HMAC-SHA256",
        "oauth_version": "1.0"
    }

    query_params = {"script": script, "deploy": deploy, "searchId": searchId}
    all_params = {**query_params, **oauth_params}
    sorted_items = sorted(all_params.items())
    encoded_items = [(urllib.parse.quote(k, safe=''), urllib.parse.quote(v, safe='')) for k, v in sorted_items]
    param_string = '&'.join(f"{k}={v}" for k, v in encoded_items)

    base_string = f"GET&{urllib.parse.quote(url_base, safe='')}&{urllib.parse.quote(param_string, safe='')}"
    signing_key = f"{urllib.parse.quote(CONSUMER_SECRET)}&{urllib.parse.quote(TOKEN_SECRET)}"
    signature = base64.b64encode(hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha256).digest()).decode()

    oauth_header = (
        f'OAuth realm="{ACCOUNT_ID}", '
        f'oauth_consumer_key="{CONSUMER_KEY}", '
        f'oauth_token="{TOKEN_ID}", '
        f'oauth_nonce="{nonce}", '
        f'oauth_timestamp="{timestamp}", '
        f'oauth_signature_method="HMAC-SHA256", '
        f'oauth_version="1.0", '
        f'oauth_signature="{urllib.parse.quote(signature)}"'
    )

    headers = {'Authorization': oauth_header, 'Content-Type': 'application/json'}
    full_url = f"{url_base}?script={script}&deploy={deploy}&searchId={searchId}"

    logger.info(f"🌐 Llamando a NetSuite: {full_url}")
    response = requests.get(full_url, headers=headers)
    logger.info(f"📦 Respuesta NetSuite: {response.status_code}")

    if response.status_code == 200:
        try:
            data = response.json()
            if "contentBase64" in data:
                decoded = base64.b64decode(data["contentBase64"]).decode("utf-8")
                logger.info(f"✅ Búsqueda '{tipo}' entregada correctamente")
                return Response(content=decoded, media_type="text/csv")
            else:
                logger.error("❌ Falta 'contentBase64' en respuesta")
                raise HTTPException(status_code=400, detail="Respuesta inválida: falta contentBase64")
        except Exception as e:
            logger.exception("❌ Error procesando la respuesta")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        logger.error(f"❌ Error NetSuite: {response.text}")
        raise HTTPException(status_code=response.status_code, detail=response.text)
