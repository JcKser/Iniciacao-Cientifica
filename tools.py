from langchain.tools import tool
from banco.database import listar_vagas_ordenadas, buscar_detalhes_vaga
from banco.db import buscar_metricas_por_vaga, gerar_pdf_relatorio_flexivel
from openai import OpenAI
import os
from shared_context import set_ultima_vaga_detalhada, get_ultima_vaga_detalhada

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@tool
def verificar_vagas_disponiveis():
    """Verifica se há vagas disponíveis.
    Se houver, retorna uma resposta simples perguntando se o usuário deseja vê-las.
    """
    vagas = listar_vagas_ordenadas()
    
    if vagas:
        prompt = """
        Você é um assistente de RH amigável e informal. Responda de maneira natural sem formatação especial.
        Exemplos: 
        Ótima notícia! Temos vagas abertas. Quer dar uma olhada?
        Sim, temos oportunidades disponíveis. Quer que eu te mostre?
        Temos algumas posições abertas. Gostaria que eu listasse elas para você?
        Gere uma nova resposta sem repetir os exemplos.
        """
        resposta = client.chat.completions.create(
            model="gpt-4",
            temperature=0.9,
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip()
        resposta = resposta.lstrip("•-").strip().strip('"')
        return resposta
    else:
        return "No momento, não temos vagas disponíveis. Mas fique de olho que sempre abrimos novas oportunidades!"

@tool
def listar_vagas():
    """Lista todas as vagas disponíveis no momento com uma introdução dinâmica."""
    vagas = listar_vagas_ordenadas()
    
    if vagas:
        prompt = """
        Você é um assistente de RH. Gere uma introdução natural para uma lista de vagas disponíveis sem formatação especial.
        Exemplos: 
        Aqui estão as vagas abertas no momento:
        Essas são as oportunidades disponíveis agora:
        Atualmente, temos essas posições em aberto:
        Gere uma nova introdução sem repetir os exemplos.
        """
        introducao = client.chat.completions.create(
            model="gpt-4",
            temperature=0.9,
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip()
        introducao = introducao.lstrip("•-").strip().strip('"')
        resposta = f"{introducao}\n"
        for vaga in vagas:
            resposta += f"{vaga['nome']}\n"
        return resposta.strip()
    else:
        return "Nenhuma vaga está disponível no momento."

@tool
def detalhar_vaga(nome_vaga: str):
    """
    Retorna os detalhes de uma vaga específica conforme registrado no banco de dados.
    Além disso, armazena o nome da vaga no contexto global para que, se o usuário
    pedir métricas depois, não seja necessário extrair novamente do texto.
    """
    # Armazena a vaga detalhada no contexto
    set_ultima_vaga_detalhada(nome_vaga)

    historico_intencao = []
    nome_vaga_armazem = []
    return buscar_detalhes_vaga(nome_vaga, historico_intencao, nome_vaga_armazem)
@tool
def mostrar_metricas(nome_vaga: str):
    """Exibe as métricas avançadas da vaga informada.
    Após exibir os dados, pergunta se o usuário deseja gerar um relatório PDF.
    """
    metricas = buscar_metricas_por_vaga(nome_vaga)
    if metricas:
        detalhes_metricas = "📊 Métricas Adicionais:\n"
        for metrica in metricas:
            detalhes_metricas += (
                f"Visualizações: {metrica.get('visualizacoes', 0)}\n"
                f"Inscrições: {metrica.get('inscricoes', 0)}\n"
                f"Inscrições Iniciadas: {metrica.get('inscricoes_iniciadas', 0)}\n"
                f"Desistências: {metrica.get('desistencias', 0)}\n\n"
            )
        pergunta = "Deseja um relatório PDF com mais detalhes sobre essas métricas?"
        return detalhes_metricas + pergunta
    else:
        return "Não consegui encontrar métricas adicionais para esta vaga."

@tool
def gerar_pdf(nome_vaga: str):
    """Gera um relatório em PDF para a vaga especificada e retorna um link para download.
    Utiliza a função gerar_pdf_relatorio_flexivel do arquivo db.py.
    """
    try:
        nome_arquivo = f"relatorio_{nome_vaga.replace(' ', '_').lower()}.pdf"
        caminho_destino = gerar_pdf_relatorio_flexivel(nome_arquivo=nome_arquivo, nome_vaga=nome_vaga)
        
        base_url = os.getenv("BASE_URL", "http://localhost:5000/")
        timestamp = int(os.path.getmtime(caminho_destino))
        link_pdf = f"{base_url}static/{nome_arquivo}?v={timestamp}"
        
        resposta_pdf = (
            "\nO relatório foi gerado com sucesso!\n"
            "Acesse o relatório clicando no link abaixo:\n" + link_pdf
        )
        return resposta_pdf
    except Exception as e:
        print(f"Erro ao gerar relatório: {e}")
        return "Erro ao gerar o relatório. Tente novamente mais tarde."
