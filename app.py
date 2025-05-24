from flask import Flask, render_template, request, redirect, url_for, send_file
import json
import os
from datetime import datetime

app = Flask(__name__)

CLIENTES_JSON = 'clientes.json'
UPLOADS_DIR = 'uploads'
os.makedirs(UPLOADS_DIR, exist_ok=True)

def carregar_clientes():
    if not os.path.exists(CLIENTES_JSON):
        return {}
    with open(CLIENTES_JSON, 'r') as f:
        return json.load(f)

def salvar_clientes(clientes):
    with open(CLIENTES_JSON, 'w') as f:
        json.dump(clientes, f, indent=4)

@app.route('/', methods=['GET'])
def painel():
    clientes = carregar_clientes()
    return render_template('index.html', clientes=clientes)

@app.route('/ping', methods=['POST'])
def ping():
    data = request.get_json()
    mac = data.get('mac')
    if not mac:
        return 'MAC inválido', 400

    clientes = carregar_clientes()
    if mac not in clientes:
        clientes[mac] = {"ultimo_update": None, "online": True}
    else:
        clientes[mac]['online'] = True

    salvar_clientes(clientes)
    return 'OK', 200

@app.route('/upload/<mac>', methods=['POST'])
def upload(mac):
    if 'arquivo' not in request.files:
        return redirect(url_for('painel'))

    arquivo = request.files['arquivo']
    if arquivo.filename == '':
        return redirect(url_for('painel'))

    caminho = os.path.join(UPLOADS_DIR, f'{mac}.zip')
    arquivo.save(caminho)

    clientes = carregar_clientes()
    if mac in clientes:
        clientes[mac]['ultimo_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        salvar_clientes(clientes)

    return redirect(url_for('painel'))

@app.route('/download/<mac>', methods=['GET'])
def download(mac):
    caminho = os.path.join(UPLOADS_DIR, f'{mac}.zip')
    if os.path.exists(caminho):
        return send_file(caminho, as_attachment=True)
    return 'Arquivo não encontrado', 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
