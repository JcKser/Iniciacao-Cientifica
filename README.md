<h1 align="center"> 🤖 Agente Customer Onboarding </h1> <p align="center"> <img alt="Python Badge" src="https://img.shields.io/badge/Python-%233776AB?style=for-the-badge&logo=python&logoColor=white"> <img alt="FastAPI Badge" src="https://img.shields.io/badge/FastAPI-%23009688?style=for-the-badge&logo=fastapi&logoColor=white"> <img alt="MySQL Badge" src="https://img.shields.io/badge/MySQL-%234479A1?style=for-the-badge&logo=mysql&logoColor=white"> <img alt="Docker Badge" src="https://img.shields.io/badge/Docker-%232496ED?style=for-the-badge&logo=docker&logoColor=white"> <img alt="OpenAI Badge" src="https://img.shields.io/badge/OpenAI-%23412991?style=for-the-badge&logo=openai&logoColor=white"> </p>

Um agente inteligente projetado para automatizar o onboarding de clientes, oferecendo respostas contextuais, personalizadas e integradas a bancos de dados e documentos vetoriais.

📋 Sobre o Projeto

O Agente Customer Onboarding é um sistema desenvolvido como parte de uma iniciação científica na PUC Minas, com foco em Inteligência Artificial aplicada à integração de clientes.

O projeto combina Processamento de Linguagem Natural (PLN) e Recuperação de Informação baseada em vetores (RAG - Retrieval-Augmented Generation), permitindo que o agente responda perguntas, forneça orientações e guie o cliente nas etapas iniciais de interação com um serviço ou produto.

🚀 Funcionalidades

💬 Atendimento inteligente via LLM (Large Language Model)

🔍 Busca vetorial em base de dados local (FAISS + JSON metadata)

🧠 Integração com banco de dados MySQL

🧾 Ingestão automática de dados e artigos

🧩 Arquitetura modular (bot, banco, vetores e utils)

⚙️ Configuração via .env para facilitar deploy e manutenção

🛠️ Tecnologias Utilizadas

Python 3.11+

FastAPI — criação de endpoints

MySQL — armazenamento relacional

FAISS — indexação vetorial para RAG

OpenAI API — modelo de linguagem natural

Docker — ambiente padronizado

dotenv — gerenciamento de variáveis de ambiente

📁 Estrutura do Projeto
Tema bot/
├── banco/
│   ├── database.py              # Configuração e conexão com MySQL
│   └── db.py                    # Operações de banco de dados
│
├── tema_bot/
│   └── base_de_dados_vetorial/
│       ├── articles_data.js
│       ├── articles_faiss.index
│       ├── articles_metadata.json
│       ├── basevetorial.py
│       ├── scrape_and_vector_ingest.py
│       └── utils/
│           ├── __init__.py
│           └── email_utils.py   # Funções auxiliares de envio de e-mail
│
├── utils/
│   ├── exceptions.py            # Tratamento de erros
│   ├── tools.py                 # Funções utilitárias gerais
│
├── bot.py                       # Entrada principal do agente
├── rag_teste.py                 # Teste e validação do modelo RAG
├── requirements.txt
├── .env                         # Variáveis de ambiente
├── Procfile                     # Deploy (Heroku ou Render)
├── .gitignore
└── README.md

⚙️ Instalação e Configuração
1️⃣ Clone o Repositório
git clone <seu-repositorio>
cd Tema\ bot

2️⃣ Crie o Ambiente Virtual
python -m venv venv
source venv/bin/activate  # (Linux/Mac)
venv\Scripts\activate     # (Windows)

3️⃣ Instale as Dependências
pip install -r requirements.txt

4️⃣ Configure o .env

Exemplo de arquivo .env:

OPENAI_API_KEY=sua_chave_aqui
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=senha
MYSQL_DB=onboarding
VECTOR_DB_PATH=tema_bot/base_de_dados_vetorial/articles_faiss.index

5️⃣ Execute o Projeto
python bot.py

🧠 Como o Sistema Funciona

O usuário envia uma mensagem (ex: “Como faço login na plataforma?”).

O módulo RAG busca contextos relevantes na base vetorial (FAISS).

O modelo LLM (OpenAI API) usa esses contextos para gerar uma resposta precisa.

O banco MySQL armazena logs, perfis e interações para análise posterior.

🧩 Módulos Principais
🔹 bot.py

Gerencia as interações principais com o usuário e a lógica de resposta.

🔹 basevetorial.py

Realiza a busca semântica na base vetorial usando FAISS.

🔹 scrape_and_vector_ingest.py

Raspagem e indexação de dados em vetores para futura consulta.

🔹 database.py / db.py

Controla a conexão e manipulação de dados no MySQL.

🔹 email_utils.py

Gerencia envio automático de e-mails e notificações.

🧪 Testes
Teste de Funcionamento Geral
python rag_teste.py


Verifica:

Conexão com MySQL

Leitura da base vetorial

Resposta do modelo RAG

Retorno JSON do bot

🐛 Solução de Problemas
Banco de Dados Não Conecta

Verifique se o MySQL está rodando na porta correta (3306)

Confirme credenciais no .env

Execute:

mysql -u root -p

Modelo Não Retorna Resposta

Verifique a variável OPENAI_API_KEY

Teste uma chamada direta com o SDK da OpenAI

Erro “FAISS index not found”

Confirme se articles_faiss.index está no caminho configurado

Rode novamente scrape_and_vector_ingest.py

📚 Comandos Úteis
# Instalar dependências
pip install -r requirements.txt

# Executar bot principal
python bot.py

# Executar testes RAG
python rag_teste.py

# Gerar nova base vetorial
python tema_bot/base_de_dados_vetorial/scrape_and_vector_ingest.py

🧾 Licença

Este projeto está licenciado sob a MIT License.

Desenvolvido como parte da Iniciação Científica na PUC Minas — Agente Customer Onboarding 🚀
