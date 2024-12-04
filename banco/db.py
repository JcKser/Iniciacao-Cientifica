from fpdf import FPDF
import os
import mysql.connector
import matplotlib.pyplot as plt
from rapidfuzz import process
import datetime
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env
load_dotenv()

# Configurações do banco de dados usando variáveis de ambiente
db_config = {
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'port': os.getenv('DB_PORT'),
}

# Pasta para salvar relatórios e gráficos
UPLOAD_FOLDER = os.path.join(os.getcwd(), "static")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Classe para geração de PDF
class PDF(FPDF):
    def header(self):
        self.set_font("Arial", style="B", size=18)
        title_text = "Relatório de Métricas"
        page_width = self.w
        title_width = self.get_string_width(title_text)
        title_x_position = (page_width - title_width) / 2
        self.text(x=title_x_position, y=15, txt=title_text)
    
    # Adiciona o texto explicativo logo abaixo do título
        self.ln(20)  # Move para a próxima linha após o título
        texto_explicativo = (
        "Segundo a análise dos dados da vaga, apresentamos as principais métricas "
        "relacionadas ao processo seletivo, incluindo o engajamento dos candidatos, desempenho das "
        "etapas e perfil dos inscritos."
    )
        self.set_font("Arial", size=13)
        self.multi_cell(0, 8, texto_explicativo, align="J")
        self.ln(5)  # Adiciona um pequeno espaçamento após o texto explicativo

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", size=8)
        self.cell(0, 10, f"Página {self.page_no()}", align='C')

    def add_section_title(self, title):
        self.set_font("Arial", style="B", size=14)
        self.set_fill_color(220, 220, 220)
        self.set_text_color(0, 0, 0)
        self.cell(0, 10, title, ln=True, align='C', fill=True)
        self.ln(5)

    def add_metric(self, label, value):
        self.set_font("Arial", size=11)
        self.cell(0, 8, f"{label}: {value}", ln=True)

# Funções utilitárias para manipulação do banco de dados
def executar_query(query, params=None):
    try:
        with mysql.connector.connect(**db_config) as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(query, params or ())
                return cursor.fetchall()
    except mysql.connector.Error as e:
        print(f"Erro ao executar query: {e}")
        return []
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn.is_connected():
            conn.close()

def format_autopct(pct):
    return f'{pct:.1f}%'  # Formato dos números


def buscar_metricas_por_vaga(nome_vaga):
    query = """
        SELECT 
            ps.nome AS vaga, 
            COALESCE(mv.visualizacoes, 0) AS visualizacoes,
            COALESCE(mv.inscricoes, 0) AS inscricoes,
            COALESCE(mv.inscricoes_iniciadas, 0) AS inscricoes_iniciadas,
            COALESCE(mv.desistencias, 0) AS desistencias,
            COALESCE(ps.data_criacao, '0000-00-00') AS data_criacao
        FROM 
            metricas_vagas mv
        JOIN 
            processos_seletivos ps 
        ON 
            mv.processo_id = ps.id
        WHERE 
            ps.nome = %s
    """
    metricas = executar_query(query, (nome_vaga,))
    if not metricas:
        print(f"Nenhuma métrica encontrada para a vaga: {nome_vaga}")
    return metricas

def buscar_metricas_por_vaga_flexivel(frase_usuario):
    vagas = executar_query("SELECT nome FROM processos_seletivos")
    vagas_disponiveis = [vaga['nome'] for vaga in vagas]

    print(f"Vagas disponíveis no banco: {vagas_disponiveis}")
    print(f"Frase do usuário: {frase_usuario}")

    nome_vaga = encontrar_nome_vaga(frase_usuario, vagas_disponiveis)
    print(f"Nome da vaga encontrada: {nome_vaga}")

    if not nome_vaga:
        print(f"Nenhuma vaga encontrada na frase: {frase_usuario}")
        return None

    return buscar_metricas_por_vaga(nome_vaga)

def encontrar_nome_vaga(frase_usuario, vagas_disponiveis):
    resultado = process.extractOne(frase_usuario, vagas_disponiveis, score_cutoff=85)
    print(f"Resultado da correspondência: {resultado}")
    if resultado:
        return resultado[0]
    return None

