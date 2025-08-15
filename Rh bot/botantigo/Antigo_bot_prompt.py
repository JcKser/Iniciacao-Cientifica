from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import random
from listas import respostas_iniciais, keywords_listavagas, resposta_listavagas, respostas_positivas, respostas_negativas, frases_buscar_vaga
from banco.database import listar_vagas_ordenadas, buscar_detalhes_vaga
from rapidfuzz import process, fuzz
from banco.db import gerar_pdf_relatorio_flexivel, buscar_metricas_por_vaga
import os
from openai import OpenAI
from dotenv import load_dotenv  # Importa dotenv para carregar variáveis de ambiente


app = Flask(__name__)
# Carregar variáveis do arquivo .env
load_dotenv()  # Sem necessidade de especificar o caminho se o .env estiver na mesma pasta.

# Recuperar a chave da API
client = OpenAI(
  api_key=os.environ['OPENAI_API_KEY']  # this is also the default, it can be omitted
)



UPLOAD_FOLDER = os.path.join(os.getcwd(), "static")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Variável global para armazenar o histórico de intenções
historico_intencao = []
nome_vaga_armazem = []

def reconhecer_palavra_chave(mensagem, keywords_listavagas, similaridade_minima=95):
    """
    Verifica se a mensagem contém uma palavra-chave com similaridade suficiente.
    """
    resultado = process.extractOne(
        mensagem, keywords_listavagas, score_cutoff=similaridade_minima
    )
    if resultado:
        palavra_similar = resultado[0]
        return True, palavra_similar
    return False, None
    # Remove this block as it is redundant

def detectar_resposta(mensagem, categorias, limiar=75):
    """
    Detecta se a mensagem do usuário corresponde a alguma categoria usando fuzzy matching.
    """
    resultado = process.extractOne(mensagem.lower(), categorias, scorer=fuzz.ratio)
    if resultado and resultado[1] >= limiar:
        return resultado[0]
    return None

def processar_resposta_usuario(mensagem, historico_intencao, lista_mensagens):
    """
    Processa a intenção do usuário com base no histórico de intenções.
    """
    # Verifica se lista_mensagens é uma lista
    if not isinstance(lista_mensagens, list):
        raise TypeError("A variável 'lista_mensagens' deve ser uma lista.")

    if not historico_intencao:
        return None, "Nenhuma intenção no histórico."

    ultima_intencao = historico_intencao[-1]["intencao"]

    # Intenção: Validar detalhes da vaga
    if ultima_intencao == "validar_detalhes_vaga":
        nome_vaga = historico_intencao[-1]["vaga"]
        metricas = buscar_metricas_por_vaga(nome_vaga)

        if metricas:
            detalhes_metricas = "\n📊 **Métricas Adicionais:**\n"
            for metrica in metricas:
                detalhes_metricas += (
                    f"- Visualizações: {metrica.get('visualizacoes', 0)}\n"
                    f"- Inscrições: {metrica.get('inscricoes', 0)}\n"
                    f"- Inscrições Iniciadas: {metrica.get('inscricoes_iniciadas', 0)}\n"
                    f"- Desistências: {metrica.get('desistencias', 0)}\n"
                )
            pergunta = "Deseja um relatório PDF com mais detalhes sobre essas métricas?"
            lista_mensagens.append({"role": "assistant", "content": detalhes_metricas})
            
            # Atualiza a intenção para "oferecer_gerar_pdf"
            historico_intencao.append({"intencao": "oferecer_gerar_pdf", "vaga": nome_vaga})
            return f"{detalhes_metricas}\n\n{pergunta}", lista_mensagens
        else:
            return None, "Não consegui encontrar métricas adicionais para esta vaga."

    # Intenção: Oferecer geração de PDF
    elif ultima_intencao == "oferecer_gerar_pdf":
        positiva = detectar_resposta(mensagem, respostas_positivas)
        negativa = detectar_resposta(mensagem, respostas_negativas)

        if positiva:
            # Atualiza a intenção para "confirmar_gerar_pdf"
            historico_intencao.append({"intencao": "confirmar_gerar_pdf", "vaga": historico_intencao[-1]["vaga"]})
            return "Você confirma que deseja gerar o relatório PDF?", lista_mensagens

        elif negativa:
            return "Entendido! Se precisar de mais informações, estou aqui para ajudar.", lista_mensagens

    # Intenção: Confirmar geração de PDF
    elif ultima_intencao == "confirmar_gerar_pdf":
        positiva = detectar_resposta(mensagem, respostas_positivas)
        negativa = detectar_resposta(mensagem, respostas_negativas)

        if positiva:
            nome_vaga = historico_intencao[-1]["vaga"]
            try:
                nome_arquivo = f"relatorio_{nome_vaga.replace(' ', '_').lower()}.pdf"
                caminho_destino = gerar_pdf_relatorio_flexivel(nome_arquivo=nome_arquivo, nome_vaga=nome_vaga)

                base_url = request.host_url
                timestamp = int(os.path.getmtime(caminho_destino))
                link_pdf = f"{base_url}static/{nome_arquivo}?v={timestamp}"

                resposta_pdf = f"O relatório foi gerado com sucesso!\n\nAcesse o relatório clicando no link abaixo:\n{link_pdf}"
                lista_mensagens.append({"role": "assistant", "content": resposta_pdf})
                return resposta_pdf, lista_mensagens
            except Exception as e:
                print(f"Erro ao gerar relatório: {e}")
                return "Erro ao gerar o relatório. Tente novamente mais tarde.", lista_mensagens

        elif negativa:
            return "Entendido! Se precisar de mais informações, estou aqui para ajudar.", lista_mensagens

        # Caso a resposta não seja clara
        return "Desculpe, não entendi sua resposta. Você deseja gerar o relatório PDF?", lista_mensagens

