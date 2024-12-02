from flask import Flask, request, send_from_directory
from twilio.twiml.messaging_response import MessagingResponse
import random
from listas import respostas_iniciais, keywords_listavagas, resposta_listavagas, respostas_positivas, respostas_negativas
from banco.database import listar_vagas_ordenadas, buscar_detalhes_vaga
from rapidfuzz import process, fuzz
from banco.db import gerar_pdf_relatorio_flexivel
import os
from openai import OpenAI
from dotenv import load_dotenv  # Importa dotenv para carregar variáveis de ambiente


app = Flask(__name__)
# Carregar variáveis do arquivo .env
load_dotenv()  # Sem necessidade de especificar o caminho se o .env estiver na mesma pasta.

# Recuperar a chave da API
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("A chave OPENAI_API_KEY não foi encontrada no arquivo .env")


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
        palavra_similar, similaridade = resultado[0], resultado[1]
        return True, palavra_similar
    return False, None

def processar_resposta_usuario(mensagem, historico_intencao, lista_mensagens):
    """
    Processa a resposta do usuário e lida com respostas positivas, negativas e mensagens fora do escopo.
    """
    print(f"Mensagem recebida: {mensagem}")
    print(f"Histórico de intenção: {historico_intencao}")

    # Função auxiliar para detectar a intenção com fuzziness
    def detectar_resposta(categorias, mensagem_usuario, limiar=75):
        resultado = process.extractOne(mensagem_usuario, categorias, scorer=fuzz.ratio)
        if resultado and resultado[1] >= limiar:  # Verifica se a similaridade está acima do limiar
            return True, resultado[0]
        return False, None

    # Verificar se a intenção é gerar relatório
    if historico_intencao and historico_intencao[-1]["intencao"] == "gerar_relatorio":
        nome_vaga = historico_intencao[-1]["vaga"]
        print(f"Nome da vaga: {nome_vaga}")

        # Detectar respostas positivas ou negativas
        positiva, resposta_positiva_detectada = detectar_resposta(respostas_positivas, mensagem.lower())
        negativa, resposta_negativa_detectada = detectar_resposta(respostas_negativas, mensagem.lower())

        if positiva:
            try:
                # Gera o nome do arquivo e o caminho do PDF
                nome_arquivo = f"relatorio_{nome_vaga.replace(' ', '_').lower()}.pdf"
                caminho_destino = gerar_pdf_relatorio_flexivel(nome_arquivo=nome_arquivo, nome_vaga=nome_vaga)

                # Base URL e timestamp para criar o link com cache-busting
                base_url = request.host_url
                timestamp = int(os.path.getmtime(caminho_destino))
                link_pdf = f"{base_url}static/{nome_arquivo}?v={timestamp}"

                # Texto com link "implícito"
                mensagem_com_link = f'O relatório foi gerado com sucesso! Acesse aqui: [> PDF]({link_pdf})'

                # Adiciona a mensagem à lista de respostas
                lista_mensagens.append({"role": "assistant", "content": mensagem_com_link})
                print(f"Relatório gerado com sucesso: {link_pdf}")
                return mensagem_com_link, lista_mensagens
            except Exception as e:
                print(f"Erro ao gerar relatório: {e}")
                lista_mensagens.append({"role": "assistant", "content": "Erro ao gerar o relatório. Tente novamente mais tarde."})
                return "Erro ao gerar o relatório. Tente novamente mais tarde.", lista_mensagens

        elif negativa:
            # Resposta negativa: Apenas encerra a intenção
            print(f"Resposta negativa detectada: {resposta_negativa_detectada}")
            return "Entendido! Se precisar de mais informações, é só perguntar.", lista_mensagens

        else:
            # Mensagem não corresponde a nenhuma categoria
            print("Mensagem fora do escopo.")
            return (
                "Desculpe, não entendi sua resposta. Por favor, responda com 'sim' para gerar o relatório ou 'não' caso não deseje o relatório.",
                lista_mensagens,
            )

    # Caso nenhuma intenção correspondente seja encontrada
    print("Nenhuma intenção correspondente encontrada.")
    return None, lista_mensagens


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

def buscar_vaga_flexivel(nome_vaga, historico_intencao, nome_vaga_armazem):
    """
    Busca uma vaga com uma correspondência flexível no nome e retorna os detalhes.
    """
    if not nome_vaga:
        return "Por favor, forneça um nome de vaga válido para buscar os detalhes."
    
    vagas = listar_vagas_ordenadas()  # Lista todas as vagas disponíveis
    if not vagas:
        return "Não há vagas disponíveis para buscar no momento."

    nomes_vagas = [vaga['nome'] for vaga in vagas]  # Extrai os nomes das vagas
    
    # Encontra a vaga mais similar ao nome fornecido
    resultado = process.extractOne(nome_vaga, nomes_vagas)
    print(f"Resultado da correspondência: {resultado}")
    
    if resultado:
        nome_candidato, similaridade = resultado[0], resultado[1]
        print(f"Vaga encontrada: {nome_candidato} com similaridade de {similaridade}%")
        
        # Definir um limite de similaridade para aceitar a correspondência
        if similaridade >= 85:
            vaga_encontrada = next((vaga for vaga in vagas if vaga['nome'] == nome_candidato), None)
            if vaga_encontrada:
                # Armazena o nome da vaga encontrada no armazém
                nome_vaga_armazem.append(vaga_encontrada['nome'])
                return buscar_detalhes_vaga(vaga_encontrada['nome'], historico_intencao, nome_vaga_armazem)

    return f"Desculpe, não consegui encontrar nenhuma vaga parecida com '{nome_vaga}'. Tente novamente com outro nome ou verifique a lista de vagas disponíveis."

