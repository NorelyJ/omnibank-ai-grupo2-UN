import re
import spacy
from dataclasses import dataclass, field
from typing import List

nlp = spacy.load('es_core_news_sm')

# Patrones para datos bancarios colombianos
PATRONES = [
    (r'\b\d{10}\b',                        '[CC_REDACTED]'),
    (r'\b\d{16}\b',                        '[TARJETA_REDACTED]'),
    (r'\b\d{9,11}\b',                      '[CUENTA_REDACTED]'),
    (r'[\w.-]+@[\w.-]+\.\w{2,4}',         '[EMAIL_REDACTED]'),
    (r'\+?57[\s-]?\d{10}',                '[TEL_REDACTED]'),
    (r'\b3\d{9}\b',                        '[CEL_REDACTED]'),
]

@dataclass
class ResultadoRedaccion:
    texto_original:  str
    texto_redactado: str
    pii_encontrada:  bool
    tipos_removidos: List[str] = field(default_factory=list)

def redactar_pii(texto: str) -> ResultadoRedaccion:
    """Elimina PII del texto antes de enviarlo al LLM."""
    resultado = texto
    tipos = []

    # Paso 1: patrones regex
    for patron, reemplazo in PATRONES:
        if re.search(patron, resultado):
            tipos.append(reemplazo)
        resultado = re.sub(patron, reemplazo, resultado)

    # Paso 2: entidades con spaCy (nombres, lugares)
    doc = nlp(resultado)
    for ent in reversed(doc.ents):   # reversed para no desplazar índices
        if ent.label_ in ('PER',):
            resultado = resultado[:ent.start_char] + '[NOMBRE_REDACTED]' + resultado[ent.end_char:]
            tipos.append('PER')

    return ResultadoRedaccion(
        texto_original  = texto,
        texto_redactado = resultado,
        pii_encontrada  = len(tipos) > 0,
        tipos_removidos = list(set(tipos)),
    )
