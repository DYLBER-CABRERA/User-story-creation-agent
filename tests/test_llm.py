"""Pruebas de build_providers: orden de proveedores, overrides y omisión de Gemini.

No se abre conexión real: solo se construyen los objetos de cliente
(ChatOllama/ChatGoogleGenerativeAI), que no hacen red hasta .invoke().
"""
# Settings: dataclass inmutable de la config (aquí se fabrica una "falsa"
# sin leer .env, controlando cada valor de prueba)
from generador.config import Settings
# build_providers: la función bajo prueba (arma la lista ordenada de proveedores)
from generador.llm import build_providers


def mk_settings(**kwargs):
    """Crea Settings con valores base de prueba; **kwargs pisa lo que se pase.

    **kwargs: empaqueta argumentos con nombre en un dict -> base.update(kwargs)
    sobreescribe solo los campos que el test quiera cambiar (p.ej. google_api_key="").
    """
    base = dict(
        ollama_model="phi3:mini",                     # modelo de prueba (liviano)
        ollama_base_url="http://localhost:11434",     # URL típica de Ollama
        ollama_num_ctx=4096,                          # contexto por defecto
        ollama_num_predict=1800,                      # tope de generación
        google_api_key="fake-key",                    # clave ficticia (sin red real)
        gemini_model="gemini-2.5-flash",              # modelo Gemini por defecto
        provider_order=("ollama", "gemini"),          # orden por defecto del .env
        temperature=0.4,                              # temperatura por defecto
    )
    base.update(kwargs)  # aplicar overrides del test sobre los defaults
    # Settings(**base): unpacking de dict -> cada llave es un parámetro del dataclass
    return Settings(**base)


def test_order_respeta_gemini_como_primario():
    """order=("gemini","ollama") debe devolver esa lista EXACTA en ese orden."""
    s = mk_settings()  # settings estándar con clave ficticia presente
    provs = build_providers(s, order=("gemini", "ollama"))
    # Comprensión: extrae solo los nombres (tuplas (nombre, llm) -> nombre)
    assert [n for n, _ in provs] == ["gemini", "ollama"]
    # "_" es la convención de "valor que no se usa" (el cliente LLM)


def test_order_default_es_el_del_env():
    """Sin `order` explícito, se respeta settings.provider_order (.env)."""
    s = mk_settings()  # provider_order=("ollama", "gemini")
    provs = build_providers(s)  # order=None -> cae al del settings
    assert [n for n, _ in provs] == ["ollama", "gemini"]


def test_modelos_sobreescribe_el_elegido():
    """modelos={"ollama": "qwen2.5:7b"} pisa SOLO el modelo de Ollama."""
    s = mk_settings()
    # dict(...) convierte la lista de tuplas en {nombre: cliente} para lookup directo
    provs = dict(build_providers(s, order=("ollama", "gemini"), modelos={"ollama": "qwen2.5:7b"}))
    assert provs["ollama"].model == "qwen2.5:7b"        # modelo elegido por el usuario
    assert provs["gemini"].model == "gemini-2.5-flash"  # el no elegido conserva el .env


def test_gemini_sin_api_key_se_omite():
    """Sin GOOGLE_API_KEY, build_providers descarta Gemini (continue en llm.py)."""
    # google_api_key="" -> condición `if not s.google_api_key` es True -> continue
    s = mk_settings(google_api_key="")
    provs = build_providers(s, order=("gemini", "ollama"))
    # Solo queda Ollama: el sistema no falla, queda en modo solo-local
    assert [n for n, _ in provs] == ["ollama"]
