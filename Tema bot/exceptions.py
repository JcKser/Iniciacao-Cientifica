# exceptions.py
class RAGFallbackError(Exception):
    """
    Exceção para acionar o fluxo de criação de ticket 
    quando o RAG não puder responder.
    """
    pass