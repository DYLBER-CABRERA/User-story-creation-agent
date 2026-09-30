"""Uso:
    python -m generador.cli
    python -m generador.cli --pasajero 6 --conductor 5 --administrador 4
    python -m generador.cli --app "Mi App" --context "..." --out historias.txt
    python -m generador.cli --provider gemini --model gemini-2.5-flash
    python -m generador.cli --spec all --json historias.json
    python -m generador.cli --spec rutas            # solo SPEC-001
    python -m generador.cli --debug-prompt          # prompt exacto + tiempo por intento
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import get_settings
from .generar import APP_NAME_DEFAULT, CONTEXT_DEFAULT, generar_historias
from .specs import construir_specs, contexto_proyecto, escribir_specs, seleccionar


def main() -> int:
    s = get_settings()
    default_provider = s.provider_order[0] if s.provider_order else "ollama"
    if default_provider not in ("ollama", "gemini", "groq"):
        default_provider = "ollama"

    ap = argparse.ArgumentParser(description="Genera historias de usuario con Ollama, Gemini o Groq (con respaldo automático)")
    ap.add_argument("--pasajero", type=int, default=6)
    ap.add_argument("--conductor", type=int, default=5)
    ap.add_argument("--administrador", type=int, default=4)
    ap.add_argument("--app", default=APP_NAME_DEFAULT)
    ap.add_argument(
        "--context",
        default=contexto_proyecto() or CONTEXT_DEFAULT,
        help="Contexto para el modelo (por defecto: generado desde docs/alcance-contexto-proyecto.md)",
    )
    ap.add_argument("--out", help="Archivo .txt donde guardar el resultado (además de imprimirlo)")
    ap.add_argument(
        "--provider",
        choices=["ollama", "gemini", "groq"],
        default=default_provider,
        help=f"Proveedor principal (respaldo: los otros). Por defecto: {default_provider}",
    )
    ap.add_argument(
        "--model",
        default=None,
        help="Modelo del proveedor elegido (por defecto: el del .env)",
    )
    ap.add_argument(
        "--spec",
        nargs="?",
        const="all",
        default=None,
        metavar="FUNCIONALIDAD",
        help="Exporta SPECs tras generar: sin valor o 'all' = las 12; o un número/slug (003, rutas)",
    )
    ap.add_argument(
        "--json",
        dest="json_out",
        default=None,
        metavar="ARCHIVO",
        help="Guarda las historias generadas en JSON (para python -m generador.specs --historias ...)",
    )
    ap.add_argument(
        "--debug-prompt",
        action="store_true",
        help="Imprime en stderr el prompt exacto que se envía al modelo y el tiempo de cada intento",
    )
    args = ap.parse_args()

    order = (args.provider,) + tuple(
        p for p in ("ollama", "gemini", "groq") if p != args.provider
    )
    modelo = args.model or {
        "ollama": s.ollama_model,
        "gemini": s.gemini_model,
        "groq": s.groq_model,
    }[args.provider]

    print(f"Generando con {args.provider} ({modelo})…", file=sys.stderr)
    try:
        historias, segundos = generar_historias(
            n_pasajero=args.pasajero,
            n_conductor=args.conductor,
            n_admin=args.administrador,
            app_name=args.app,
            context=args.context,
            order=order,
            modelos={args.provider: modelo},
            debug=args.debug_prompt,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    lineas: list[str] = []
    for titulo, lista in [("PASAJERO", historias.pasajero), ("CONDUCTOR", historias.conductor), ("ADMINISTRADOR", historias.administrador)]:
        lineas.append(f"\n## {titulo}")
        lineas.extend(h.detalle for h in lista)
    texto = "\n".join(lineas).strip()

    print(texto)
    print(f"\n(generado en {segundos:.1f} s con {args.provider} · {modelo})", file=sys.stderr)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(texto + "\n")
        print(f"Guardado en {args.out}", file=sys.stderr)

    if args.json_out:
        Path(args.json_out).write_text(historias.model_dump_json(indent=2), encoding="utf-8")
        print(f"Historias guardadas en {args.json_out}", file=sys.stderr)

    if args.spec is not None:
        docs = seleccionar(construir_specs(historias), args.spec)
        if not docs:
            print(f"Ninguna SPEC coincide con '{args.spec}'.", file=sys.stderr)
            return 1
        rutas = escribir_specs(docs)
        print(f"{len(rutas)} SPEC(s) escritas en {rutas[0].parent}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
