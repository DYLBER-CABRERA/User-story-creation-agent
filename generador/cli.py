"""Interfaz de consola del generador.

Uso:
    python -m generador.cli
    python -m generador.cli --pasajero 6 --conductor 5 --administrador 4
    python -m generador.cli --app "Mi App" --context "..." --out historias.txt
    python -m generador.cli --provider gemini --model gemini-2.5-flash

python -m paquete.modulo ejecuta el módulo como script (__name__ == "__main__").
"""
from __future__ import annotations  # anotaciones perezosas

# argparse: librería estándar para parsear flags de línea de comandos
# (--pasajero 6, --provider gemini, etc.) con ayuda automática y tipos.
import argparse
# sys: acceso a streams estándar; sys.stderr permite imprimir mensajes de
# progreso sin mezclarlos con el resultado (stdout limpio para piping/| head)
import sys

# get_settings: config del .env (orden de proveedores por defecto, modelos)
from .config import get_settings
# Constantes y función principal de generación (mismo paquete)
from .generar import APP_NAME_DEFAULT, CONTEXT_DEFAULT, generar_historias


def main() -> int:
    """Parsea args, genera historias, imprime resultado y retorna código de salida.

    Retorna int: 0 = éxito, 1 = error (se usa como exit code del proceso).
    """
    s = get_settings()  # config del .env (una sola lectura al inicio)
    # provider_order[0] si existe, si no "ollama" (default razonable)
    default_provider = s.provider_order[0] if s.provider_order else "ollama"
    # Sanidad: si .env tiene un nombre raro, forzar ollama en vez de fallar después
    if default_provider not in ("ollama", "gemini"):
        default_provider = "ollama"

    # argparse.ArgumentParser: define el esquema de la CLI y genera --help solo
    ap = argparse.ArgumentParser(description="Genera historias de usuario con Ollama o Gemini (con respaldo automático)")
    # --pasajero N: type=int convierte el string del CLI a entero;
    # default=6 si no se pasa el flag (mismos defaults que generar_historias)
    ap.add_argument("--pasajero", type=int, default=6)
    ap.add_argument("--conductor", type=int, default=5)
    ap.add_argument("--administrador", type=int, default=4)
    ap.add_argument("--app", default=APP_NAME_DEFAULT)        # {app_name} del prompt
    ap.add_argument("--context", default=CONTEXT_DEFAULT)     # {context} del prompt
    ap.add_argument("--out", help="Archivo .txt donde guardar el resultado (además de imprimirlo)")
    # choices=[...] restringe valores válidos; argparse falla solo si es inválido
    ap.add_argument(
        "--provider",
        choices=["ollama", "gemini"],
        default=default_provider,
        help=f"Proveedor principal (respaldo: el otro). Por defecto: {default_provider}",
    )
    ap.add_argument(
        "--model",
        default=None,  # None => "usa el del .env" (se resuelve más abajo)
        help="Modelo del proveedor elegido (por defecto: el del .env)",
    )
    args = ap.parse_args()  # Namespace con todos los flags ya tipados

    # Traduce el flag --provider a orden de fallbacks:
    #   ollama primero, gemini como respaldo (o al revés)
    order = ("ollama", "gemini") if args.provider == "ollama" else ("gemini", "ollama")
    # --model tiene prioridad; si no, el modelo del .env según el proveedor elegido
    modelo = args.model or (s.ollama_model if args.provider == "ollama" else s.gemini_model)

    # Mensaje de progreso en stderr -> no contamina el JSON/txt que sale por stdout
    print(f"Generando con {args.provider} ({modelo})…", file=sys.stderr)
    try:
        # Llamada ÚNICA al LLM (la complejidad de retry/fallback vive en generar.py)
        historias, segundos = generar_historias(
            n_pasajero=args.pasajero,
            n_conductor=args.conductor,
            n_admin=args.administrador,
            app_name=args.app,
            context=args.context,
            order=order,                       # orden primario/respaldo
            modelos={args.provider: modelo},   # override del modelo elegido
        )
    except Exception as exc:  # noqa: BLE001  (cualquier error de red/modelo/validación)
        # Captura TODO y sale con 1: la consola no debe imprimir traceback al usuario
        print(f"Error: {exc}", file=sys.stderr)
        return 1  # exit code de fallo

    # Formateo del txt de salida (stdout): secciones por rol
    lineas: list[str] = []
    # Lista de tuplas (título, lista) para iterar sin repetir código
    for titulo, lista in [("PASAJERO", historias.pasajero), ("CONDUCTOR", historias.conductor), ("ADMINISTRADOR", historias.administrador)]:
        lineas.append(f"\n ## {titulo}")                # encabezado de sección
        lineas.extend(h.texto for h in lista)           # extend agrega CADA línea
        # (h.texto es la property de schemas.py: "HU-P01: Como..., para ...")
    texto = "\n".join(lineas).strip()  # une con saltos y recorta bordes

    print(texto)  # resultado limpio por stdout (pipeable a archivo u otro proceso)
    # stderr: métricas de rendimiento/provenance (segundos, proveedor, modelo)
    print(f"\n(generado en {segundos:.1f} s con {args.provider} · {modelo})", file=sys.stderr)

    if args.out:  # --out opcional
        # encoding="utf-8" -> tildes y ñ se guardan bien (portable entre SO)
        with open(args.out, "w", encoding="utf-8") as fh:  # with cierra el archivo solo
            fh.write(texto + "\n")  # newline final (buena práctica en txt)
        print(f"Guardado en {args.out}", file=sys.stderr)
    return 0  # exit code de éxito


# Guard de ejecución: True solo si corrimos "python -m generador.cli",
# False si otro archivo hace "from .cli import main" (no debe autoejecutarse).
if __name__ == "__main__":
    # raise SystemExit(0|1): termina el proceso con el código retornado por main()
    raise SystemExit(main())
