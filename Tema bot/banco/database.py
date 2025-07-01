# banco/database.py
# -*- coding: utf-8 -*-

import re
import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error
from contextlib import contextmanager

# Carrega variáveis de ambiente
load_dotenv()

DB_CONFIG = {
    'user':     os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host':     os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'port':     os.getenv('DB_PORT', 3306), # Porta padrão 3306
}

@contextmanager
def get_connection():
    """Gerenciador de contexto para a conexão com o banco de dados."""
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        yield conn
    except Error as e:
        print(f"ERRO DE CONEXÃO COM O BANCO DE DADOS: {e}")
        yield None
    finally:
        if conn and conn.is_connected():
            conn.close()

# --- Funções Auxiliares de Limpeza ---
def _clean_cpf(cpf: str) -> str:
    """Remove caracteres não numéricos do CPF."""
    return re.sub(r'\D', '', str(cpf))

def _clean_phone(phone: str) -> str:
    """Remove caracteres não numéricos do telefone."""
    return re.sub(r'\D', '', str(phone))


# --- Funções de Busca (Modificadas para retornar Dicionário ou None) ---

def buscar_usuario_por_cpf(cpf: str) -> dict | None:
    """
    Busca um usuário pelo CPF.
    Retorna:
    - Um dicionário com os dados do usuário, se encontrado.
    - None, se não encontrado ou em caso de erro.
    """
    cpf_digits = _clean_cpf(cpf)
    if not cpf_digits:
        return None
    
    with get_connection() as db:
        if db is None:
            return None # Retorna None se a conexão com o DB falhar

        query = "SELECT id, nome, email, telefone, cpf FROM candidatos WHERE cpf = %s"
        try:
            with db.cursor(dictionary=True) as cur:
                cur.execute(query, (cpf_digits,))
                user_data = cur.fetchone() # Retorna o dicionário do usuário ou None
            return user_data
        except Error as e:
            print(f"Erro ao buscar por CPF: {e}")
            return None


def buscar_usuario_por_email(email: str) -> dict | None:
    """Busca um usuário pelo email e retorna seus dados como um dicionário."""
    email_lower = email.lower().strip()
    with get_connection() as db:
        if db is None: return None
        
        query = "SELECT id, nome, email, telefone, cpf FROM candidatos WHERE email = %s"
        try:
            with db.cursor(dictionary=True) as cur:
                cur.execute(query, (email_lower,))
                user_data = cur.fetchone()
            return user_data
        except Error as e:
            print(f"Erro ao buscar por Email: {e}")
            return None


def buscar_usuario_por_telefone(telefone: str) -> dict | None:
    """Busca um usuário pelo telefone e retorna seus dados como um dicionário."""
    tel_digits = _clean_phone(telefone)
    if not tel_digits: return None
    
    with get_connection() as db:
        if db is None: return None
        
        # Busca por telefones que terminam com os dígitos informados
        # para compatibilidade com números que têm ou não '55' no início.
        search_phone = tel_digits[-11:] if len(tel_digits) >= 11 else tel_digits
        query = "SELECT id, nome, email, telefone, cpf FROM candidatos WHERE telefone LIKE %s"
        
        try:
            with db.cursor(dictionary=True) as cur:
                cur.execute(query, (f"%{search_phone}",))
                user_data = cur.fetchone()
            return user_data
        except Error as e:
            print(f"Erro ao buscar por Telefone: {e}")
            return None

# --- Função de Criação (a lógica original já é boa) ---

def criar_candidato(nome: str, cpf: str, email: str, telefone: str) -> tuple[bool, str]:
    """
    Tenta inserir um novo candidato. Retorna (sucesso, mensagem_para_usuario).
    """
    cpf_digits = _clean_cpf(cpf)
    if len(cpf_digits) != 11:
        return False, "CPF inválido. Por favor, use 11 dígitos."
    
    tel_digits = _clean_phone(telefone)
    if not (10 <= len(tel_digits) <= 11):
        return False, "Telefone inválido. Verifique o DDD e o número."

    email_lower = email.lower().strip()

    with get_connection() as db:
        if db is None:
            return False, "Não foi possível conectar ao banco de dados para o cadastro."

        query = "INSERT INTO candidatos (nome, cpf, email, telefone) VALUES (%s, %s, %s, %s)"
        try:
            with db.cursor() as cur:
                cur.execute(query, (nome, cpf_digits, email_lower, tel_digits))
            db.commit()
        except Error as e:
            if e.errno == 1062: # Erro de entrada duplicada
                if "cpf" in e.msg:
                    return False, "Este CPF já está cadastrado em nosso sistema."
                if "email" in e.msg:
                    return False, "Este email já está cadastrado em nosso sistema."
            print(f"ERRO AO INSERIR NO BANCO DE DADOS: {e}")
            return False, "Houve um problema ao realizar o cadastro. Tente mais tarde."

    return True, "Cadastro realizado com sucesso!"
