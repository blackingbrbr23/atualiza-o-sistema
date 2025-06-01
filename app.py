from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort, make_response
from datetime import datetime
import os
import shutil
import psycopg2

app = Flask(__name__)

# ==============================
#   CONFIGURAÇÃO DO BANCO (Supabase)
# ==============================
DATABASE_URL = (
    "postgresql://"
    "postgres.olmnsorpzkxqojrgljyy"   # ← usuário correto com “q”
    ":%40%40W365888aw"                # senha “@@W365888aw” codificada
    "@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
)

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    """
    Cria a tabela 'clientes' caso não exista. Campos:
      - mac TEXT PRIMARY KEY
      - nome TEXT NOT NULL
      - ultimo_ping TIMESTAMP
      - ultima_atualizacao TEXT DEFAULT '---'
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS clientes (
                    mac TEXT PRIMARY KEY,
                    nome TEXT NOT NULL,
                    ultimo_ping TIMESTAMP,
                    ultima_atualizacao TEXT DEFAULT '---'
                );
            """)
            conn.commit()

# Garante que a tabela exista logo ao importar/app iniciar
init_db()

# ==============================
#   CONFIGURAÇÃO DA PASTA DE UPLOADS
# ==============================
UPLOAD_FOLDER = "atualizacoes"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# ==============================
#   ROTAS
# ==============================

@app.route('/')
def index():
    """
    Exibe todos os clientes cadastrados:
      - nome
      - MAC (chave)
      - status online/offline (último ping < 5 min)
      - última atualização
      - botões de upload individual e exclusão
    """
    clientes = {}
    agora = datetime.now()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT mac, nome, ultimo_ping, ultima_atualizacao
                FROM clientes
                ORDER BY nome;
            """)
            rows = cur.fetchall()

            for mac, nome, ultimo_ping, ultima_atualizacao in rows:
                online = False
                if ultimo_ping:
                    delta = (agora - ultimo_ping).total_seconds()
                    if delta < 300:
                        online = True

                clientes[mac] = {
                    "nome": nome,
                    "online": online,
                    "ultimo_ping": ultimo_ping.strftime("%Y-%m-%d %H:%M:%S") if ultimo_ping else "---",
                    "ultima_atualizacao": ultima_atualizacao or "---"
                }

    return render_template('index.html', clientes=clientes)


@app.route('/upload_all', methods=['POST'])
def upload_all():
    """
    Recebe um único arquivo .rar e distribui a todos os clientes cadastrados no banco.
    Em seguida, atualiza o campo ultima_atualizacao para cada MAC.
    """
    if 'arquivo' not in request.files:
        return "Nenhum arquivo enviado", 400

    arquivo = request.files['arquivo']
    if not arquivo.filename.lower().endswith('.rar'):
        return "Apenas .rar", 400

    # Salvar temporário
    nome_temp = 'temp.rar'
    caminho_temp = os.path.join(UPLOAD_FOLDER, nome_temp)
    arquivo.save(caminho_temp)

    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1) Buscar todos os MACs de clientes
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT mac FROM clientes;")
            macs = [row[0] for row in cur.fetchall()]

    # 2) Para cada MAC, copiar o temp.rar e atualizar ultima_atualizacao no banco
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for mac in macs:
                destino = os.path.join(UPLOAD_FOLDER, f"{mac}.rar")
                shutil.copy(caminho_temp, destino)
                cur.execute(
                    "UPDATE clientes SET ultima_atualizacao = %s WHERE mac = %s;",
                    (agora_str, mac)
                )
            conn.commit()

    os.remove(caminho_temp)
    return redirect(url_for('index'))


@app.route('/upload/<cliente_id>', methods=['POST'])
def upload_cliente(cliente_id):
    """
    Recebe um .rar apenas para o cliente cujo MAC é cliente_id.
    Salva como '{mac}.rar' e atualiza ultima_atualizacao no banco.
    """
    # Verifica existência no banco
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM clientes WHERE mac = %s;", (cliente_id,))
            existe = cur.fetchone() is not None

    if not existe:
        abort(404)

    if 'arquivo' not in request.files:
        return "Nenhum arquivo enviado", 400

    arquivo = request.files['arquivo']
    if not arquivo.filename.lower().endswith('.rar'):
        return "Apenas .rar", 400

    nome_rar = f"{cliente_id}.rar"
    caminho_rar = os.path.join(UPLOAD_FOLDER, nome_rar)
    arquivo.save(caminho_rar)

    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE clientes SET ultima_atualizacao = %s WHERE mac = %s;",
                (agora_str, cliente_id)
            )
            conn.commit()

    return redirect(url_for('index'))


@app.route('/delete/<cliente_id>', methods=['POST'])
def delete_cliente(cliente_id):
    """
    Remove o cliente (mac) do banco e deleta o arquivo '{mac}.rar' se existir.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM clientes WHERE mac = %s;", (cliente_id,))
            conn.commit()

    rar_path = os.path.join(UPLOAD_FOLDER, f"{cliente_id}.rar")
    if os.path.exists(rar_path):
        os.remove(rar_path)

    return redirect(url_for('index'))


