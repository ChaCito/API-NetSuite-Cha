from fastapi import FastAPI, Response, HTTPException
import os, time, uuid, hmac, hashlib, base64, urllib.parse, requests
from dotenv import load_dotenv
import logging

load_dotenv()
app = FastAPI()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,  # Puedes cambiar a DEBUG para más detalle
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s'
)
logger = logging.getLogger("netsuite-api")

ACCOUNT_ID = os.getenv("ACCOUNT_ID")
CONSUMER_KEY = os.getenv("CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("CONSUMER_SECRET")
TOKEN_ID = os.getenv("TOKEN_ID")
TOKEN_SECRET = os.getenv("TOKEN_SECRET")

url_base = 'https://9292634-sb1.restlets.api.netsuite.com/app/site/hosting/restlet.nl'

@app.get("/netsuite/data")
async def get_netsuite_data(script: str = "2265", deploy: str = "1", searchId: str = "2931"):
    logger.info(f"Request received with params: script={script}, deploy={deploy}, searchId={searchId}")

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

    logger.info(f"Calling NetSuite URL: {full_url}")
    logger.debug(f"Request headers: {headers}")

    response = requests.get(full_url, headers=headers)

    logger.info(f"NetSuite response status: {response.status_code}")

    if response.status_code == 200:
        try:
            data = response.json()
            logger.debug(f"Response JSON keys: {list(data.keys())}")
            if "contentBase64" in data:
                decoded = base64.b64decode(data["contentBase64"]).decode("utf-8")
                logger.info(f"Decoded contentBase64 length: {len(decoded)} chars")
                return Response(content=decoded, media_type="text/csv")
            else:
                logger.error("No se encontró 'contentBase64' en la respuesta")
                raise HTTPException(status_code=400, detail="No se encontró contentBase64")
        except Exception as e:
            logger.error(f"Error procesando respuesta JSON: {e}")
            raise HTTPException(status_code=500, detail=f"Error procesando respuesta: {str(e)}")
    else:
        logger.error(f"Error NetSuite: {response.text}")
        raise HTTPException(status_code=response.status_code, detail=f"Error NetSuite: {response.text}")
