import re
import os
import openai
import json
from datetime import datetime
from banco.database import buscar_usuario_por_cpf, criar_candidato, buscar_usuario_por_email, buscar_usuario_por_telefone
from dotenv import load_dotenv

# IMPORTAR A FUNÇÃO RAG_ANSWER E A EXCEÇÃO RAGFallbackError
from rag_teste import rag_answer, RAGFallbackError
from utils.email_utils import send_support_ticket

# Carrega variáveis de ambiente e define API Key
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("Defina OPENAI_API_KEY no .env")

class ChatContext:
    def __init__(self):
        self.awaiting_confirmation = False
        self.awaiting_cadastro = False
        self.awaiting_sac_option = False
        self.greeted = False
        self.last_cpf_found = None
        self.awaiting_alternative_search = False
        self.user_data_found = {}
        self.last_rag_query = None

FAQ_SAC = {
    "1": {
        "pergunta": "Como ativar minha conta e começar a usar a plataforma?",
        "resposta": (
            "Para ativar sua conta:"
            "\n1️⃣ Acesse https://app.suaempresa.com/ativar-conta"
            "\n2️⃣ Informe seu e-mail cadastrado"
            "\n3️⃣ Clique no link recebido por e-mail"
            "\nPronto! Agora você pode fazer login e explorar o painel."
        )
    },
    "2": {
        "pergunta": "Onde encontro o material de onboarding do cliente?",
        "resposta": (
            "Você pode acessar o material de onboarding em:"
            "\nhttps://interna.suaempresa.com/onboarding"
            "\nLá estão vídeos, guias e perguntas frequentes."
        )
    },
    "3": {
        "pergunta": "Como integrar com meu sistema de RH/CRM?",
        "resposta": (
            "Para integrar:"
            "\n• Gere sua chave de API em Configurações → Integrações"
            "\n• Consulte a documentação em https://docs.suaempresa.com/api"
            "\n• Se precisar, fale com o time de TI pelo chat interno."
        )
    },
    "4": {
        "pergunta": "Quero falar com um atendente humano",
        "resposta": (
            "Sem problemas! Nossos canais de atendimento são:"
            "\n📞 Telefone: (31) 4000-1234"
            "\n💬 Chat interno (Slack): #suporte-cs"
        )
    },
    "5": {
        "pergunta": "Outra dúvida (usar buscador avançado)",
        "resposta": (
            "Claro! Descreva sua dúvida em poucas palavras que usarei a base vetorial para buscar a melhor resposta."
        )
    },
}

def _sac_menu() -> str:
    "Retorna o menu de opções do SAC."
    linhas = ["📋 Central de Ajuda"]
    for key, faq in FAQ_SAC.items():
        linhas.append(f"{key}) {faq['pergunta']}")
    return "\n".join(linhas)

