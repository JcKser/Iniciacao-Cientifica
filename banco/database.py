import mysql.connector
from mysql.connector import Error
import random
from listas import perguntas_possiveis, introducoes
from dotenv import load_dotenv
import os

# Carregar variáveis de ambiente do .env
load_dotenv()

# Configuração da conexão com o banco de dados usando variáveis do .env
db_config = {
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'port': os.getenv('DB_PORT')
}

def connect_db():
    """
    Conecta ao banco de dados MySQL usando a configuração especificada.
    """
    try:
        return mysql.connector.connect(**db_config)
    except Error as e:
        print("Erro ao conectar ao banco de dados:", e)
        return None

def listar_vagas_ordenadas():
    """
    Consulta o banco de dados para listar vagas disponíveis na tabela processos_seletivos.
    Retorna uma lista de dicionários com os dados das vagas ou uma lista vazia em caso de erro.
    """
    db = connect_db()
    if db is None:
        return []  # Retorna uma lista vazia se a conexão falhar

    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT nome, descricao, requisitos FROM processos_seletivos ORDER BY id ASC")
        vagas = cursor.fetchall()
        return vagas if vagas else []
    except Error as e:
        print("Erro ao listar vagas:", e)
        return []  # Retorna uma lista vazia em caso de erro
    finally:
        if 'cursor' in locals():  # Verifica se o cursor foi criado antes de tentar fechá-lo
            cursor.close()
        if db.is_connected():
            db.close()

def buscar_detalhes_vaga(nome_vaga, historico_intencao, nome_vaga_armazem):
    """
    Consulta o banco de dados para buscar os detalhes de uma vaga específica pelo nome
    e retorna uma string formatada.
    """
    db = connect_db()
    if db is None:
        return "Não foi possível conectar ao banco de dados para buscar os detalhes da vaga."

    try:
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT nome, descricao, salario, requisitos, vagas, data_criacao, status
            FROM processos_seletivos
            WHERE nome = %s
        """
        cursor.execute(query, (nome_vaga,))
        vaga = cursor.fetchone()
        
        if vaga:
            introducao = random.choice(introducoes)  
            
            # Registra a intenção
            historico_intencao.append({"intencao": "mostrar_metricas", "vaga": vaga['nome']})
            nome_vaga_armazem.append(vaga['nome'])
            
            # Aqui removemos o hífen inicial e usamos *asteriscos* para negrito (estilo WhatsApp)
            detalhes = (
                f"{introducao}\n\n"
                f"🔎 *Vaga:* {vaga['nome']}\n\n"
                f"📄 *Descrição:* {vaga['descricao']}\n\n"
                f"🛠️ *Requisitos:* {vaga['requisitos']}\n\n"
                f"💼 *Salário:* R$ {vaga['salario']:.2f}\n\n"
                f"👥 *Número de Vagas:* {vaga['vagas']}\n\n"
                f"📅 *Data de Abertura:* {vaga['data_criacao']}\n\n"
                f"📌 *Status:* {'Aberta' if vaga['status'] == 'aberto' else 'Fechada'}"
            )
            
            # Escolhe pergunta final
            pergunta = random.choice(perguntas_possiveis)
            return f"{detalhes}\n\n{pergunta}"
        else:
            return "Desculpe, não encontrei detalhes para essa vaga ou ela não está aberta no momento."
    except Exception as e:
        print(f"Erro ao buscar detalhes da vaga: {e}")
        return "Erro ao buscar os detalhes da vaga."
    finally:
        if 'cursor' in locals():
            cursor.close()
        if db and db.is_connected():
            db.close()