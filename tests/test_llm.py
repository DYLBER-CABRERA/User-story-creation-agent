from generador.config import Settings
from generador.llm import build_providers


def mk_settings(**kwargs):
    base = dict(
        ollama_model="phi3:mini",
        ollama_base_url="http://localhost:11434",
        ollama_num_ctx=4096,
        ollama_num_predict=1800,
        google_api_key="fake-key",
        gemini_model="gemini-2.5-flash",
        groq_api_key="",
        groq_model="qwen/qwen3.8-27b",
        provider_order=("ollama", "gemini"),
        temperature=0.4,
    )
    base.update(kwargs)
    return Settings(**base)


def test_order_respeta_gemini_como_primario():
    s = mk_settings()
    provs = build_providers(s, order=("gemini", "ollama"))
    assert [n for n, _ in provs] == ["gemini", "ollama"]


def test_order_default_es_el_del_env():
    s = mk_settings()
    provs = build_providers(s)
    assert [n for n, _ in provs] == ["ollama", "gemini"]


def test_modelos_sobreescribe_el_elegido():
    s = mk_settings()
    provs = dict(build_providers(s, order=("ollama", "gemini"), modelos={"ollama": "qwen2.5:7b"}))
    assert provs["ollama"].model == "qwen2.5:7b"
    assert provs["gemini"].model == "gemini-2.5-flash"  # el no elegido conserva el .env


def test_gemini_sin_api_key_se_omite():
    s = mk_settings(google_api_key="")
    provs = build_providers(s, order=("gemini", "ollama"))
    assert [n for n, _ in provs] == ["ollama"]


def test_groq_como_tercer_proveedor():
    s = mk_settings(groq_api_key="gsk_fake")
    provs = build_providers(s, order=("groq",))
    assert [n for n, _ in provs] == ["groq"]
    assert provs[0][1].model == "qwen/qwen3.8-27b"
    # con los tres disponibles: el orden pedido se respeta
    provs3 = build_providers(s, order=("ollama", "gemini", "groq"))
    assert [n for n, _ in provs3] == ["ollama", "gemini", "groq"]


def test_groq_sin_api_key_se_omite():
    s = mk_settings(groq_api_key="")
    provs = build_providers(s, order=("groq", "ollama"))
    assert [n for n, _ in provs] == ["ollama"]