def _get_system_prompt_for_gpt(context: ChatContext) -> str:
    """
    Retorna o prompt do sistema para o GPT, instruindo-o a identificar a intenção
    e responder em formato JSON. O prompt é adaptado ao contexto.
    """
    base_prompt = """
Você é um assistente de Customer Success focado em Onboarding, com tom caloroso, receptivo e empático.
Gere respostas originais, variando a linguagem e sinônimos. Evite clichês repetidos.

Sua resposta DEVE ser uma estrutura JSON no formato:
`{{ "acao": "saudacao" | "problema" | "duvida" | "ja_cliente" | "nao_cliente" | "confirmar_cpf" | "recusar_cpf" | "fornecer_cadastro" | "escolher_sac" | "sac_duvida_avancada" | "contato_alternativo" | "outro", "resposta": "Texto da resposta para o usuário" }}`.

**Detalhes para cada 'acao':**
- **saudacao:** Cumprimente de modo leve e humanizado, sem usar frases padrões repetidas. Não é obrigatório dizer "bom dia/tarde/noite" toda vez; use conforme o horário e contexto. Ofereça ajuda no mesmo texto.
- **problema:** Demonstre empatia genuína e antes de pedir detalhes do problema, pergunte se o usuário já é cliente para direcionar o próximo passo.
- **duvida:** Mostre interesse e peça detalhes adicionais de forma acolhedora, sem mencionar cliente.
- **ja_cliente:** Agradeça pela confiança e solicite o CPF (apenas dígitos ou formatado) para validação.
- **nao_cliente:** Informe que será preciso um cadastro simples e solicite em linhas separadas: Nome, CPF, Email e Telefone.
- **confirmar_cpf:** O usuário confirmou que os dados do CPF estão corretos. Responda positivamente e apresente o menu do SAC. NÃO adicione perguntas sobre cadastro ou outras opções aqui.
- **recusar_cpf:** O usuário negou que os dados do CPF estejam corretos. Neste caso, peça ao usuário que informe outro e-mail ou número de telefone para tentar localizar o cadastro.
- **fornecer_cadastro:** O usuário está fornecendo os dados para cadastro (Nome, CPF, Email, Telefone). Você não responderá, apenas o código Python processará.
- **escolher_sac:** O usuário está escolhendo uma opção do menu do SAC (número 1 a 4).
- **sac_duvida_avancada:** O usuário escolheu a opção 5 do SAC e agora está descrevendo sua dúvida avançada.
- **contato_alternativo:** O usuário explicitamente pediu ou indicou que prefere outra forma de contato (telefone, chat). Você deve fornecer as opções.
- **outro:** Responda de forma simpática que não entendeu e convide a reformular, ou se a intenção não se encaixa nas categorias anteriores.

**Instruções de Contexto Atuais:**
"""
    if context.awaiting_confirmation:
        base_prompt += f"\n- O usuário está aguardando para confirmar ou negar os dados do CPF '{context.last_cpf_found}'. Os dados encontrados são: Nome: {context.user_data_found.get('nome', '')}, Email: {context.user_data_found.get('email', '')}, Telefone: {context.user_data_found.get('telefone', '')}. Interprete a resposta dele para definir 'acao' como 'confirmar_cpf' ou 'recusar_cpf'. Não force 'sim' ou 'não' em sua resposta, apenas interprete a intenção. A mensagem já exibida para o usuário foi gerada pelo banco de dados e já contém a pergunta de confirmação. NÃO adicione perguntas ou sugestões adicionais à resposta final."
    elif context.awaiting_cadastro:
        base_prompt += "\n- O usuário está aguardando para fornecer Nome, CPF, Email e Telefone para cadastro. A 'acao' deve ser 'fornecer_cadastro' se ele enviou os dados em linhas separadas ou 'outro' se não."
    elif context.awaiting_sac_option:
        base_prompt += "\n- O usuário está no menu do SAC. Se a mensagem for APENAS um número entre 1 e 5 (ex: '1', '2', '5'), a 'acao' DEVE ser 'escolher_sac'. SE a mensagem for uma descrição textual de uma dúvida (mesmo que curta), e o usuário já escolheu a opção 5 anteriormente (indicado pelo 'awaiting_sac_option' estar ativo), a 'acao' DEVE ser 'sac_duvida_avancada'."
    elif context.awaiting_alternative_search:
        base_prompt += "\n- O usuário está aguardando para fornecer um email ou número de telefone para que o bot tente localizar o cadastro por outros meios."
        base_prompt += "\n- Se o usuário fornecer um email, defina 'acao' como 'fornecer_email_alternativo'. Se for um telefone, 'acao' como 'fornecer_telefone_alternativo'. Caso contrário, 'acao' como 'outro'."

    base_prompt += "\n\nSua resposta FINAL deve ser APENAS o JSON. Não inclua texto extra."
    return base_prompt

