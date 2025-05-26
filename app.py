from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort
from datetime import datetime
import os
import json
import shutil

app = Flask(__name__)
UPLOAD_FOLDER = "atualizacoes"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

CLIENTES_FILE = "clientes.json"

def carregar_clientes():
    if not os.path.exists(CLIENTES_FILE):
        return {}
    with open(CLIENTES_FILE, "r") as f:
        return json.load(f)

def salvar_clientes(clientes):
    with open(CLIENTES_FILE, "w") as f:
        json.dump(clientes, f, indent=4)

@app.route('/')
def index():
    clientes = carregar_clientes()
    agora = datetime.now()

    for cliente_id, dados in clientes.items():
        dados['online'] = False
        if dados.get('ultimo_ping'):
            try:
                dt = datetime.strptime(dados['ultimo_ping'], "%Y-%m-%d %H:%M:%S")
                if (agora - dt).total_seconds() < 300:
                    dados['online'] = True
            except Exception as e:
                print(f"Erro ao processar ping: {e}")

    return render_template('index.html', clientes=clientes)

@app.route('/upload_all', methods=['POST'])
def upload_all():
    if 'arquivo' not in request.files:
        return "Nenhum arquivo enviado", 400

    arquivo = request.files['arquivo']
    if not arquivo.filename.endswith('.rar'):
        return "Apenas .rar", 400

    nome_temporario = 'temp.rar'
    caminho_temp = os.path.join(UPLOAD_FOLDER, nome_temporario)
    arquivo.save(caminho_temp)

    clientes = carregar_clientes()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for cliente_id in clientes.keys():
        destino = os.path.join(UPLOAD_FOLDER, f"{cliente_id}.rar")
        shutil.copy(caminho_temp, destino)
        clientes[cliente_id]['ultima_atualizacao'] = agora

    os.remove(caminho_temp)
    salvar_clientes(clientes)
    return redirect(url_for('index'))

@app.route('/upload/<cliente_id>', methods=['POST'])
def upload(cliente_id):
    clientes = carregar_clientes()
    if cliente_id not in clientes:
        abort(404)

    if 'arquivo' not in request.files:
        return "Nenhum arquivo", 400
    arquivo = request.files['arquivo']
    if not arquivo.filename.endswith('.rar'):
        return "Apenas .rar", 400

    nome = f"{cliente_id}.rar"
    caminho = os.path.join(UPLOAD_FOLDER, nome)
    arquivo.save(caminho)
    clientes[cliente_id]['ultima_atualizacao'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    salvar_clientes(clientes)
    return redirect(url_for('index'))

@app.route('/delete/<cliente_id>', methods=['POST'])
def delete_cliente(cliente_id):
    clientes = carregar_clientes()
    if cliente_id in clientes:
        clientes.pop(cliente_id)
        salvar_clientes(clientes)
        rar = os.path.join(UPLOAD_FOLDER, f"{cliente_id}.rar")
        if os.path.exists(rar):
            os.remove(rar)
    return redirect(url_for('index'))

@app.route('/download/<cliente_id>')
def baixar_atualizacao(cliente_id):
    nome = f"{cliente_id}.rar"
    caminho = os.path.join(UPLOAD_FOLDER, nome)
    if not os.path.exists(caminho):
        return "Arquivo não encontrado", 404
    return send_from_directory(UPLOAD_FOLDER, nome, as_attachment=True)

@app.route('/ping', methods=['POST'])
def ping():
    data = request.get_json()
    mac = data.get('mac')
    if not mac:
        return {"error": "MAC não enviado"}, 400

    clientes = carregar_clientes()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if mac not in clientes:
        clientes[mac] = {
            "nome": f"Cliente {len(clientes)+1}",
            "mac": mac,
            "ultimo_ping": agora,
            "ultima_atualizacao": "---"
        }
    else:
        clientes[mac]['ultimo_ping'] = agora

    salvar_clientes(clientes)
    return {"message": "Ping recebido"}, 200

if __name__ == '__main__':
    app.run(debug=True)