def enviar_mensagem(mensagem, lista_mensagens):
    """
    Processa a mensagem do usuário, gerando respostas baseadas em intenções,
    incluindo geração de relatórios, listagem de vagas e detalhamento de uma vaga.
    """
    global historico_intencao

    # Verificar se a última intenção é gerar relatório
    # Verificar se a última intenção é gerar relatório
    if historico_intencao and historico_intencao[-1]["intencao"] == "validar_detalhes_vaga":
        positiva_resultado = process.extractOne(mensagem.lower(), respostas_positivas, scorer=fuzz.ratio)
        negativa_resultado = process.extractOne(mensagem.lower(), respostas_negativas, scorer=fuzz.ratio)

        positiva = positiva_resultado[0] if positiva_resultado and positiva_resultado[1] >= 75 else None
        negativa = negativa_resultado[0] if negativa_resultado and negativa_resultado[1] >= 75 else None

        if positiva:
            # Recuperar o nome da vaga
            nome_vaga = historico_intencao[-1]["vaga"]
            try:
                # Gerar o relatório
                nome_arquivo = f"relatorio_{nome_vaga.replace(' ', '_').lower()}.pdf"
                caminho_destino = gerar_pdf_relatorio_flexivel(nome_arquivo=nome_arquivo, nome_vaga=nome_vaga)

                base_url = request.host_url
                timestamp = int(os.path.getmtime(caminho_destino))
                link_pdf = f"{base_url}static/{nome_arquivo}?v={timestamp}"

                resposta_texto = f"O relatório foi gerado com sucesso!\n\nAcesse o relatório clicando no link abaixo:\n{link_pdf}"
                lista_mensagens.append({"role": "assistant", "content": resposta_texto})
                return resposta_texto, lista_mensagens
            except Exception as e:
                print(f"Erro ao gerar relatório: {e}")
                resposta_texto = "Erro ao gerar o relatório. Tente novamente mais tarde."
                lista_mensagens.append({"role": "assistant", "content": resposta_texto})
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

    similaridade_corte = 80  # Define a porcentagem mínima de similaridade

    # Reconhecer a palavra-chave com similaridade
    match, palavra_similar = reconhecer_palavra_chave(mensagem.lower(), keywords_listavagas)
    if match:
        similaridade = fuzz.ratio(mensagem.lower(), palavra_similar.lower())
        
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


    # 4. Buscar detalhes da vaga
    detalhes_vaga = buscar_vaga_flexivel(mensagem, historico_intencao, nome_vaga_armazem)

    if detalhes_vaga != "Desculpe, não encontrei detalhes para essa vaga ou ela não está aberta no momento.":
        nome_vaga = nome_vaga_armazem[-1] if nome_vaga_armazem else "vaga não especificada"
        historico_intencao.append({"intencao": "validar_detalhes_vaga", "vaga": nome_vaga})
        lista_mensagens.append({"role": "assistant", "content": detalhes_vaga + "\n\nDeseja um relatório desta vaga? Responda 'sim' para gerar o relatório."})
        return detalhes_vaga, lista_mensagens

    # 5. Adicionar mensagem do usuário ao histórico
    lista_mensagens.append({"role": "user", "content": mensagem})

    # 6. Resumir mensagens se exceder o limite de tokens
    total_tokens = sum([contar_tokens(m['content']) for m in lista_mensagens])
    if total_tokens > 2048:
        resumo = resumir_mensagens(lista_mensagens)
        lista_mensagens = [{"role": "system", "content": resumo}]

    # 7. Adicionar mensagem inicial do sistema se não estiver presente
    if not any(m['role'] == 'system' for m in lista_mensagens):
        lista_mensagens.insert(0, {
            "role": "system",
            "content": (
                "Você é um assistente de RH. Responda apenas a perguntas relacionadas a recrutamento, "
                "vagas e processos seletivos. Para perguntas fora desse contexto, responda com 'Desculpe, "
                "sou um assistente de RH e só posso responder perguntas relacionadas a recrutamento, vagas e processos seletivos.'"
            )
        })

    # 8. Enviar mensagem para a API OpenAI
    try:
        resposta = OpenAI.chat.completions.create(
            messages=lista_mensagens,
            model="gpt-4",
        )
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
    lista_mensagens = []  # Lista para armazenar o histórico de mensagens
    
    resposta_texto, lista_mensagens = enviar_mensagem(mensagem, lista_mensagens)
    
    # Responder ao usuário usando Twilio
    resposta = MessagingResponse()
    resposta.message(resposta_texto)
    return str(resposta)



@app.route('/')
def index():
    return "Servidor está funcionando"

@app.route('/static/<path:filename>', methods=['GET'])
def download_file(filename):
    # Serve arquivos da pasta static
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)