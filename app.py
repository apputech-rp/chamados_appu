from flask import Flask, render_template, request, redirect, url_for, flash, make_response
import sqlite3
from datetime import datetime
import pytz
import csv
import io

app = Flask(__name__)
app.secret_key = 'chave_secreta'

fuso_brasilia = pytz.timezone('America/Sao_Paulo')

def get_db():
    db = sqlite3.connect('chamados.db', check_same_thread=False)
    db.row_factory = sqlite3.Row  # Configura o retorno como dicionário
    return db

def formatar_data_hora(data_hora_str):
    if data_hora_str:
        data_hora_obj = datetime.strptime(data_hora_str, '%Y-%m-%d %H:%M:%S')  # Converte string para datetime
        data_hora_obj = pytz.utc.localize(data_hora_obj).astimezone(fuso_brasilia)  # Converte para BRT
        return data_hora_obj.strftime('%d/%m/%y %H:%M')  # Retorna formatado
    return None

@app.context_processor
def inject_functions():
    return {'formatar_data_hora': formatar_data_hora}

@app.route('/', methods=['GET', 'POST'])
def index():
    db = get_db()
    cursor = db.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chamados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_chamado INTEGER UNIQUE,
            solicitante TEXT,
            descricao TEXT,
            prioridade TEXT,
            categoria TEXT,
            status TEXT DEFAULT 'aberto',
            solucao TEXT,
            data_abertura TEXT DEFAULT CURRENT_TIMESTAMP,
            data_fechamento TEXT,
            tipo TEXT
        )
    ''')
    db.commit()

    if request.method == 'POST':
        numero_chamado = request.form['numero_chamado']
        solicitante = request.form['solicitante']
        descricao = request.form['descricao']
        prioridade = request.form['prioridade']
        tipo = request.form['tipo']
        categoria = request.form['categoria']

        cursor.execute("SELECT * FROM chamados WHERE numero_chamado = ?", (numero_chamado,))
        resultado = cursor.fetchone()

        if resultado:
            flash('Erro: Número de chamado já existe. Por favor, escolha outro.')
            return redirect(url_for('index'))

        cursor.execute("INSERT INTO chamados (numero_chamado, solicitante, descricao, prioridade, tipo, categoria) VALUES (?, ?, ?, ?, ?, ?)",
                       (numero_chamado, solicitante, descricao, prioridade, tipo, categoria))
        db.commit()
        return redirect(url_for('index'))

    chamados = cursor.execute("SELECT * FROM chamados").fetchall()
    db.close()
    return render_template('index.html', chamados=chamados)

@app.route('/relatorio')
def relatorio():
    db = get_db()
    cursor = db.cursor()

    # Filtros da URL
    prioridade = request.args.get('prioridade')
    tipo = request.args.get('tipo')
    categoria = request.args.get('categoria')
    status = request.args.get('status')
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    # Consulta base
    query = "SELECT * FROM chamados WHERE 1=1"
    params = []

    # Aplicar filtros
    if prioridade:
        query += " AND prioridade = ?"
        params.append(prioridade)
    if tipo:
        query += " AND tipo = ?"
        params.append(tipo)
    if categoria:
        query += " AND categoria = ?"
        params.append(categoria)
    if status:
        query += " AND status = ?"
        params.append(status)
    if data_inicio:
        query += " AND data_abertura >= ?"
        params.append(data_inicio)
    if data_fim:
        query += " AND data_abertura <= ?"
        params.append(data_fim)

    # Executar a consulta
    chamados = cursor.execute(query, params).fetchall()

    # Calcular métricas
    total_chamados = len(chamados)
    chamados_abertos = sum(1 for c in chamados if c['status'] == 'aberto')
    chamados_fechados = total_chamados - chamados_abertos

    db.close()
    return render_template('relatorio.html', chamados=chamados, total_chamados=total_chamados,
                          chamados_abertos=chamados_abertos, chamados_fechados=chamados_fechados)

@app.route('/exportar_csv')
def exportar_csv():
    db = get_db()
    cursor = db.cursor()

    # Recuperar os chamados
    chamados = cursor.execute("SELECT * FROM chamados").fetchall()

    # Criar um arquivo CSV em memória
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Número', 'Solicitante', 'Descrição', 'Prioridade', 'Tipo', 'Categoria', 'Status', 'Solução', 'Data Abertura', 'Data Fechamento'])
    for chamado in chamados:
        writer.writerow([
            chamado['numero_chamado'],
            chamado['solicitante'],
            chamado['descricao'],
            chamado['prioridade'],
            chamado['tipo'],
            chamado['categoria'],
            chamado['status'],
            chamado['solucao'],
            chamado['data_abertura'],
            chamado['data_fechamento']
        ])

    # Retornar o arquivo CSV como download
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=chamados.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

@app.route('/atualizar/<int:id>', methods=['GET', 'POST'])
def atualizar(id):
    db = get_db()
    cursor = db.cursor()
    chamado = cursor.execute("SELECT * FROM chamados WHERE id = ?", (id,)).fetchone()

    if request.method == 'POST':
        status = request.form['status']
        solucao = request.form['solucao']

        if status == 'fechado presencial' or status == 'fechado remoto':        
            data_fechamento_utc = datetime.now(pytz.utc)  # Pegamos a data em UTC
            data_fechamento_str = data_fechamento_utc.strftime("%Y-%m-%d %H:%M:%S")  # Salvamos no formato UTC
        else:
            data_fechamento_str = None

        cursor.execute("UPDATE chamados SET status = ?, solucao = ?, data_fechamento = ? WHERE id = ?",
                       (status, solucao, data_fechamento_str, id))
        db.commit()
        db.close()
        return redirect(url_for('index'))

    db.close()
    return render_template('atualizar.html', chamado=chamado)

@app.route('/excluir/<int:id>')
def excluir(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM chamados WHERE id = ?", (id,))
    db.commit()
    db.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
   app.run(host='192.168.100.40', port=5000, debug=False)