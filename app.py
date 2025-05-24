from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort
from datetime import datetime
import os
import json

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

    # Verifica quem está online (ping dentro dos últimos 5 minutos)
    for cliente_id, dados in clientes.items():
        dados['online'] = False
        if 'ultimo_ping' in dados and dados['ultimo_ping']:
            try:
                dt_ping = datetime.strptime(dados['ultimo_ping'], "%Y-%m-%d %H:%M:%S")
                if (agora - dt_ping).total_seconds() < 300:
                    dados['online'] = True
            except Exception as e:
                print(f"Erro ao processar data de ping: {e}")

    return render_template('index.html', clientes=clientes)

@app.route('/upload/<cliente_id>', methods=['POST'])
def upload(cliente_id):
    clientes = carregar_clientes()
    if cliente_id not in clientes:
        abort(404)

    if 'arquivo' not in request.files:
        return "Nenhum arquivo enviado", 400

    arquivo = request.files['arquivo']
    if arquivo.filename == '':
        return "Nenhum arquivo selecionado", 400

    if not arquivo.filename.endswith('.exe'):
        return "Apenas arquivos .exe são permitidos", 400

    nome_arquivo = f"{cliente_id}.exe"
    caminho = os.path.join(UPLOAD_FOLDER, nome_arquivo)
    arquivo.save(caminho)

    clientes[cliente_id]['ultima_atualizacao'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    salvar_clientes(clientes)

    return redirect(url_for('index'))

@app.route('/download/<cliente_id>')
def baixar_atualizacao(cliente_id):
    nome_arquivo = f"{cliente_id}.zip"
    caminho = os.path.join(UPLOAD_FOLDER, nome_arquivo)
    if not os.path.exists(caminho):
        return "Arquivo não encontrado", 404
    return send_from_directory(UPLOAD_FOLDER, nome_arquivo, as_attachment=True)

@app.route('/ping', methods=['POST'])
def ping():
    data = request.get_json()
    mac = data.get('mac')
    if not mac:
        return {"error": "MAC não enviado"}, 400

    clientes = carregar_clientes()

    if mac not in clientes:
        # Adiciona cliente novo com MAC e nome genérico
        clientes[mac] = {
            "nome": f"Cliente {len(clientes)+1}",
            "mac": mac,
            "ultimo_ping": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ultima_atualizacao": "---"
        }
    else:
        # Atualiza último ping
        clientes[mac]['ultimo_ping'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    salvar_clientes(clientes)
    return {"message": "Ping recebido"}, 200

if __name__ == '__main__':
    app.run(debug=True)
