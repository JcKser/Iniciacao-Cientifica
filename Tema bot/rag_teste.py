#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import faiss
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Importa nosso "sinalizador" de falha
from exceptions import RAGFallbackError

# Carrega .env a partir da raiz do projeto
load_dotenv() 

# Inicializa o client OpenAI
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("Variável de ambiente OPENAI_API_KEY não definida no .env")
client = OpenAI(api_key=api_key)

# Carrega índice FAISS e metadados
try:
    # <<< CORREÇÃO AQUI >>>
    # O caminho agora inclui a pasta 'tema_bot' para corresponder à sua estrutura de arquivos.
    BASE = Path(__file__).parent / "tema_bot" / "base_de_dados_vetorial"
    index = faiss.read_index(str(BASE / "articles_faiss.index"))
    with open(BASE / "articles_metadata.json", "r", encoding="utf-8") as f:
        metas = json.load(f)
except FileNotFoundError:
    # Levanta um erro claro se os arquivos da base não forem encontrados
    raise FileNotFoundError(f"Erro ao carregar arquivos de base vetorial. Verifique se a estrutura de pastas está correta. Caminho verificado: {BASE}")


def rag_answer(query: str, k: int = 3) -> str:
    """
    Busca a resposta usando RAG. 
    Se a resposta não for encontrada, lança a exceção RAGFallbackError.
    """
    # 1. Gera embedding da pergunta
    resp = client.embeddings.create(model="text-embedding-ada-002", input=query)
    qvec = np.array([resp.data[0].embedding], dtype="float32")
    
    # 2. Busca os k mais similares
    D, I = index.search(qvec, k)
    
    # 3. Monta o contexto com os trechos recuperados
    contexts = [f"[{metas[idx]['title']}] {metas[idx]['content'][:500]}..." for idx in I[0]]

    # 4. Monta o prompt para o LLM com a instrução de falha
    prompt = (
        "Você é um assistente de suporte. Baseado nos trechos de documentos fornecidos, responda à pergunta do usuário. "
        # Instrução clara para o modelo sinalizar quando não sabe a resposta.
        "Se a resposta não estiver clara ou não puder ser encontrada nos trechos, responda EXATAMENTE com a frase: "
        "'NAO_SEI_A_RESPOSTA'."
        "\n\nTRECHOS DE CONTEXTO:\n\n"
        + "\n\n".join(contexts)
        + f"\n\nPERGUNTA DO USUÁRIO: {query}\n\nRESPOSTA:"
    )
    
    # 5. Envia ao ChatGPT para gerar a resposta
    chat_completion = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    
    response_text = chat_completion.choices[0].message.content.strip()

    # 6. <<< VERIFICAÇÃO E "AVISO" DE FALHA >>>
    # Se a resposta do modelo for o nosso código de falha, disparamos o alarme.
    if "NAO_SEI_A_RESPOSTA" in response_text:
        print("RAG falhou em encontrar uma resposta. Acionando fallback.")
        raise RAGFallbackError("O modelo indicou não ter informações suficientes para responder.")

    # 7. Se tudo correu bem, retorna a resposta
    return response_text

if __name__ == "__main__":
    # Teste para o arquivo funcionando individualmente
    pergunta_teste = input("Teste RAG — digite uma pergunta:\n> ")
    try:
        resposta_teste = rag_answer(pergunta_teste)
        print("\nResposta RAG:\n", resposta_teste)
    except RAGFallbackError as e:
        # Simula o que o bot.py faria: captura o "alarme"
        print(f"\nO RAG acionou o fallback: {e}")
        print("Neste ponto, o bot.py criaria o ticket de suporte.")
