from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort
from datetime import datetime
import os
import shutil
import psycopg2

app = Flask(__name__)

# ====== CONFIGURAÇÃO DO BANCO (Supabase Pooler) ======
DATABASE_URL = (
    "postgresql://"
    "postgres.olmnsorpzkxqojrgljyy:%40%40W365888aw"
    "@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
)

def get_db_connection():
    """
    Retorna uma conexão psycopg2 para o DATABASE_URL configurado.
    """
    return psycopg2.connect(DATABASE_URL)


def init_db():
    """
    Cria automaticamente a tabela 'clientes' caso não exista.
    Campos:
      - mac (TEXT PRIMARY KEY)
      - nome (TEXT NOT NULL)
      - ultimo_ping (TIMESTAMP)           → último momento em que o cliente deu ping
      - ultima_atualizacao (TEXT DEFAULT '---')
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


# ====== CONFIGURAÇÃO DOS ARQUIVOS ======
UPLOAD_FOLDER = "atualizacoes"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


@app.before_first_request
def startup():
    """
    Ao iniciar o servidor Flask, executa init_db() para garantir que a tabela exista.
    """
    init_db()


# ====== ROTAS ======

@app.route('/')
def index():
    """
    Página principal: lista todos os clientes no banco, calcula se estão ONLINE (ping < 5 minutos)
    e exibe seu nome, MAC, status online/offline, data do último ping e data da última atualização.
    """
    clientes = {}
    agora = datetime.now()

    # 1) Busca todos os clientes salvos no banco
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
                    # Se o ping foi nos últimos 300 segundos, consideramos online
                    delta = (agora - ultimo_ping).total_seconds()
                    if delta < 300:
                        online = True

                clientes[mac] = {
                    "nome": nome,
                    "online": online,
                    # Formatamos último ping como string para exibir na tabela
                    "ultimo_ping": ultimo_ping.strftime("%Y-%m-%d %H:%M:%S") if ultimo_ping else "---",
                    "ultima_atualizacao": ultima_atualizacao or "---"
                }

    return render_template('index.html', clientes=clientes)


@app.route('/upload_all', methods=['POST'])
def upload_all():
    """
    Recebe um único arquivo .rar e distribui para TODOS os clientes que existem
    no banco de dados. Para cada cliente:
      - Copia o arquivo temporário para nome '{mac}.rar' dentro de UPLOAD_FOLDER
      - Atualiza o campo ultima_atualizacao no banco com timestamp atual
    """
    if 'arquivo' not in request.files:
        return "Nenhum arquivo enviado", 400

    arquivo = request.files['arquivo']
    if not arquivo.filename.lower().endswith('.rar'):
        return "Apenas .rar", 400

    # Salva primeiro em um arquivo temporário
    nome_temp = 'temp.rar'
    caminho_temp = os.path.join(UPLOAD_FOLDER, nome_temp)
    arquivo.save(caminho_temp)

    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1) Busca todos os MACs de clientes no banco
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT mac FROM clientes;")
            macs = [row[0] for row in cur.fetchall()]

    # 2) Para cada MAC, copia o temp.rar e atualiza ultima_atualizacao
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

    # Remove o temp.rar
    os.remove(caminho_temp)
    return redirect(url_for('index'))


@app.route('/upload/<cliente_id>', methods=['POST'])
def upload_cliente(cliente_id):
    """
    Recebe um arquivo .rar específico para determinado cliente (cliente_id = MAC).
    Se o cliente existir no banco, salva '{mac}.rar' em UPLOAD_FOLDER
    e atualiza ultima_atualizacao para timestamp atual.
    """
    # Verifica se existe o cliente no banco
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
    Remove o cliente do banco e deleta também o arquivo '{mac}.rar' em UPLOAD_FOLDER (se existir).
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
    Serve o arquivo '{mac}.rar' como anexo, se existir. Caso contrário, retorna 404.
    """
    nome_rar = f"{cliente_id}.rar"
    caminho = os.path.join(UPLOAD_FOLDER, nome_rar)
    if not os.path.exists(caminho):
        return "Arquivo não encontrado", 404

    return send_from_directory(UPLOAD_FOLDER, nome_rar, as_attachment=True)


@app.route('/ping', methods=['POST'])
def ping():
    """
    Recebe JSON via POST com chave "mac". Se não vier "mac", retorna erro 400.
    Se o MAC não existe no banco, insere um novo registro com:
      - nome padrão "Cliente {N}" (sendo N = total atual de clientes + 1)
      - ultimo_ping = timestamp de agora
      - ultima_atualizacao = '---'
    Se existir, apenas atualiza o campo ultimo_ping para timestamp de agora.
    """
    data = request.get_json()
    if not data or 'mac' not in data:
        return {"error": "MAC não enviado"}, 400

    mac = data['mac']
    agora = datetime.now()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Verifica se já existe
            cur.execute("SELECT COUNT(*) FROM clientes WHERE mac = %s;", (mac,))
            exists = (cur.fetchone()[0] > 0)

            if exists:
                # Atualiza apenas último ping
                cur.execute(
                    "UPDATE clientes SET ultimo_ping = %s WHERE mac = %s;",
                    (agora, mac)
                )
            else:
                # Descobre quantos clientes já existem para numerar o nome
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
    # Roda o Flask em modo debug na porta 5000 (você pode alterar se quiser)
    app.run(debug=True, host='0.0.0.0', port=5000)
