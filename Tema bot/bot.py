import os
from dotenv import load_dotenv
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from tools import processar_mensagem, ChatContext  # Importa ChatContext também

# Carrega .env e API key
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Defina OPENAI_API_KEY no .env")

app = Flask(__name__)

# Dicionário para armazenar o contexto de chat por usuário (número de telefone)
# Em produção, isso seria um banco de dados (Redis, Firestore, etc.)
user_contexts = {}

def enviar_resposta(texto: str) -> str:
    resp = MessagingResponse()
    resp.message(texto)
    return str(resp)

@app.route("/bot", methods=["POST"])
def bot():
    user_msg = request.form.get("Body", "").strip()
    from_number = request.form.get("From") # Obtém o número do remetente (ID do usuário)

    if not user_msg:
        return enviar_resposta("Não recebi nenhuma mensagem. Pode reenviar?")

    if not from_number:
        app.logger.warning("Requisição POST sem 'From' number. Não será possível manter o contexto.")
        return enviar_resposta("Desculpe, não consegui identificar seu número para continuar a conversa.")

    # Tenta obter o contexto para este usuário, ou cria um novo se não existir
    if from_number not in user_contexts:
        user_contexts[from_number] = ChatContext()
        app.logger.info(f"Novo contexto criado para o usuário: {from_number}")

    current_context = user_contexts[from_number]

    try:
        # Chama sua lógica de processamento, passando o contexto atual
        resposta = processar_mensagem(user_msg, current_context)
    except Exception as e:
        app.logger.error(f"Erro ao processar mensagem do usuário {from_number}: {e}", exc_info=True)
        resposta = "Desculpe, ocorreu um problema ao processar sua solicitação."

    return enviar_resposta(resposta)

if __name__ == "__main__":
    # roda no host 0.0.0.0 se for em container, ou apenas debug local
    app.run(debug=True)