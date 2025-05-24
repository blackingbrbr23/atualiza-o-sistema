from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for
from datetime import datetime
import json
import os

app = Flask(__name__)
ARQUIVO_JSON = "clientes.json"
PASTA_ATUALIZACOES = "atualizacoes"  # onde ficam os arquivos .zip enviados


def carregar_clientes():
    if not os.path.exists(ARQUIVO_JSON):
        return {}
    with open(ARQUIVO_JSON, "r") as f:
        return json.load(f)

def salvar_clientes(clientes):
    with open(ARQUIVO_JSON, "w") as f:
        json.dump(clientes, f, indent=4)

@app.context_processor
def inject_now():
    from datetime import datetime
    return {'now': datetime.now()}

@app.route("/")
def index():
    clientes = carregar_clientes()
    return render_template("index.html", clientes=clientes)

@app.route("/ping", methods=["POST"])
def ping():
    data = request.get_json()
    mac = data.get("mac")

    if not mac:
        return jsonify({"error": "mac é obrigatório"}), 400

    clientes = carregar_clientes()
    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    mac_existente = False
    for cliente_id, c in clientes.items():
        if c.get("mac") == mac:
            c["ultimo_ping"] = agora_str
            mac_existente = True
            break

    if not mac_existente:
        # Associa MAC a 1º cliente sem MAC
        for cliente_id, c in clientes.items():
            if not c.get("mac"):
                c["mac"] = mac
                c["ultimo_ping"] = agora_str
                mac_existente = True
                break

    if not mac_existente:
        return jsonify({"error": "Sem clientes livres para associar esse MAC"}), 404

    salvar_clientes(clientes)
    return jsonify({"status": "ok"}), 200


@app.route("/upload/<cliente_id>", methods=["POST"])
def upload(cliente_id):
    if "arquivo" not in request.files:
        return "Nenhum arquivo enviado", 400
    arquivo = request.files["arquivo"]

    if arquivo.filename == "":
        return "Arquivo vazio", 400

    if not arquivo.filename.endswith(".zip"):
        return "Apenas arquivos .zip são aceitos", 400

    pasta_cliente = os.path.join(PASTA_ATUALIZACOES, cliente_id)
    os.makedirs(pasta_cliente, exist_ok=True)
    caminho = os.path.join(pasta_cliente, arquivo.filename)
    arquivo.save(caminho)

    clientes = carregar_clientes()
    clientes[cliente_id]["ultima_atualizacao"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    salvar_clientes(clientes)

    return redirect(url_for("index"))

@app.route("/download/<cliente_id>")
def baixar_atualizacao(cliente_id):
    pasta_cliente = os.path.join(PASTA_ATUALIZACOES, cliente_id)
    if not os.path.exists(pasta_cliente):
        return "Nenhuma atualização disponível", 404

    arquivos = os.listdir(pasta_cliente)
    if not arquivos:
        return "Nenhuma atualização disponível", 404

    # Serve o arquivo .zip mais recente
    arquivos.sort(reverse=True)
    return send_from_directory(pasta_cliente, arquivos[0], as_attachment=True)

if __name__ == "__main__":
    if not os.path.exists(PASTA_ATUALIZACOES):
        os.makedirs(PASTA_ATUALIZACOES)
    app.run(debug=True, host="0.0.0.0")
