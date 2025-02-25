from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, flash, Response, jsonify
from flask_httpauth import HTTPBasicAuth

import os
import psycopg2
import psycopg2.extras
from datetime import datetime
import pytz
import csv

app = Flask(__name__)
app.secret_key = 'chave_secreta'

fuso_brasilia = pytz.timezone('America/Sao_Paulo')

# URL do banco de dados (definir no Render)
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://appu_db_qflz_user:KP9LDX3ptUDn79KyzOsP3UTDgF8IvFCG@dpg-cuqtillumphs73f0cov0-a.oregon-postgres.render.com/appu_db_qflz")

auth = HTTPBasicAuth()

BASIC_AUTH_USERNAME1 = os.environ.get('BASIC_AUTH_USERNAME1', 'denis')  # Valor padrão se não definido
BASIC_AUTH_PASSWORD1 = os.environ.get('BASIC_AUTH_PASSWORD1')
BASIC_AUTH_USERNAME2 = os.environ.get('BASIC_AUTH_USERNAME2', 'lubelia')
BASIC_AUTH_PASSWORD2 = os.environ.get('BASIC_AUTH_PASSWORD2')

@auth.verify_password
def verify_password(username, password):
    username = username.strip().lower()
    password = password.strip().lower()
    basic_username1 = BASIC_AUTH_USERNAME1.strip().lower()
    basic_password1 = BASIC_AUTH_PASSWORD1.strip().lower()
    basic_username2 = BASIC_AUTH_USERNAME2.strip().lower()
    basic_password2 = BASIC_AUTH_PASSWORD2.strip().lower()

    if username == basic_username1 and password == basic_password1:
        return username
    elif username == basic_username2 and password == basic_password2:
        return username
    return None

def get_db():
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.DictCursor)
        return conn
    except psycopg2.Error as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None

