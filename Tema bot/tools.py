import re
import os
import openai
import json
from datetime import datetime
# Importar as novas funções de busca por email e telefone
from banco.database import buscar_candidato_por_cpf, criar_candidato, buscar_candidato_por_email, buscar_candidato_por_telefone
from dotenv import load_dotenv

# IMPORTAR A FUNÇÃO RAG_ANSWER
from rag_teste import rag_answer # <--- Importação corrigida com base na sua estrutura de pastas

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
            # Esta resposta não será mais usada diretamente, mas a pergunta é para o GPT
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
        base_prompt += f"\n- O usuário está aguardando para confirmar ou negar os dados do CPF '{context.last_cpf_found}'. Interprete a resposta dele para definir 'acao' como 'confirmar_cpf' ou 'recusar_cpf'. Não force 'sim' ou 'não' em sua resposta, apenas interprete a intenção. A mensagem já exibida para o usuário foi gerada pelo banco de dados e já contém a pergunta de confirmação. NÃO adicione perguntas ou sugestões adicionais à resposta final."
    elif context.awaiting_cadastro:
        base_prompt += "\n- O usuário está aguardando para fornecer Nome, CPF, Email e Telefone para cadastro. A 'acao' deve ser 'fornecer_cadastro' se ele enviou os dados em linhas separadas ou 'outro' se não."
    elif context.awaiting_sac_option:
        # **ATENÇÃO AQUI: Reforçando a instrução para o GPT**
        # Este prompt é mais para guiar o GPT, mas o código vai forçar a ação.
        base_prompt += "\n- O usuário está no menu do SAC. Se a mensagem for APENAS um número entre 1 e 5 (ex: '1', '2', '5'), a 'acao' DEVE ser 'escolher_sac'. SE a mensagem for uma descrição textual de uma dúvida (mesmo que curta), e o usuário já escolheu a opção 5 anteriormente (indicado pelo 'awaiting_sac_option' estar ativo), a 'acao' DEVE ser 'sac_duvida_avancada'."
    elif context.awaiting_alternative_search: # NOVO
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

    # 1. Tratamento de saudação inicial para evitar repetição excessiva
    # Se for uma saudação pura e não estiver em awaiting_sac_option,
    # deixa o fluxo ir para o GPT gerar uma saudação original.
    # Se já saudou ou se estiver em awaiting_sac_option, responde "Em que mais posso ajudar".
    if re.search(r"\b(oi|olá|ola|bom dia|boa tarde|boa noite)\b", lower):
        if not context.greeted:
            context.greeted = True
            # Permite que o GPT decida a saudação inicial
        else:
            return "Em que mais posso ajudar você?"

    # **NOVO BLOCO DE FORÇAMENTO DE RAG**
    # 2. PRIORIDADE MÁXIMA: Se o bot está esperando a descrição de uma dúvida avançada (após o 5)
    # E a mensagem do usuário NÃO é um número de opção do SAC (já que ele já "escolheu" 5 implicitamente)
    if context.awaiting_sac_option and not (texto.isdigit() and 1 <= int(texto) <= 5):
        print("DEBUG: Entrou no bloco de forçamento de RAG. Chamando rag_answer.")
        # Se o bot está esperando uma dúvida avançada, qualquer input que não seja uma opção de menu
        # deve ser tratado como a dúvida para o RAG.
        rag_result = rag_answer(texto) # Chama a função RAG com a pergunta do usuário
        context.awaiting_sac_option = False # A dúvida foi respondida, reseta o estado
        return rag_result # Retorna a resposta obtida do RAG


    # 3. Fluxo de cadastro (tem prioridade se o bot pediu dados de cadastro E os dados completos foram enviados)
    # Mudei a ordem para que este bloco venha DEPOIS do forçamento de RAG.
    if context.awaiting_cadastro:
        partes = texto.splitlines()
        if len(partes) >= 4 and all(len(p.strip()) > 0 for p in partes[:4]):
            nome, cpf, email, telefone = partes[0].strip(), partes[1].strip(), partes[2].strip(), partes[3].strip()

            cpf_limpo = re.sub(r"\D", "", cpf)
            if not re.fullmatch(r"\d{11}", cpf_limpo):
                context.awaiting_cadastro = True
                return "CPF inválido no cadastro. Por favor, verifique e tente novamente."
            if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email):
                context.awaiting_cadastro = True
                return "Email inválido no cadastro. Por favor, verifique e tente novamente."

            ok, resp_db = criar_candidato(nome, cpf_limpo, email, telefone)
            context.awaiting_cadastro = False
            if ok:
                context.awaiting_sac_option = True
                return resp_db + "\n\n" + _sac_menu()
            return resp_db

    # 4. **Prioridade Máxima:** Tentar reconhecer um CPF sempre que ele for enviado
    cpf_match = re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", texto)
    if cpf_match and not context.awaiting_alternative_search: # Só busca por CPF se não estiver esperando email/telefone
        cpf_limpo = re.sub(r"\D", "", cpf_match.group())
        context.last_cpf_found = cpf_limpo
        resp_db = buscar_candidato_por_cpf(cpf_limpo)

        if "Encontramos seu cadastro" in resp_db: # Se o CPF foi encontrado
            context.awaiting_confirmation = True
        elif "Você gostaria de se cadastrar?" in resp_db: # Se o CPF não foi encontrado E sugere cadastro
            context.awaiting_cadastro = True

        return resp_db

    # 5. **NOVO FLUXO:** Lidar com busca alternativa por email/telefone
    # Este bloco só é ativado se o bot estiver no estado awaiting_alternative_search
    if context.awaiting_alternative_search:
        email_match = re.fullmatch(r"[^@]+@[^@]+\.[^@]+", texto)
        tel_digits = re.sub(r"\D", "", texto)

        resp_db_alt = None

        if email_match:
            resp_db_alt = buscar_candidato_por_email(texto)
            context.last_cpf_found = None # Resetar last_cpf_found ao buscar por outro meio
        elif 10 <= len(tel_digits) <= 11:
            resp_db_alt = buscar_candidato_por_telefone(texto)
            context.last_cpf_found = None # Resetar last_cpf_found ao buscar por outro meio

        if resp_db_alt: # Se houve uma tentativa de busca por email ou telefone
            if "Encontramos seu cadastro" in resp_db_alt:
                context.awaiting_alternative_search = False # Encontrou, sai do estado
                context.awaiting_confirmation = True
                return resp_db_alt
            elif "não encontrei seu cadastro" in resp_db_alt:
                context.awaiting_alternative_search = False # Não encontrou, sai do estado de busca alternativa
                context.awaiting_cadastro = True # Agora sim, sugere cadastro
                return resp_db_alt + " Você gostaria de se cadastrar?"
            # Caso não seja nenhuma das strings esperadas (erro de conexão, por exemplo)
            return resp_db_alt
        else: # Se o usuário não forneceu nem email nem telefone válidos no estado de busca alternativa
            return "Não consegui identificar um e-mail ou telefone válido. Por favor, digite um e-mail ou um número de telefone para continuar a busca."


    # 6. Chamada ao GPT para interpretação flexível da intenção (Só se não foi interceptado antes)
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
            # Reutiliza last_cpf_found (que pode ter sido setado por cpf, email ou tel)
            return f"Ótimo! Seus dados foram validados. Como posso te ajudar hoje?\n\n" + _sac_menu()

        elif action == "recusar_cpf":
            context.awaiting_confirmation = False
            context.last_cpf_found = None
            context.awaiting_alternative_search = True # Ativa o novo estado de busca alternativa
            return "Entendo. Por favor, informe seu melhor e-mail ou número de telefone para tentarmos localizar seu cadastro." # Mensagem padronizada

        # Se o GPT tentar uma dessas ações, mas não está no contexto de busca alternativa, o bloco 4 acima já trataria.
        # Estas ações são mais para o GPT gerar a resposta inicial.
        elif action == "fornecer_email_alternativo" or action == "fornecer_telefone_alternativo":
            # Se o GPT gerou essas ações, mas o bot não está no estado awaiting_alternative_search,
            # ele irá para o fluxo principal ou será capturado pelo bloco 4.
            # Aqui, apenas garantimos que o GPT não vai adicionar mais texto, pois o bloco 4 já faz isso.
            if context.awaiting_alternative_search: # Só continua se estiver no estado
                return processar_mensagem(texto, context) # Re-processa a mensagem, que agora será pega pelo bloco 4.
            else:
                return reply_text # Retorna a resposta do GPT se não estiver no estado específico

        elif action == "contato_alternativo":
            context.awaiting_confirmation = False
            context.awaiting_cadastro = False
            context.awaiting_sac_option = False
            context.awaiting_alternative_search = False
            return reply_text

        elif action == "ja_cliente":
            pass # Deixa o fluxo seguir para tentar reconhecer o CPF

        elif action == "nao_cliente":
            context.awaiting_cadastro = True

        elif action == "escolher_sac":
            # Esta parte só será alcançada se o bot *não* estiver em awaiting_sac_option,
            # ou se a mensagem for um número, e o GPT retornou corretamente "escolher_sac".
            if texto.isdigit() and 1 <= int(texto) <= 5:
                if texto == "5":
                    context.awaiting_sac_option = True # Mantém o estado para aguardar a dúvida avançada
                    return "Ok, poderia me descrever seu problema para eu poder te ajudar a resolver seu problema"
                else: # Para opções 1-4
                    context.awaiting_sac_option = False # A opção foi tratada, reseta o estado
                    return FAQ_SAC[texto]["resposta"]
            else:
                # Se o GPT retornou escolher_sac mas não é um dígito, e não está em awaiting_sac_option
                # (já que o bloco de forçamento trataria isso),
                # é uma interpretação errada do GPT em um contexto diferente.
                context.awaiting_sac_option = False # Reseta o estado para evitar loops
                return reply_text # Retorna o que o GPT sugeriu originalmente

        # O bloco `sac_duvida_avancada` foi movido para o início como uma prioridade.
        # Portanto, esta parte do código para `sac_duvida_avancada` não é mais necessária aqui.
        # elif action == "sac_duvida_avancada":
        #     rag_result = rag_answer(texto)
        #     context.awaiting_sac_option = False
        #     return rag_result


        # Se o GPT sugeriu algo com 'central de ajuda' ou 'menu' mas não foi uma escolha explícita do SAC
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