# Funções para criar gráficos
def criar_grafico_pizza(metricas, nome_arquivo="grafico_metricas.png"):
    if not metricas:
        print("Nenhuma métrica encontrada para gerar o gráfico.")
        return None

    # Inicializar categorias e valores
    categorias = []
    valores = []

    # Processar os dados para o gráfico
    for metrica in metricas:
        total_visualizacoes = metrica.get("visualizacoes", 0)
        total_inscricoes = metrica.get("inscricoes", 0)

        # Verificar dados válidos
        if total_visualizacoes > 0:
            # Adicionar categorias e proporções
            categoria_inscritos = f"{metrica['vaga']} \n (Inscritos)"
            categoria_nao_inscritos = f"{metrica['vaga']}\n (Não Inscritos)"

            # Ajustar para rótulos longos
            categoria_inscritos = "\n".join(categoria_inscritos.split(" ", 3))
            categoria_nao_inscritos = "\n".join(categoria_nao_inscritos.split(" ", 3))

            categorias.append(categoria_inscritos)
            categorias.append(categoria_nao_inscritos)

            # Calcular porcentagens
            inscritos = (total_inscricoes / total_visualizacoes) * 100
            nao_inscritos = 100 - inscritos

            valores.extend([inscritos, nao_inscritos])
        else:
            print(f"Vaga ignorada: '{metrica['vaga']}' - Visualizações inválidas ou zero.")

    # Verificar se há valores válidos e categorias correspondentes
    if not valores or len(categorias) != len(valores):
        print("Erro: As categorias e os valores não correspondem.")
        return None

    # Criar gráfico de pizza
    try:
        fig, ax = plt.subplots(figsize=(10, 8))
        wedges, texts, autotexts = ax.pie(
            valores,
            labels=categorias,
            autopct=format_autopct,  # Adiciona os números
            startangle=140,
            colors=plt.cm.Paired.colors,  # Define uma paleta de cores
            textprops={'fontsize': 18}  # Ajusta o tamanho dos rótulos (categorias)
)
        for autotext in autotexts:
            autotext.set_fontsize(18)  # Aumenta o tamanho da fonte dos números
        # Configurar título
        plt.title("Porcentagem de Inscrições por Visualizaçao", fontsize=25, fontweight="bold")

        # Salvar gráfico
        caminho_grafico = os.path.join(UPLOAD_FOLDER, nome_arquivo)
        plt.tight_layout()
        plt.savefig(caminho_grafico)
        plt.close()

        return caminho_grafico
    except Exception as e:
        print(f"Erro ao criar gráfico: {e}")
        return None