def formatar_data_hora(data_hora_obj):
    if data_hora_obj:
        if isinstance(data_hora_obj, str):  # Verifica se é string
            try:
                data_hora_obj = datetime.strptime(data_hora_obj, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return None  # Ou trate o erro de formato de data como preferir

        if data_hora_obj.tzinfo is None:  # Verifica se é naive
            data_hora_obj = pytz.utc.localize(data_hora_obj).astimezone(fuso_brasilia)
        else:  # Se já tiver tzinfo, apenas converte para o fuso desejado
            data_hora_obj = data_hora_obj.astimezone(fuso_brasilia) # Converte diretamente

        return data_hora_obj.strftime('%d/%m/%y %H:%M')
    return None

@app.context_processor
def inject_functions():
    return {'formatar_data_hora': formatar_data_hora}

@app.route('/', methods=['GET', 'POST'])
@auth.login_required
def index():
    db = get_db()
    if not db:
        return render_template('erro_conexao.html')

    cursor = db.cursor()

    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chamados (
                id SERIAL PRIMARY KEY,
                numero_chamado INTEGER UNIQUE,
                solicitante TEXT,
                descricao TEXT,
                prioridade TEXT,
                categoria TEXT,
                status TEXT DEFAULT 'aberto',
                solucao TEXT,
                data_abertura TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                data_fechamento TIMESTAMP WITH TIME ZONE,
                tipo TEXT
            )
        ''')
        db.commit()
    except psycopg2.Error as e:
        print(f"Erro ao criar a tabela: {e}")
        flash('Erro ao configurar o banco de dados. Tente novamente mais tarde.')
        return render_template('erro_conexao.html')

    if request.method == 'POST':
        numero_chamado = request.form.get('numero_chamado')
        solicitante = request.form.get('solicitante')
        descricao = request.form.get('descricao')
        prioridade = request.form.get('prioridade')
        tipo = request.form.get('tipo')
        categoria = request.form.get('categoria')

        if not all([numero_chamado, solicitante, descricao, prioridade, tipo, categoria]):
            flash('Todos os campos são obrigatórios. Por favor, preencha todos os campos.')
            return redirect(url_for('index'))

        try:
            cursor.execute("SELECT * FROM chamados WHERE numero_chamado = %s", (numero_chamado,))
            resultado = cursor.fetchone()

            if resultado:
                flash('Erro: Número de chamado já existe. Por favor, escolha outro.')
                return redirect(url_for('index'))

            cursor.execute("INSERT INTO chamados (numero_chamado, solicitante, descricao, prioridade, tipo, categoria) VALUES (%s, %s, %s, %s, %s, %s)",
                           (numero_chamado, solicitante, descricao, prioridade, tipo, categoria))
            db.commit()
            flash('Chamado cadastrado com sucesso!')
            return redirect(url_for('index'))
        except psycopg2.Error as e:
            print(f"Erro ao inserir chamado: {e}")
            flash('Erro ao cadastrar o chamado. Tente novamente mais tarde.')
            return redirect(url_for('index'))

    try:
        cursor.execute("SELECT * FROM chamados")
        chamados = cursor.fetchall()
    except psycopg2.Error as e:
        print(f"Erro ao carregar chamados: {e}")
        chamados = []

    db.close()
    return render_template('index.html', chamados=chamados)

@app.route('/relatorio')
def relatorio():
    db = get_db()
    if not db:
        return render_template('erro_conexao.html')

    cursor = db.cursor()

    # Capturar os parâmetros da URL
    prioridade_filtro = request.args.get('prioridade', '').strip()
    tipo_filtro = request.args.get('tipo', '').strip()
    categoria_filtro = request.args.get('categoria', '').strip()
    status_filtro = request.args.get('status', '').strip()
    data_inicio_filtro = request.args.get('data_inicio', '').strip()
    data_fim_filtro = request.args.get('data_fim', '').strip()
    
    print(f"Filtros recebidos - Prioridade: {prioridade_filtro}, Tipo: {tipo_filtro}, Categoria: {categoria_filtro}, Status: {status_filtro}, Data Início: {data_inicio_filtro}, Data Fim: {data_fim_filtro}")

    # Monta a consulta SQL dinamicamente
    query = "SELECT * FROM chamados WHERE 1=1"
    count_query = "SELECT COUNT(*) FROM chamados WHERE 1=1"
    grafico_query = "SELECT prioridade, COUNT(*) FROM chamados WHERE 1=1"
    params = []

    def adicionar_filtro(nome_coluna, valor):
        """ Função auxiliar para adicionar filtros dinamicamente. """
        nonlocal query, count_query, grafico_query, params
        if valor:
            query += f" AND {nome_coluna} = %s"
            count_query += f" AND {nome_coluna} = %s"
            grafico_query += f" AND {nome_coluna} = %s"
            params.append(valor)

    # Aplica os filtros
    adicionar_filtro("prioridade", prioridade_filtro)
    adicionar_filtro("tipo", tipo_filtro)
    adicionar_filtro("categoria", categoria_filtro)
    adicionar_filtro("status", status_filtro)

    if data_inicio_filtro:
        query += " AND data_abertura >= %s"
        count_query += " AND data_abertura >= %s"
        grafico_query += " AND data_abertura >= %s"
        params.append(data_inicio_filtro)

    if data_fim_filtro:
        query += " AND data_abertura <= %s"
        count_query += " AND data_abertura <= %s"
        grafico_query += " AND data_abertura <= %s"
        params.append(data_fim_filtro)

    try:
        # Buscar chamados filtrados
        cursor.execute(query, params)
        chamados = cursor.fetchall()

        # Buscar contadores de chamados filtrados
        cursor.execute(count_query, params)
        total_chamados = cursor.fetchone()[0]

        cursor.execute(count_query + " AND status = 'aberto'", params)
        chamados_abertos = cursor.fetchone()[0]

        cursor.execute(count_query + " AND status = 'em_andamento'", params)
        chamados_em_andamento = cursor.fetchone()[0] or 0

        cursor.execute(count_query + " AND status = 'orcamento'", params)
        chamados_orcamento = cursor.fetchone()[0] or 0

        cursor.execute(count_query + " AND status IN ('fechado presencial', 'fechado remoto')", params)
        chamados_fechados = cursor.fetchone()[0]

        # Buscar dados para o gráfico (agora com correção)
        cursor.execute(grafico_query + " GROUP BY prioridade", params)
        prioridades = cursor.fetchall()

        # Criar dicionário de contagem de prioridades
        contagem_prioridades = {
            'urgente': 0,
            'alta': 0,
            'media': 0,
            'baixa': 0
        }
        for prioridade, count in prioridades:
            contagem_prioridades[prioridade] = count

    except psycopg2.Error as e:
        print(f"Erro ao buscar chamados: {e}")
        chamados = []
        total_chamados = 0
        chamados_abertos = 0
        chamados_fechados = 0
        contagem_prioridades = {'urgente': 0, 'alta': 0, 'media': 0, 'baixa': 0}

    db.close()

    return render_template('relatorio.html', chamados_abertos=chamados_abertos, chamados_em_andamento=chamados_em_andamento, 
                       chamados_orcamento=chamados_orcamento,
                           chamados_fechados=chamados_fechados, total_chamados=total_chamados, chamados=chamados,
                           contagem_prioridades=contagem_prioridades)


@app.route('/atualizar/<int:id>', methods=['GET', 'POST'])
def atualizar(id):
    db = get_db()
    if not db:
        return render_template('erro_conexao.html')

    cursor = db.cursor()

    # Buscar chamado pelo ID corretamente
    cursor.execute("SELECT * FROM chamados WHERE id = %s", (id,))
    chamado = cursor.fetchone()  # Correção aqui

    if not chamado:
        flash("Chamado não encontrado!", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        status = request.form['status']
        solucao = request.form['solucao']

        if status in ['fechado presencial', 'fechado remoto']:
            data_fechamento_utc = datetime.now(pytz.utc)
            data_fechamento_str = data_fechamento_utc.strftime("%Y-%m-%d %H:%M:%S")
        else:
            data_fechamento_str = None

        cursor.execute(
            "UPDATE chamados SET status = %s, solucao = %s, data_fechamento = %s WHERE id = %s",
            (status, solucao, data_fechamento_str, id)
        )
        db.commit()
        db.close()
        flash("Chamado atualizado com sucesso!", "success")
        return redirect(url_for('index'))

    db.close()
    return render_template('atualizar.html', chamado=chamado)


@app.route('/excluir/<int:id>')
def excluir(id):
    db = get_db()
    if not db:
        return render_template('erro_conexao.html')

    cursor = db.cursor()
    cursor.execute("DELETE FROM chamados WHERE id = %s", (id,))
    db.commit()
    db.close()
    return redirect(url_for('index'))

@app.route('/exportar_csv')
def exportar_csv():
    db = get_db()
    if not db:
        return render_template('erro_conexao.html')

    cursor = db.cursor()
    cursor.execute("SELECT * FROM chamados")
    chamados = cursor.fetchall()
    db.close()

    # Criando o CSV
    output = []
    output.append(["ID", "Número", "Solicitante", "Descrição", "Prioridade", "Categoria", "Status", "Solução", "Abertura", "Fechamento", "Tipo"])

    for chamado in chamados:
        output.append([
            chamado['id'],
            chamado['numero_chamado'],
            chamado['solicitante'],
            chamado['descricao'],
            chamado['prioridade'],
            chamado['categoria'],
            chamado['status'],
            chamado['solucao'],
            chamado['data_abertura'].strftime('%d/%m/%Y %H:%M') if chamado['data_abertura'] else '',
            chamado['data_fechamento'].strftime('%d/%m/%Y %H:%M') if chamado['data_fechamento'] else '',
            chamado['tipo']
        ])

    # Criando a resposta CSV
    si = "\n".join([";".join(map(str, row)) for row in output])
    response = Response(si, mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=relatorio_chamados.csv"
    return response

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=False)
