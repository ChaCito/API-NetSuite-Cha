from flask import Flask, Response, request, jsonify
import requests
import time
import uuid
import hmac
import hashlib
import base64
import urllib.parse

app = Flask(__name__)

# 🔐 Credenciales NetSuite
ACCOUNT_ID = '9292634_SB1'
CONSUMER_KEY = '8f604dd13aac2c78787439710739792dfbdc97cd93c08ebbe10a4513ec66ea30'
CONSUMER_SECRET = '8b0d4bbe20f4edd675c79ab00ba9a2298abe008cdcbc8b7ef22d193848cfe6a0'
TOKEN_ID = '328707364f8b42010ff3ef054055d39a72b801241385377ef83c87d35e5c0f21'
TOKEN_SECRET = 'f78ade34700af6fdf090248fa6ce45f2bce9587b70c1be30e8e12b554a33ca7e'

# 🌐 URL base del RESTlet
url_base = 'https://9292634-sb1.restlets.api.netsuite.com/app/site/hosting/restlet.nl'
http_method = 'GET'

@app.route('/netsuite/data')
def get_netsuite_data():
    # 🔧 Parámetros dinámicos desde la URL
    script = request.args.get("script", "2265")
    deploy = request.args.get("deploy", "1")
    search_id = request.args.get("searchId", "2931")

    # 🔁 Query para NetSuite
    query_params = {
        "script": script,
        "deploy": deploy,
        "searchId": search_id
    }

    # ⏱️ Tiempo y nonce
    nonce = uuid.uuid4().hex
    timestamp = str(int(time.time()))

    # 🧾 Parámetros OAuth
    oauth_params = {
        "oauth_consumer_key": CONSUMER_KEY,
        "oauth_token": TOKEN_ID,
        "oauth_nonce": nonce,
        "oauth_timestamp": timestamp,
        "oauth_signature_method": "HMAC-SHA256",
        "oauth_version": "1.0"
    }

    # 🔁 Combinar todos los parámetros
    all_params = {**query_params, **oauth_params}

    # ✅ Ordenar alfabéticamente
    sorted_items = sorted(all_params.items(), key=lambda x: x[0])
    encoded_items = [(urllib.parse.quote(k, safe=''), urllib.parse.quote(v, safe='')) for k, v in sorted_items]
    param_string = '&'.join(f"{k}={v}" for k, v in encoded_items)

    # 🧱 Base String
    encoded_url = urllib.parse.quote(url_base, safe='')
    encoded_params = urllib.parse.quote(param_string, safe='')
    base_string = f"{http_method}&{encoded_url}&{encoded_params}"

    # 🔐 Firmar
    signing_key = f"{urllib.parse.quote(CONSUMER_SECRET)}&{urllib.parse.quote(TOKEN_SECRET)}"
    digest = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha256).digest()
    signature = base64.b64encode(digest).decode()

    # 📑 Header OAuth
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

    # 🧾 Headers y URL final
    headers = {
        'Authorization': oauth_header,
        'Content-Type': 'application/json'
    }

    full_url = f"{url_base}?script={script}&deploy={deploy}&searchId={search_id}"

    # 📡 Llamada
    response = requests.get(full_url, headers=headers)

    if response.status_code == 200:
        try:
            data = response.json()
            if "contentBase64" in data:
                decoded = base64.b64decode(data["contentBase64"]).decode("utf-8")
                return Response(decoded, mimetype="text/csv")
            else:
                return jsonify({"error": "No se encontró 'contentBase64' en la respuesta"}), 400
        except Exception as e:
            return jsonify({"error": "Error procesando respuesta", "detalle": str(e)}), 500
    else:
        return jsonify({"error": "Error al consultar NetSuite", "detalle": response.text}), response.status_code

if __name__ == '__main__':
    app.run(port=5001)