@app.route('/download/<cliente_id>')
def baixar_atualizacao(cliente_id):
    """
    Serve o arquivo '{mac}.rar' como anexo. 
    Antes de retornar, busca em DB o campo 'ultima_atualizacao' (TEXT no formato "YYYY-MM-DD HH:MM:SS"),
    converte para ISO (YYYY-MM-DDTHH:MM:SS) e coloca no cabeçalho 'X-Data-Envio'.
    Se não existir arquivo, retorna 404.
    """
    # 1) Verifica se existe no banco e captura ultima_atualizacao
    ultima_envio_str = None
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ultima_atualizacao FROM clientes WHERE mac = %s;",
                (cliente_id,)
            )
            row = cur.fetchone()
            if row:
                ultima_envio_str = row[0]  # ex: "2025-05-30 14:22:00"

    if not ultima_envio_str or ultima_envio_str.strip() == "---":
        # Sem registro válido de data → não há arquivo ou nunca enviado
        abort(404)

    # Converte string do banco (YYYY-MM-DD HH:MM:SS) para ISO 8601
    try:
        dt = datetime.strptime(ultima_envio_str, "%Y-%m-%d %H:%M:%S")
        data_envio_iso = dt.isoformat()
    except Exception:
        data_envio_iso = None

    # 2) Verifica se o arquivo existe fisicamente
    nome_rar = f"{cliente_id}.rar"
    caminho = os.path.join(UPLOAD_FOLDER, nome_rar)
    if not os.path.exists(caminho):
        return "Arquivo não encontrado", 404

    # 3) Usa make_response para anexar cabeçalho personalizado
    response = make_response(send_from_directory(UPLOAD_FOLDER, nome_rar, as_attachment=True))
    if data_envio_iso:
        response.headers["X-Data-Envio"] = data_envio_iso
    return response


@app.route('/ping', methods=['POST'])
def ping():
    """
    Recebe JSON com {"mac": "..."}.
    - Se não vier 'mac', erro 400.
    - Se MAC não existir no banco, inserir novo registro com:
        nome = "Cliente {N}", ultimo_ping = agora, ultima_atualizacao = '---'
    - Se já existir, apenas atualizar ultimo_ping.
    """
    data = request.get_json()
    if not data or 'mac' not in data:
        return {"error": "MAC não enviado"}, 400

    mac = data['mac']
    agora = datetime.now()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM clientes WHERE mac = %s;", (mac,))
            existe = (cur.fetchone()[0] > 0)

            if existe:
                # Atualiza último ping
                cur.execute(
                    "UPDATE clientes SET ultimo_ping = %s WHERE mac = %s;",
                    (agora, mac)
                )
            else:
                # Descobre quantos clientes já existem para numerar o nome padrão
                cur.execute("SELECT COUNT(*) FROM clientes;")
                total = cur.fetchone()[0] or 0
                nome_padrao = f"Cliente {total + 1}"
                cur.execute(
                    """
                    INSERT INTO clientes (mac, nome, ultimo_ping, ultima_atualizacao)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (mac, nome_padrao, agora, "---")
                )
            conn.commit()

    return {"message": "Ping recebido"}, 200


if __name__ == '__main__':
    # Se for rodar localmente com `python app.py`, mantém debug=True
    app.run(debug=True, host='0.0.0.0', port=5000)
