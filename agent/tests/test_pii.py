import pytest
from pii_filter import redactar_pii

def test_cedula_redactada():
    r = redactar_pii('Mi cédula es 1023456789')
    assert '[CC_REDACTED]' in r.texto_redactado
    assert '1023456789' not in r.texto_redactado
    assert r.pii_encontrada is True

def test_email_redactado():
    r = redactar_pii('Escríbeme a juan.perez@gmail.com por favor')
    assert '[EMAIL_REDACTED]' in r.texto_redactado
    assert 'juan.perez@gmail.com' not in r.texto_redactado

def test_tarjeta_redactada():
    r = redactar_pii('Tengo problemas con mi tarjeta 4111111111111111')
    assert '[TARJETA_REDACTED]' in r.texto_redactado

def test_celular_redactado():
    r = redactar_pii('Llámame al 3001234567')
    assert '[CEL_REDACTED]' in r.texto_redactado

def test_texto_limpio_sin_cambios():
    texto = '¿Cuál es la tasa de interés del CDT a 90 días?'
    r = redactar_pii(texto)
    assert r.pii_encontrada is False
    assert r.texto_redactado == texto

def test_multiples_pii():
    r = redactar_pii('Soy 1023456789 y mi correo es ana@banco.co')
    assert '[CC_REDACTED]' in r.texto_redactado
    assert '[EMAIL_REDACTED]' in r.texto_redactado