def processar_mensagem(mensagem: str, context: ChatContext) -> str:
    """
    Processa a mensagem do usuário conforme o contexto específico da sessão,
    delegando mais responsabilidade ao GPT para interpretar a intenção.
    """
    texto = mensagem.strip()
    lower = texto.lower()

    # 1. Tratamento de saudação inicial
    if re.search(r"\b(oi|olá|ola|bom dia|boa tarde|boa noite)\b", lower):
        if not context.greeted:
            context.greeted = True
            pass
        else:
            return "Em que mais posso ajudar você?"
    
    # 2. PRIORIDADE MÁXIMA: Tratamento de RAG
    if context.awaiting_sac_option and not (texto.isdigit() and 1 <= int(texto) <= 5):
        print("DEBUG: Entrou no bloco de forçamento de RAG. Chamando rag_answer.")
        context.last_rag_query = texto
        try:
            rag_result = rag_answer(texto)
            context.awaiting_sac_option = False
            return rag_result
        except RAGFallbackError as e:
            print(f"DEBUG: RAG falhou: {e}. Criando ticket de suporte.")
            context.awaiting_sac_option = False
            
            ticket_info = {
                "protocolo": f"CHATBOT-FALLBACK-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "assunto": f"Dúvida não respondida pelo RAG: {context.last_rag_query}",
                "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "nome": context.user_data_found.get('nome', 'Não informado'),
                "email": context.user_data_found.get('email', 'Não informado'),
                "telefone": context.user_data_found.get('telefone', 'Não informado'),
                "cpf": context.user_data_found.get('cpf', 'Não informado'),
                "last_rag_query": context.last_rag_query
            }
            
            send_success = send_support_ticket(ticket_info)
            
            if send_success:
                return "Me desculpa, mesmo com esses detalhes não consigo te ajudar com esse problema no momento. Mas fique tranquilo(a), criamos um ticket de ajuda com o número de protocolo **{protocolo}**. Em breve um de nossos especialistas entrará em contato para te ajudar!".format(protocolo=ticket_info['protocolo'])
            else:
                return "Me desculpa, mesmo com esses detalhes não consigo te ajudar com esse problema no momento. Não foi possível criar um ticket automaticamente. Por favor, tente entrar em contato diretamente com nosso suporte pelo telefone (31) 4000-1234."

    # 3. <--- CÓDIGO CORRIGIDO: Fluxo de cadastro robusto com Regex
    if context.awaiting_cadastro:
        # Tenta extrair os dados usando expressões regulares para mais flexibilidade
        nome_match = re.search(r"(?:nome completo|nome)[\s:]*(?P<nome>[A-Za-zÀ-ú\s]+)", texto, re.IGNORECASE)
        cpf_match = re.search(r"(?P<cpf>\d{3}\.?\d{3}\.?\d{3}-?\d{2}|\d{11})", texto)
        email_match = re.search(r"(?P<email>[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", texto)
        telefone_match = re.search(r"(?P<telefone>\(?\d{2}\)?\s?\d?[\s-]?\d{4,5}[\s-]?\d{4})", texto)

        # Se encontrou todos os dados necessários, prossegue com o cadastro
        if nome_match and cpf_match and email_match and telefone_match:
            nome = nome_match.group('nome').strip()
            cpf_limpo = re.sub(r'\D', '', cpf_match.group('cpf'))
            email = email_match.group('email').strip()
            telefone = telefone_match.group('telefone').strip()

            # Validações dos dados extraídos
            if not re.fullmatch(r"\d{11}", cpf_limpo):
                return "O CPF informado parece inválido. Por favor, verifique e envie os dados novamente."
            
            # Chama a função para criar o candidato no banco
            ok, resp_db = criar_candidato(nome, cpf_limpo, email, telefone)
            context.awaiting_cadastro = False # Finaliza o estado de aguardar cadastro
            
            if ok:
                context.awaiting_sac_option = True
                context.user_data_found = {"nome": nome, "cpf": cpf_limpo, "email": email, "telefone": telefone}
                return resp_db + "\n\n" + _sac_menu()
            else:
                # Retorna a mensagem de erro do banco (ex: CPF/email duplicado)
                return resp_db
        else:
            # Se não encontrou todos os dados na mensagem, deixa o fluxo continuar para o GPT
            # que poderá pedir para o usuário reenviar os dados.
            pass

    # 4. <--- CÓDIGO CORRIGIDO: Proteção no fluxo de busca por CPF
    cpf_match = re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", texto)
    # Adicionada a condição "not context.awaiting_cadastro"
    if cpf_match and not context.awaiting_cadastro and not context.awaiting_alternative_search:
        cpf_limpo = re.sub(r"\D", "", cpf_match.group())
        context.last_cpf_found = cpf_limpo
        
        user_data = buscar_usuario_por_cpf(cpf_limpo)

        if user_data:
            context.awaiting_confirmation = True
            context.user_data_found = user_data
            return (f"**Encontramos um possível cadastro!**\n\n"
                    f"**Nome:** {user_data['nome']}\n"
                    f"**E-mail:** {user_data['email']}\n"
                    f"**Telefone:** {user_data['telefone']}\n\n"
                    "É você mesmo? ")
        else:
            context.awaiting_alternative_search = True
            return "Não encontrei seu cadastro com este CPF. Gostaria de tentar com seu e-mail ou telefone?"

    # 5. Fluxo de busca alternativa por email/telefone
    if context.awaiting_alternative_search:
        email_match = re.fullmatch(r"[^@]+@[^@]+\.[^@]+", texto)
        tel_digits = re.sub(r"\D", "", texto)
        user_data_alt = None

        if email_match:
            user_data_alt = buscar_usuario_por_email(texto)
        elif 10 <= len(tel_digits) <= 11:
            user_data_alt = buscar_usuario_por_telefone(texto)
        else:
            return "Não consegui identificar um e-mail ou telefone válido. Por favor, digite um para continuar a busca."

        if user_data_alt:
            context.awaiting_alternative_search = False
            context.awaiting_confirmation = True
            context.user_data_found = user_data_alt
            return (f"**Encontramos um possível cadastro associado a este dado!**\n\n"
                    f"**Nome:** {user_data_alt['nome']}\n"
                    f"**E-mail:** {user_data_alt['email']}\n"
                    f"**Telefone:** {user_data_alt['telefone']}\n\n"
                    "É você mesmo? Por favor, **responda 'sim' ou 'não'**.")
        else:
            context.awaiting_alternative_search = False
            context.awaiting_cadastro = True
            return "Não encontrei seu cadastro com o e-mail ou telefone fornecido. Você gostaria de se cadastrar para ter acesso à nossa plataforma?"

    # 6. Chamada ao GPT para interpretação flexível
    system_prompt = _get_system_prompt_for_gpt(context)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",  "content": texto}
    ]
    try:
        resp = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=messages,
            temperature=0.4,
            response_format={"type": "json_object"}
        )
        gpt_json_response = json.loads(resp.choices[0].message.content.strip())
        action = gpt_json_response.get("acao")
        reply_text = gpt_json_response.get("resposta")

        print(f"DEBUG: Context awaiting_sac_option: {context.awaiting_sac_option}")
        print(f"DEBUG: User Input: {texto}")
        print(f"DEBUG: GPT Action: {action}")
        print(f"DEBUG: GPT Reply Text: {reply_text}")

        # Lógica para reagir à "acao" do GPT
        if action == "confirmar_cpf":
            context.awaiting_confirmation = False
            context.awaiting_sac_option = True
            return f"Ótimo! Seus dados foram validados. Como posso te ajudar hoje?\n\n" + _sac_menu()

        elif action == "recusar_cpf":
            context.awaiting_confirmation = False
            context.last_cpf_found = None
            context.user_data_found = {}
            context.awaiting_alternative_search = True
            return "Entendo. Por favor, informe seu melhor e-mail ou número de telefone para tentarmos localizar seu cadastro."

        elif action == "ja_cliente":
            return "Que ótimo! Para que eu possa acessar seu cadastro e te ajudar melhor, você poderia me informar seu CPF (somente os números)?"

        elif action == "nao_cliente":
            context.awaiting_cadastro = True
            return "Entendi. Para que você possa usar nossa plataforma e ter acesso a todas as funcionalidades, precisamos de um rápido cadastro. Por favor, me informe:\nSeu Nome Completo:\nSeu CPF (apenas números):\nSeu E-mail:\nSeu Telefone (com DDD):"

        elif action == "escolher_sac":
            if texto.isdigit() and 1 <= int(texto) <= 5:
                if texto == "5":
                    context.awaiting_sac_option = True
                    return "Ok, poderia me descrever sua dúvida em poucas palavras para eu poder buscar a melhor resposta na nossa base de conhecimento?"
                else:
                    context.awaiting_sac_option = False
                    return FAQ_SAC[texto]["resposta"]
            else:
                context.awaiting_sac_option = False
                return reply_text
        
        if "central de ajuda" in reply_text.lower() or "menu" in reply_text.lower() or "sac" in reply_text.lower():
            context.awaiting_sac_option = True
            reply_text += "\n\n" + _sac_menu()
        
        return reply_text

    except json.JSONDecodeError:
        print(f"Erro ao decodificar JSON da resposta do GPT: {resp.choices[0].message.content}")
        return "Desculpe, tive um problema ao processar sua solicitação. Por favor, tente novamente."
    except Exception as e:
        print(f"Erro inesperado com a API OpenAI: {e}")
        return "Desculpe, estou com dificuldades no momento. Tente novamente mais tarde."