# shared_context.py

_ultima_vaga_detalhada = None

def set_ultima_vaga_detalhada(nome_vaga: str):
    global _ultima_vaga_detalhada
    _ultima_vaga_detalhada = nome_vaga

def get_ultima_vaga_detalhada() -> str:
    return _ultima_vaga_detalhada
