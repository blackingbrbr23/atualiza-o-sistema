from flask import Flask, request, jsonify, render_template
import json
import os
import time

app = Flask(__name__)

CLIENTES_FILE = "clientes.json"


def carregar_clientes():
    if not os.path.exists(CLIENTES_FILE):
        with open(CLIENTES_FILE, "w") as f:
            json.dump({}, f)
    with open(CLIENTES_FILE, "r") as f:
        return json.load(f)


def salvar_clientes(clientes):
    with open(CLIENTES_FILE, "w") as f:
        json.dump(clientes, f, indent=4)


@app.route("/")
def painel():
    clientes = carregar_clientes()
    return render_template("painel.html", clientes=clientes)


@app.route("/ping", methods=["POST"])
def ping():
    try:
        data = request.get_json()
        mac = data.get("mac")

        if not mac:
            return jsonify({"status": "erro", "mensagem": "MAC não fornecido"}), 400

        clientes = carregar_clientes()

        if mac not in clientes:
            clientes[mac] = {
                "ultimo_ping": time.time()
            }
        else:
            clientes[mac]["ultimo_ping"] = time.time()

        salvar_clientes(clientes)

        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"Erro no /ping: {e}")
        return jsonify({"status": "erro", "mensagem": "Erro interno no servidor"}), 500


@app.template_filter("status_online")
def status_online(timestamp):
    agora = time.time()
    return "online" if agora - timestamp < 60 else "offline"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)

