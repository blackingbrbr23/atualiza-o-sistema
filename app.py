from flask import Flask, render_template, request, send_file, redirect, url_for
from datetime import datetime
import os
import json

app = Flask(__name__)

# Caminhos
DADOS_JSON = 'clientes.json'
PASTA_ATUALIZACOES = 'atualizacoes'

# Criar a pasta de atualizações se não existir
os.makedirs(PASTA_ATUALIZACOES, exist_ok=True)

# Função para carregar os dados
def carregar_clientes():
    if os.path.exists(DADOS_JSON):
        with open(DADOS_JSON, 'r') as f:
            return json.load(f)
    return {}

# Função para salvar os dados
def salvar_clientes(clientes):
    with open(DADOS_JSON, 'w') as f:
        json.dump(clientes, f, indent=4)

# Rota principal (painel)
@app.route('/')
def index():
    clientes = carregar_clientes()
    return render_template('index.html', clientes=clientes, now=datetime.now)

# Rota que o cliente chama ao executar o programa pela primeira vez
@app.route('/ping', methods=['POST'])
def ping():
    dados = request.get_json()
    mac = dados.get('mac')

    if not mac:
        return "MAC não fornecido", 400

    clientes = carregar_clientes()
    
    if mac not in clientes:
        clientes[mac] = {
            "mac": mac,
            "nome": f"Cliente {len(clientes)+1}",
            "ultimo_ping": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ultima_atualizacao": "---"
        }
    else:
        clientes[mac]["ultimo_ping"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    salvar_clientes(clientes)
    return "Ping registrado", 200

# Rota para enviar atualização .zip para um cliente específico
@app.route('/upload/<cliente_id>', methods=['POST'])
def upload(cliente_id):
    if 'arquivo' not in request.files:
        return "Nenhum arquivo enviado", 400

    arquivo = request.files['arquivo']
    if arquivo.filename == '':
        return "Nome de arquivo inválido", 400

    caminho_arquivo = os.path.join(PASTA_ATUALIZACOES, f"{cliente_id}.zip")
    arquivo.save(caminho_arquivo)

    clientes = carregar_clientes()
    if cliente_id in clientes:
        clientes[cliente_id]["ultima_atualizacao"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        salvar_clientes(clientes)

    return redirect(url_for('index'))

# Rota para baixar atualização
@app.route('/baixar/<mac>')
def baixar_atualizacao(mac):
    caminho_arquivo = os.path.join(PASTA_ATUALIZACOES, f"{mac}.zip")
    if os.path.exists(caminho_arquivo):
        return send_file(caminho_arquivo, as_attachment=True)
    return "Arquivo não encontrado", 404

if __name__ == '__main__':
    app.run(debug=True)
