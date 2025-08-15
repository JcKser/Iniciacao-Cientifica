<<<<<<< HEAD
=======

>>>>>>> e58dbed52c4a8e89b37179ac37fad28d50c0f01b
import os
import smtplib
import re
from email.mime.text import MIMEText
from email.header import Header
from dotenv import load_dotenv
from datetime import datetime


load_dotenv()


EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_SENDER_PASSWORD = os.getenv("EMAIL_SENDER_PASSWORD")
EMAIL_SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER")
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", 587)) 
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

# --- Função Auxiliar de Formatação de Telefone ---
def _format_phone(phone_number: str) -> str:
    """
    Formata um número de telefone de dígitos puros para (DD)YYYYY-YYYY ou (DD)YYYY-YYYY.
    """
    digits = re.sub(r'\D', '', str(phone_number))
    if len(digits) == 11: # Celular com 9º dígito
        return f"({digits[0:2]}) {digits[2:7]}-{digits[7:11]}"
    elif len(digits) == 10: # Fixo ou celular sem 9º dígito
        return f"({digits[0:2]}) {digits[2:6]}-{digits[6:10]}"
    return phone_number 


def send_support_ticket(ticket_info: dict) -> bool:
    """
    Envia os detalhes do ticket para o e-mail de suporte.
    Retorna True se o e-mail foi enviado com sucesso, False caso contrário.
    """
    if not all([EMAIL_SENDER, EMAIL_SENDER_PASSWORD, EMAIL_SMTP_SERVER, EMAIL_RECEIVER]):
        print("ERRO: Variáveis de ambiente de e-mail não configuradas corretamente no .env.")
        print("Verifique EMAIL_SENDER, EMAIL_SENDER_PASSWORD, EMAIL_SMTP_SERVER, EMAIL_RECEIVER.")
        return False

    sender_email = EMAIL_SENDER
    sender_password = EMAIL_SENDER_PASSWORD
    receiver_email = EMAIL_RECEIVER

    # Assunto 
    subject = Header(f"NOVO TICKET DE TESTE - {ticket_info['assunto']}", 'utf-8').encode()

    # Corpo do e-mail com os detalhes do ticket
    body = (
        f"Detalhes do Novo Chamado (TESTE):\n"
        f"-----------------------------------\n"
        f"Protocolo: {ticket_info['protocolo']}\n"
        f"Assunto: {ticket_info['assunto']}\n"
        f"Data/Hora: {ticket_info['data_hora']}\n\n"
        f"Dados do Cliente:\n"
        f"Nome: {ticket_info['nome']}\n"
        f"E-mail: {ticket_info['email']}\n"
<<<<<<< HEAD
        f"Telefone: {_format_phone(ticket_info['telefone'])}\n" # <--- MUDANÇA AQUI
=======
        f"Telefone: {ticket_info['telefone']}\n" # Já formatado pela função auxiliar
>>>>>>> e58dbed52c4a8e89b37179ac37fad28d50c0f01b
        f"CPF: {ticket_info['cpf'] if ticket_info['cpf'] else 'Não informado'}\n\n"
        f"Última Dúvida (do RAG): {ticket_info['last_rag_query']}\n"
        f"-----------------------------------\n"
        f"Este ticket de TESTE foi aberto automaticamente pelo chatbot de teste."
    )

    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = receiver_email

    try:
        print(f"Tentando conectar ao servidor SMTP: {EMAIL_SMTP_SERVER}:{EMAIL_SMTP_PORT}")
        # Estabelece conexão segura com o servidor SMTP
        with smtplib.SMTP(EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT) as server:
            server.starttls() # Inicia a segurança TLS
            server.login(sender_email, sender_password) # Faz login com as credenciais
            server.sendmail(sender_email, receiver_email, msg.as_string()) # Envia o e-mail
        print(f"SUCESSO: E-mail de ticket de TESTE enviado com sucesso para {receiver_email}")
        return True
    except smtplib.SMTPAuthenticationError:
        print(f"ERRO DE AUTENTICAÇÃO SMTP: Falha ao fazer login no servidor SMTP.")
        print(f"Verifique se o EMAIL_SENDER e EMAIL_SENDER_PASSWORD (senha de app) estão corretos no .env.")
        print(f"Se for Gmail, certifique-se de usar uma 'senha de app' gerada pelo Google.")
        return False
    except smtplib.SMTPConnectError as e:
        print(f"ERRO DE CONEXÃO SMTP: Não foi possível conectar ao servidor SMTP: {e}")
        print(f"Verifique se {EMAIL_SMTP_SERVER} e {EMAIL_SMTP_PORT} estão corretos e acessíveis.")
        return False
    except Exception as e:
        print(f"ERRO GERAL: Não foi possível enviar o e-mail de ticket de TESTE: {e}")
        return False


if __name__ == "__main__":
    print("Iniciando teste de envio de e-mail de ticket...")

    test_ticket_info = {
        "protocolo": f"TEST-TICKET-{datetime.now().strftime('%Y%m%d%H%M%S')}", 
        "nome": "Júlio César Simulado",
        "email": "teste.simulacao@exemplo.com", 
        "telefone": "31987654321", 
        "cpf": "12345678900",
        "assunto": "Problema simulado: Acesso ao sistema falhando",
        "last_rag_query": "Não consigo entrar na plataforma desde a manhã. A senha não está funcionando, mesmo após resetar.",
        "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    }

    # Formata o telefone para exibição no corpo do e-mail usando a função auxiliar
    test_ticket_info['telefone'] = _format_phone(test_ticket_info['telefone'])
    if send_support_ticket(test_ticket_info):
        print("\nTeste de envio de e-mail finalizado. Verifique a caixa de entrada do destinatário!")
    else:
<<<<<<< HEAD
        print("\nTeste de envio de e-mail falhou. Verifique os erros acima e suas configurações no .env.")
=======
        print("\nTeste de envio de e-mail falhou. Verifique os erros acima e suas configurações no .env.")
>>>>>>> e58dbed52c4a8e89b37179ac37fad28d50c0f01b