def calcular_taxas_por_vaga(nome_vaga):
    """
    Calcula taxas específicas (engajamento, conversão, conclusão, desistência) para uma vaga.
    """
    metricas = buscar_metricas_por_vaga(nome_vaga)
    if not metricas:
        return f"Não encontrei métricas para a vaga '{nome_vaga}'."

    for metrica in metricas:
        visualizacoes = metrica.get("visualizacoes", 0)
        inscricoes_iniciadas = metrica.get("inscricoes_iniciadas", 0)
        inscritos = metrica.get("inscricoes", 0)
        desistencias = metrica.get("desistencias", 0)
# Testando o agente no terminal
    taxa_engajamento = (inscricoes_iniciadas / visualizacoes) * 100 if visualizacoes > 0 else 0
    taxa_conversao = (inscritos / visualizacoes) * 100 if visualizacoes > 0 else 0
    taxa_conclusao = (inscritos / inscricoes_iniciadas) * 100 if inscricoes_iniciadas > 0 else 0
    taxa_desistencia = (desistencias / inscricoes_iniciadas) * 100 if inscricoes_iniciadas > 0 else 0

    return (
        f"📊 Taxas para a vaga '{nome_vaga}':\n"
        f"- Taxa de Engajamento: {taxa_engajamento:.2f}%\n"
        f"- Taxa de Conversão: {taxa_conversao:.2f}%\n"
        f"- Taxa de Conclusão: {taxa_conclusao:.2f}%\n"
        f"- Taxa de Desistência: {taxa_desistencia:.2f}%"
    )

# Testando o agente no terminal
if __name__ == "__main__":
    print("🤖 Assistente de RH iniciado. Pergunte sobre vagas disponíveis!")


def contar_tokens(texto):
    """Conta tokens aproximados de uma string."""
    return len(texto.split())

