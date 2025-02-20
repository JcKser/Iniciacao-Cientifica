import os
import re
from datetime import datetime
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import openai
from langchain_community.chat_models import ChatOpenAI  # Atualizado conforme aviso
from langchain.agents import initialize_agent, AgentType
from langchain.memory import ConversationBufferMemory
from tools import (
    verificar_vagas_disponiveis,
    listar_vagas,
    detalhar_vaga,
    mostrar_metricas,
    gerar_pdf,
    get_ultima_vaga_detalhada  # Importa a função correta
)

# Variável global para armazenar o nome da última vaga detalhada
# (Se você estiver armazenando o contexto em tools.py, essa variável não é necessária aqui)
# última_vaga_detalhada = None  <-- Não precisa ser definida aqui se for gerenciada em tools.py

def extrair_nome_vaga(mensagem: str) -> str:
    """
    Tenta extrair o nome da vaga a partir da mensagem do usuário.
    Exemplo: "Quero ver as métricas da vaga Analista de Dados" -> retorna "Analista de Dados"
    """
    match = re.search(r"vaga\s*(?:de\s+)?(.+)", mensagem, re.IGNORECASE)
    if match:
        nome = match.group(1).strip()
        return nome.replace("*", "")
    return None

def extrair_nome_vaga_dos_detalhes(mensagem: str) -> str:
    """
    Tenta extrair o nome da vaga a partir de uma mensagem de detalhes do assistente.
    Exemplo: "Aqui estão os detalhes da vaga de *Desenvolvedor Front-End*:" -> retorna "Desenvolvedor Front-End"
    """
    match = re.search(r"vaga\s*(?:de\s*)?\*?([^*\n:]+)\*?", mensagem, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None

def get_last_assistant_message() -> str:
    """
    Retorna o conteúdo da última mensagem do assistente presente na memória.
    Se o atributo 'role' não estiver disponível, verifica o nome da classe.
    """
    for msg in reversed(memory.chat_memory.messages):
        try:
            if msg.role == "assistant":
                return msg.content.lower()
        except AttributeError:
            if msg.__class__.__name__ == "AIMessage":
                return msg.content.lower()
    return ""

# Inicializa a aplicação Flask
app = Flask(__name__)

# Configura a chave de API do OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("A variável de ambiente OPENAI_API_KEY não está definida.")

# Cria o modelo de linguagem (GPT-4 Turbo)
llm = ChatOpenAI(model="gpt-4-turbo", temperature=0.7)

# Mensagem de sistema para orientar o agente
system_message = (
    "Você é um assistente de RH especializado em vagas, recrutamento e processos seletivos. "
    "Utilize as ferramentas disponíveis para responder a perguntas sobre vagas e oportunidades, chame a função verificar_vagas_disponiveis. "
    "Cuidado: se o usuário perguntar algo como 'vagas', ele apenas quer saber se há vagas disponíveis e não listá-las todas. "
    "Sempre que a conversa indicar que o usuário deseja ver as vagas, chame a função listar_vagas. "
    "Se o usuário solicitar detalhes de uma vaga, chame a função detalhar_vaga e atualize o nome da vaga como última vaga detalhada. "
    "Se o usuário quiser ver métricas avançadas de uma vaga, chame a função mostrar_metricas. "
    "Se o usuário pedir um relatório PDF, chame a função gerar_pdf."
)

# Inicializa a memória para manter o contexto da conversa
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

# Inicializa o agente com suporte a function calling e as ferramentas disponíveis
agente_rh = initialize_agent(
    tools=[
        listar_vagas,
        verificar_vagas_disponiveis,
        detalhar_vaga,
        mostrar_metricas,
        gerar_pdf
    ],
    llm=llm,
    agent=AgentType.OPENAI_MULTI_FUNCTIONS,
    verbose=True,
    memory=memory,
    agent_kwargs={"system_message": system_message, "return_direct": True},
)

@app.route('/bot', methods=['POST'])
def bot() -> str:
    """
    Endpoint que processa as mensagens recebidas via Twilio.
    Utiliza o contexto para interpretar respostas positivas e negativas conforme o assunto.
    """
    mensagem = request.form.get('Body', "").strip()
    mensagem_lower = mensagem.lower()

    # Saudação simples
    if mensagem_lower in ["oi", "olá", "bom dia", "boa tarde", "boa noite", "e aí", "hello"]:
        resposta_texto = gerar_saudacao()
        return enviar_resposta(resposta_texto)
    
    positive_responses = ["sim", "sim, gostaria", "sim gostaria", "quero sim", "sim quero"]
    negative_responses = ["não", "nao", "não, obrigado", "nao, obrigado", "não quero", "não desejo", "n"]

    # Resposta positiva
    if mensagem_lower in positive_responses:
        last_assistant_msg = get_last_assistant_message()
        if last_assistant_msg:
            if "vagas" in last_assistant_msg or "oportunidades" in last_assistant_msg:
                resposta_texto = listar_vagas("")
                return enviar_resposta(resposta_texto)
            elif "relatório pdf" in last_assistant_msg or "pdf" in last_assistant_msg:
                ultima = get_ultima_vaga_detalhada()
                if not ultima:
                    ultima = extrair_nome_vaga_dos_detalhes(last_assistant_msg)
                if ultima:
                    resposta_texto = gerar_pdf(ultima)
                    return enviar_resposta(resposta_texto)
                else:
                    resposta_texto = "Não identifiquei a vaga para gerar o relatório PDF. Por favor, informe o nome da vaga."
                    return enviar_resposta(resposta_texto)
            elif "métricas" in last_assistant_msg:
                ultima = get_ultima_vaga_detalhada()
                if not ultima:
                    ultima = extrair_nome_vaga_dos_detalhes(last_assistant_msg)
                if ultima:
                    resposta_texto = mostrar_metricas(ultima)
                    return enviar_resposta(resposta_texto)
                else:
                    resposta_texto = "Não identifiquei a vaga para exibir as métricas. Por favor, informe o nome da vaga."
                    return enviar_resposta(resposta_texto)
        return enviar_resposta("Por favor, poderia especificar se deseja ver as vagas ou obter métricas da vaga?")
    
    # Resposta negativa
    if mensagem_lower in negative_responses:
        last_assistant_msg = get_last_assistant_message()
        if last_assistant_msg:
            if "vagas" in last_assistant_msg or "oportunidades" in last_assistant_msg:
                return enviar_resposta("Entendido. Se precisar de mais informações sobre vagas, estou à disposição.")
            elif "métricas" in last_assistant_msg or "relatório pdf" in last_assistant_msg:
                return enviar_resposta("Tudo bem. Se precisar de mais informações sobre as métricas ou desejar gerar um relatório PDF, me avise.")
        return enviar_resposta("Entendido, se precisar de algo mais, estou aqui para ajudar.")
    
    # Se o usuário solicita detalhar uma vaga, atualiza o contexto (exemplo: "detalhar vaga de Desenvolvedor Front-End")
    if "detalhar" in mensagem_lower and "vaga" in mensagem_lower:
        nome_extraido = extrair_nome_vaga(mensagem)
        if nome_extraido:
            # Aqui, a função detalhar_vaga já atualiza o contexto via tools.py
            resposta_texto = agente_rh.run(f"detalhar_vaga {nome_extraido}")
            return enviar_resposta(resposta_texto)
    
    # Solicitações de métricas
    if "métricas" in mensagem_lower or "mais informações" in mensagem_lower:
        nome_extraido = extrair_nome_vaga(mensagem)
        if not nome_extraido:
            last_assistant_msg = get_last_assistant_message()
            nome_extraido = extrair_nome_vaga_dos_detalhes(last_assistant_msg)
        if nome_extraido:
            resposta_texto = agente_rh.run(f"mostrar_metricas {nome_extraido}")
        else:
            ultima = get_ultima_vaga_detalhada()
            if ultima:
                resposta_texto = agente_rh.run(f"mostrar_metricas {ultima}")
            else:
                resposta_texto = "Não identifiquei o nome da vaga para exibir as métricas. Por favor, informe o nome da vaga."
        return enviar_resposta(resposta_texto)
    
    # Solicitações de relatório PDF
    if "pdf" in mensagem_lower:
        nome_extraido = extrair_nome_vaga(mensagem)
        if not nome_extraido:
            last_assistant_msg = get_last_assistant_message()
            nome_extraido = extrair_nome_vaga_dos_detalhes(last_assistant_msg)
        if nome_extraido:
            resposta_texto = agente_rh.run(f"gerar_pdf {nome_extraido}")
        else:
            ultima = get_ultima_vaga_detalhada()
            if ultima:
                resposta_texto = agente_rh.run(f"gerar_pdf {ultima}")
            else:
                resposta_texto = "Não identifiquei o nome da vaga para gerar o relatório PDF. Por favor, informe o nome da vaga."
        return enviar_resposta(resposta_texto)

    try:
        resposta_texto = agente_rh.run(mensagem)
    except Exception as e:
        app.logger.error(f"Erro ao processar a mensagem com o agente: {e}")
        resposta_texto = "Desculpe, houve um erro ao processar sua solicitação."

    return enviar_resposta(resposta_texto)

def gerar_saudacao() -> str:
    hora_atual = datetime.now().hour
    if hora_atual < 12:
        periodo = "Bom dia"
    elif 12 <= hora_atual < 18:
        periodo = "Boa tarde"
    else:
        periodo = "Boa noite"
    return f"{periodo}! Como posso ajudar com suas questões de RH hoje?"

def enviar_resposta(resposta: str) -> str:
    twilio_resp = MessagingResponse()
    twilio_resp.message(resposta)
    return str(twilio_resp)

if __name__ == '__main__':
    app.run(debug=True)
