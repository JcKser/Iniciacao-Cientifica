<h1 align="center"> 🧠 Agente Customer Onboarding </h1> <p align="center"> <img alt="Python Badge" src="https://img.shields.io/badge/Python-%233776AB?style=for-the-badge&logo=python&logoColor=white"> <img alt="FastAPI Badge" src="https://img.shields.io/badge/FastAPI-%23009688?style=for-the-badge&logo=fastapi&logoColor=white"> <img alt="Docker Badge" src="https://img.shields.io/badge/Docker-%232496ED?style=for-the-badge&logo=docker&logoColor=white"> <img alt="PostgreSQL Badge" src="https://img.shields.io/badge/PostgreSQL-%234169E1?style=for-the-badge&logo=postgresql&logoColor=white"> <img alt="OpenAI Badge" src="https://img.shields.io/badge/OpenAI-%23412991?style=for-the-badge&logo=openai&logoColor=white"> </p>

Um agente inteligente para auxiliar no processo de onboarding de clientes, automatizando etapas, respondendo FAQs e oferecendo orientações personalizadas em tempo real.

📋 Sobre o Projeto

O Agente Customer Onboarding é um sistema inteligente desenvolvido no contexto de uma iniciação científica na PUC Minas, com o objetivo de aprimorar a experiência do cliente durante o processo de integração em empresas (Customer Onboarding).

O projeto utiliza modelos de linguagem natural (LLMs) e técnicas de Processamento de Linguagem Natural (PLN) para compreender, responder e acompanhar o cliente nas etapas iniciais de uso de um produto ou serviço.

Além de reduzir a carga operacional de equipes de suporte, o agente garante respostas consistentes, rápidas e personalizadas conforme o perfil de cada usuário.

🚀 Funcionalidades

🤖 Atendimento inteligente e contextualizado

💬 Respostas automáticas para dúvidas frequentes (FAQ)

🔗 Integração com bancos de dados e APIs externas

📈 Análise e registro de interações para melhoria contínua

⚙️ Ambiente containerizado via Docker e PostgreSQL

🧩 API REST criada com FastAPI

🛠️ Tecnologias Utilizadas

Python 3.11+

FastAPI

Docker & Docker Compose

PostgreSQL

OpenAI API (LLMs)

Pydantic / SQLAlchemy

Postman (para testes de API)

📁 Estrutura do Projeto
AGENTE-ONBOARDING/
├── app/
│   ├── main.py                 # Ponto de entrada da API
│   ├── routes/                 # Rotas e endpoints
│   ├── services/               # Lógica de negócio (integração com IA e DB)
│   ├── models/                 # Estrutura de dados e ORM
│   ├── database/               # Conexão e schema do PostgreSQL
│   ├── utils/                  # Funções auxiliares
│   └── tests/                  # Testes unitários e de integração
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md

⚙️ Instalação e Configuração
1. Clone o Repositório
git clone <seu-repositorio>
cd AGENTE-ONBOARDING

2. Configure o Ambiente

Crie o arquivo .env com base no .env.example:

OPENAI_API_KEY=chave_aqui
POSTGRES_USER=onboarding
POSTGRES_PASSWORD=onboarding
POSTGRES_DB=onboarding_db
POSTGRES_PORT=5432

3. Suba os Containers
docker-compose up -d

4. Verifique os Serviços
docker-compose ps


Você deve ver:

PostgreSQL rodando na porta 5432

FastAPI rodando na porta 8000

5. Acesse a API

Acesse em:
🔗 http://localhost:8000/docs (Swagger UI)

🧠 Fluxo de Funcionamento

O cliente envia uma mensagem via interface (chat/webhook).

O agente processa o texto usando LLM da OpenAI.

A resposta é contextualizada com dados armazenados no PostgreSQL.

A API retorna a resposta ao usuário final em formato JSON.
