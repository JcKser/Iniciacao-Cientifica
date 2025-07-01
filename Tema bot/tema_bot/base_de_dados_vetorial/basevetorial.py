#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import faiss
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Caminho para a raiz do projeto (contém o .env)
PROJECT_ROOT = Path(__file__).parent.parent
# Caminho para esta pasta (contém articles_data.js)
VET_DIR = Path(__file__).parent

# 1) Carrega o .env da raiz
load_dotenv(PROJECT_ROOT / ".env")

# 2) Inicializa o client OpenAI
key = os.getenv("OPENAI_API_KEY")
if not key:
    raise RuntimeError("OPENAI_API_KEY não foi carregada. Verifique o .env na raiz do projeto.")
client = OpenAI(api_key=key)

# 3) Carrega o articles_data.js
js_path = VET_DIR / "articles_data.js"
with open(js_path, "r", encoding="utf-8") as f:
    text = f.read()
json_str = text.replace("export const articlesData = ", "").rstrip().rstrip(";")
articles = json.loads(json_str)

# 4) Gera embeddings
emb_list = []
for art in articles:
    resp = client.embeddings.create(
        model="text-embedding-ada-002",
        input=art["content"]
    )
    emb_list.append(resp.data[0].embedding)
embeddings = np.array(emb_list, dtype="float32")

# 5) Cria e popula índice FAISS
dim = embeddings.shape[1]
index = faiss.IndexFlatL2(dim)
index.add(embeddings)

# 6) Persiste o índice e os metadados aqui dentro de base_de_dados_vetorial
faiss.write_index(index, str(VET_DIR / "articles_faiss.index"))
with open(VET_DIR / "articles_metadata.json", "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=2)

print(f"✅ Índice FAISS criado com {index.ntotal} vetores em {VET_DIR}")