# Função para geração de relatório em PDF
# Função para geração de relatório em PDF
def gerar_pdf_relatorio_flexivel(nome_arquivo=None, frase_usuario=None, nome_vaga=None):
    try:
        # Garantir que um nome de arquivo seja definido
        if not nome_arquivo:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_vaga_safe = nome_vaga.replace(' ', '_').lower() if nome_vaga else 'flexivel'
            nome_arquivo = f"relatorio_{nome_vaga_safe}_{timestamp}.pdf"

        # Validar entrada e buscar métricas
        if nome_vaga:
            print(f"Gerando relatório para a vaga: {nome_vaga}")
            metricas = buscar_metricas_por_vaga(nome_vaga)
        elif frase_usuario:
            print(f"Gerando relatório com base na frase do usuário: {frase_usuario}")
            metricas = buscar_metricas_por_vaga_flexivel(frase_usuario)
        else:
            print("Nenhuma frase ou nome da vaga fornecido.")
            return "Nenhuma frase ou nome da vaga fornecido para gerar o relatório."

        if not metricas:
            mensagem = f"Nenhuma métrica encontrada para o relatório de {nome_vaga or frase_usuario}."
            print(mensagem)
            return mensagem

        # Criar gráfico
        caminho_grafico = criar_grafico_pizza(metricas)
        if not caminho_grafico:
            print("Erro ao criar gráfico ou nenhum dado para gerar.")
            return "Gráfico não pôde ser gerado devido à falta de dados."

        # Gerar PDF
        pdf = PDF()
        pdf.set_margins(left=25, top=10, right=25)
        pdf.set_auto_page_break(auto=True, margin=15)

        pdf.add_page()
    
        titulo = f"Métricas de {nome_vaga or 'Todas as Vagas'}"
        pdf.add_section_title(titulo)

        for metrica in metricas:
            pdf.set_font("Arial", size=13)  # Define o tamanho da fonte
            pdf.set_text_color(90, 90, 90)

            # Adiciona a métrica com texto cinza
            pdf.cell(0, 10, f"Visualizações: {metrica.get('visualizacoes', 0)}", ln=True)

            # Adicionar número de inscrições
            # Adiciona a métrica com o novo estilo
            pdf.cell(0, 10, f"Clicaram em se inscrever: {metrica.get('inscricoes_iniciadas', 0)}", ln=True)
            pdf.cell(0, 10, f"Inscritos: {metrica.get('inscricoes', 0)}", ln=True)
            pdf.cell(0, 10, f"Visualizados: {metrica.get('visualizacoes', 0)}", ln=True)
            
            # Adicionar data de criação da vaga
            data_criacao = metrica.get("data_criacao")
            if data_criacao and data_criacao != "0000-00-00":
                try:
                    # Converter data_criacao para datetime
                    data_criacao_dt = datetime.datetime.strptime(data_criacao, "%Y-%m-%d")
                    pdf.cell(0, 10, f"Data de Criação: {data_criacao_dt.strftime('%d/%m/%Y')}", ln=True)

                    
                    # Calcular tempo decorrido
                    tempo_decorrido = (datetime.datetime.now() - data_criacao_dt).days
                    pdf.cell(0, 10, f"Tempo Decorrido (dias): {tempo_decorrido}", ln=True)
                except ValueError:
                    pdf.cell(0, 10, f"Data de Criação: Data Inválida", ln=True)

                    pdf.cell(0, 10, f"Tempo Decorrido (dias): Erro de Calcúlo", ln=True)
            else:
                pdf.cell(0, 10, f"Data de Criação: Data não Disponível", ln=True)
                pdf.cell(0, 10, f"Tempo Decorrido (dias): Data não Disponível", ln=True)
        
       # Adiciona o título da seção
        pdf.add_section_title("Analise de Estatísticas")

        # Verifica se o gráfico existe
        # Adiciona gráfico e texto explicativo ao lado
        if caminho_grafico and os.path.exists(caminho_grafico):
            pdf.ln(10)  # Espaçamento antes do conteúdo

            # Coordenadas iniciais
            x_start = pdf.get_x()
            y_start = pdf.get_y()

            # Insere o gráfico à esquerda
            pdf.image(caminho_grafico, x=x_start, y=y_start, w=80, h=60)  # Gráfico menor e ajustado à esquerda

            # Define a posição para o texto à direita
            texto_x = x_start + 85  # Ajuste para não ultrapassar o gráfico
            texto_y = y_start  # Alinhar verticalmente com o gráfico
            pdf.set_xy(texto_x, texto_y)  # Define a posição inicial do texto

            # Texto explicativo com cálculos
            pdf.set_font("Arial", style="", size=10)
            pdf.set_text_color(0, 0, 0)  # Preto
            largura_texto = pdf.w - texto_x - pdf.r_margin  # Largura ajustada considerando margem direita

            # Cálculos das taxas
            for metrica in metricas:
                visualizacoes = metrica.get("visualizacoes", 0)
                inscricoes_iniciadas = metrica.get("inscricoes_iniciadas", 0)
                inscritos = metrica.get("inscricoes", 0)
                desistencias = metrica.get("desistencias", 0)

                taxa_engajamento = (inscricoes_iniciadas / visualizacoes) * 100 if visualizacoes > 0 else 0
                taxa_conversao = (inscritos / visualizacoes) * 100 if visualizacoes > 0 else 0
                taxa_conclusao = (inscritos / inscricoes_iniciadas) * 100 if inscricoes_iniciadas > 0 else 0
                taxa_desistencia = (desistencias / inscricoes_iniciadas) * 100 if inscricoes_iniciadas > 0 else 0

                # Adicionar texto com os cálculos
                pdf.set_font("Arial", size=12)  # Alterando o tamanho da fonte para 12
                pdf.set_text_color(90, 90, 90)
                pdf.multi_cell(largura_texto, 7, (
                    "Segundo as métricas, pode-se gerar alguns dados sobre taxas:\n\n"
                    f"Taxa de Engajamento: {taxa_engajamento:.2f}% \n"
                    f"Taxa de Conversão: {taxa_conversao:.2f}% \n"
                    f"Taxa de Conclusão: {taxa_conclusao:.2f}% \n"
                    f"Taxa de Desistência: {taxa_desistencia:.2f}% "
                ), align="L")

            # Retornar para nova linha após gráfico e texto
            pdf.ln(5)
        else:
            print("Erro: Gráfico não encontrado.")



        # Salvar PDF no diretório
        caminho_destino = os.path.join(UPLOAD_FOLDER, nome_arquivo)
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
        pdf.output(caminho_destino)
        print(f"Relatório PDF gerado em: {caminho_destino}")
        return caminho_destino

    except Exception as e:
        print(f"Erro ao gerar relatório: {e}")
        return f"Erro ao gerar o relatório: {str(e)}"