def resumir_mensagens(lista_mensagens):
    """Resumir as mensagens para reduzir o total de tokens."""
    conteudo_completo = " ".join(m['content'] for m in lista_mensagens if m['role'] != 'system')
    resumo = OpenAI.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "Resuma as seguintes mensagens de conversa para manter o contexto:"},
                  {"role": "user", "content": conteudo_completo}]
    ).choices[0].message['content']
    return resumo

def buscar_vaga_flexivel(nome_vaga, vagas):
    """
    Busca uma vaga com correspondência flexível e retorna os detalhes ou erro.
    """
    if not nome_vaga.strip():
        return None, "Por favor, forneça um nome de vaga válido para buscar os detalhes."

    nomes_vagas = [vaga['nome'] for vaga in vagas]
    resultado = process.extractOne(nome_vaga, nomes_vagas, scorer=fuzz.ratio)

    if resultado:
        nome_candidato, similaridade = resultado[0], resultado[1]
        if similaridade >= 85:
            vaga_encontrada = next((vaga for vaga in vagas if vaga['nome'] == nome_candidato), None)
            return vaga_encontrada, None

    return None, f"Desculpe, não consegui encontrar nenhuma vaga parecida com '{nome_vaga}'. Tente novamente."

def enviar_mensagem(mensagem, lista_mensagens):
    """
    Processa a mensagem do usuário, gerando respostas baseadas em intenções,
    incluindo geração de relatórios, listagem de vagas e detalhamento de uma vaga.
    """
    global historico_intencao
    positiva = detectar_resposta(mensagem, respostas_positivas)
    negativa = detectar_resposta(mensagem, respostas_negativas)

    # 1. Processar respostas do usuário
        # Verificar se a última intenção é metrificar ou gerar pdf
    if positiva:
        resposta_texto, lista_mensagens = processar_resposta_usuario(mensagem, historico_intencao, lista_mensagens)
        if resposta_texto:
            return resposta_texto, lista_mensagens

    elif negativa:
        resposta_texto = "Entendido! Se precisar de mais informações, é só perguntar."
        lista_mensagens.append({"role": "assistant", "content": resposta_texto})
        return resposta_texto, lista_mensagens
    
  
   
    # 2. Verificar saudações iniciais
    saudacoes = ["oi", "olá", "hello", "hey", "bom dia", "boa tarde", "boa noite"]
    if any(saudacao in mensagem.lower() for saudacao in saudacoes) and len(lista_mensagens) == 0:
        resposta_texto = random.choice(respostas_iniciais)
        lista_mensagens.append({"role": "assistant", "content": resposta_texto})
        return resposta_texto, lista_mensagens

    # 3. Verificar intenção de listar vagas
          # Reconhecer a palavra-chave com similaridade
    similaridade_corte = 80  # Define a porcentagem mínima de similaridade   
    match, palavra_similar = reconhecer_palavra_chave(mensagem.lower(), keywords_listavagas)
    if match:
        similaridade = fuzz.ratio(mensagem.lower(), palavra_similar.lower())
    while True:
        mensagem = input("Usuário: ")
        if mensagem.lower() in ["sair", "exit", "quit"]:
            print("Encerrando o assistente. Até mais! 👋")
            break
        
        if similaridade >= similaridade_corte:  # Verifica se a similaridade é maior ou igual ao corte
            vagas = listar_vagas_ordenadas()
            resposta_texto = random.choice(resposta_listavagas) + "\n"
            for vaga in vagas:
                resposta_texto += f"- {vaga['nome']}\n"
            historico_intencao.append({"intencao": "listar_vagas"})
            lista_mensagens.append({"role": "assistant", "content": resposta_texto})
            return resposta_texto, lista_mensagens
        else:
            resposta_texto = "Desculpe, não entendi bem. Pode reformular sua pergunta?"
            lista_mensagens.append({"role": "assistant", "content": resposta_texto})
            return resposta_texto, lista_mensagens
    
    # 4. Verificar pedidos de taxas por vaga


    # Verificar se o usuário está buscando detalhes de uma vaga
    # Buscar detalhes da vaga
    # Buscar detalhes da vaga
    if any(fuzz.partial_ratio(mensagem.lower(), frase) >= 80 for frase in frases_buscar_vaga) or \
        (historico_intencao and historico_intencao[-1]["intencao"] == "listar_vagas") or \
        mensagem.lower() in [vaga['nome'].lower() for vaga in listar_vagas_ordenadas()]:  # Nome da vaga diretamente

        # Listar todas as vagas
        vagas = listar_vagas_ordenadas()

        # Extrair o nome da vaga da mensagem
        nome_vaga = None

        # Detectar a frase base e extrair o texto que vem após ela
        for frase in frases_buscar_vaga:
            if fuzz.partial_ratio(mensagem.lower(), frase) >= 87:
                nome_vaga = mensagem.lower().split(frase)[-1].strip()
                break

        # Caso nenhuma frase seja encontrada, assume que a mensagem é o nome da vaga
        if not nome_vaga:
            nome_vaga = mensagem.lower()

        # Buscar vaga correspondente
        vaga_encontrada, erro = buscar_vaga_flexivel(nome_vaga, vagas)

        if erro:
            lista_mensagens.append({"role": "assistant", "content": erro})
            return erro, lista_mensagens

        if vaga_encontrada:
            # Retornar os detalhes da vaga
            detalhes_vaga = buscar_detalhes_vaga(vaga_encontrada['nome'], historico_intencao, nome_vaga_armazem)
            historico_intencao.append({"intencao": "validar_detalhes_vaga", "vaga": vaga_encontrada['nome']})
            lista_mensagens.append({"role": "assistant", "content": detalhes_vaga})
            return detalhes_vaga, lista_mensagens


  
    # 6. Adicionar mensagem do usuário ao histórico
    lista_mensagens.append({"role": "user", "content": mensagem})

    # 7. Resumir mensagens se exceder o limite de tokens
    total_tokens = sum([contar_tokens(m['content']) for m in lista_mensagens])
    if total_tokens > 2048:
        resumo = resumir_mensagens(lista_mensagens)
        lista_mensagens = [{"role": "system", "content": resumo}]

    # 8. Adicionar mensagem inicial do sistema se não estiver presente
    if not any(m['role'] == 'system' for m in lista_mensagens):
        lista_mensagens.insert(0, {
            "role": "system",
            "content": (
                "Você é um assistente de RH. Responda apenas a perguntas relacionadas a recrutamento, "
                "vagas e processos seletivos. Para perguntas fora desse contexto, responda com 'Desculpe, "
                "sou um assistente de RH e só posso responder perguntas relacionadas a recrutamento, vagas e processos seletivos.'"
            )
        })

    try:
        # Chamada à nova API usando o cliente
        resposta = client.chat.completions.create(
            model="gpt-4",
            messages=lista_mensagens
        )

        # Extraindo a resposta do objeto retornado
        resposta_texto = resposta.choices[0].message.content
        lista_mensagens.append({"role": "assistant", "content": resposta_texto})
        return resposta_texto, lista_mensagens

    except Exception as e:
        print(f"Erro na API OpenAI: {e}")
        resposta_texto = "Erro ao processar sua solicitação. Tente novamente mais tarde."
        lista_mensagens.append({"role": "assistant", "content": resposta_texto})
        return resposta_texto, lista_mensagens


@app.route('/bot', methods=['POST'])
def bot():
    mensagem = request.form.get('Body')  # Captura a mensagem do usuário via POST
    lista_mensagens = []  # Sempre inicialize como uma lista
    
    resposta_texto, lista_mensagens = enviar_mensagem(mensagem, lista_mensagens)
    
    # Responder ao usuário usando Twilio
    resposta = MessagingResponse()
    resposta.message(resposta_texto)
    return str(resposta)


@app.route('/')
def index():
    return "Servidor está funcionando"

if __name__ == "__main__":
    app.run(debug=True)
