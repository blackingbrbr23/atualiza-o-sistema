import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Para mensagens flash

CLIENTES_FILE = "clientes.json"
UPLOAD_FOLDER = "static/uploads"

# Carregar clientes
def carregar_clientes():
    with open(CLIENTES_FILE, "r") as f:
        return json.load(f)

# Salvar clientes
def salvar_clientes(clientes):
    with open(CLIENTES_FILE, "w") as f:
        json.dump(clientes, f, indent=4)

@app.route("/", methods=["GET"])
def painel():
    clientes = carregar_clientes()
    return render_template("index.html", clientes=clientes)

@app.route("/upload/<cliente_id>", methods=["POST"])
def upload(cliente_id):
    clientes = carregar_clientes()

    if cliente_id not in clientes:
        flash("Cliente não encontrado!", "danger")
        return redirect(url_for("painel"))

    if "arquivo" not in request.files:
        flash("Nenhum arquivo enviado!", "danger")
        return redirect(url_for("painel"))

    arquivo = request.files["arquivo"]
    if arquivo.filename == "":
        flash("Nenhum arquivo selecionado!", "danger")
        return redirect(url_for("painel"))

    if not arquivo.filename.endswith(".zip"):
        flash("Apenas arquivos .zip são permitidos!", "danger")
        return redirect(url_for("painel"))

    # Criar pasta do cliente se não existir
    pasta_cliente = os.path.join(UPLOAD_FOLDER, cliente_id)
    os.makedirs(pasta_cliente, exist_ok=True)

    caminho_arquivo = os.path.join(pasta_cliente, "atualizacao.zip")
    arquivo.save(caminho_arquivo)

    # Atualizar data
    clientes[cliente_id]["ultima_atualizacao"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    salvar_clientes(clientes)

    flash(f"Atualização enviada para {clientes[cliente_id]['nome']}!", "success")
    return redirect(url_for("painel"))

@app.route("/atualizacao/<cliente_id>", methods=["GET"])
def baixar_atualizacao(cliente_id):
    pasta_cliente = os.path.join(UPLOAD_FOLDER, cliente_id)
    arquivo = os.path.join(pasta_cliente, "atualizacao.zip")

    if not os.path.exists(arquivo):
        return "Nenhuma atualização disponível.", 404

    return send_from_directory(pasta_cliente, "atualizacao.zip", as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
