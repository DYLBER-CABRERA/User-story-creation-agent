# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------------
# cli.py — Interfaz de línea de comandos del validador de historias de usuario.
# Lógica general: lee una o varias historias de usuario, las pasa por un grafo
# LangGraph (build_graph) que las valida, y muestra/imprime el resultado (texto o JSON).
# ---------------------------------------------------------------------------

# Docstring del módulo: se muestra al ejecutar `python -m validador.cli --help`.
# No es código ejecutable (es la documentación del módulo).
"""Uso por consola:
    python -m validador.cli "Como pasajero, quiero ..., para ..."
    python -m validador.cli --file historias.txt      # una historia por línea
    python -m validador.cli --file historias.txt --json > resultados.json
"""
# from __future__ import annotations: pospone la evaluación de anotaciones de tipo
# (por ejemplo "list[str]") a modo de cadenas, permitiendo sintaxis moderna sin
# romper versiones viejas de Python. Se importa "desde el futuro" del módulo.
from __future__ import annotations

# Importa el módulo estándar argparse, usado para parsear argumentos de consola
# (define la interfaz de línea de comandos de forma declarativa).
import argparse
# Importa el módulo estándar json, usado para serializar resultados a formato JSON.
import json
# Importa el módulo estándar sys, usado para escribir errores en stderr.
import sys

# Importación relativa: importa la función `build_graph` del módulo `graph`
# que está en el mismo paquete (validador). Es quien construye el grafo LangGraph.
from .graph import build_graph

# Diccionario que asigna cada posible veredicto (clave) a un icono (valor).
# Se usa para mostrar el resultado de forma visual en consola.
# Lógica: centraliza el mapeo "estado -> emoji" para no repetirlo en el print.
ICONOS = {
    "aprobada": "✅",                 # Clave: historia aprobada -> icono check verde.
    "aprobada_con_observaciones": "🟡",  # Aprobada pero con observaciones -> círculo amarillo.
    "requiere_reescritura": "🟠",     # Requiere reescribirse -> círculo naranja.
    "rechazada": "❌",                # Rechazada -> aspa roja.
    "no_evaluada": "⚠️",              # No se evaluó (por error/contexto) -> signo de advertencia.
}


# Definición de la función principal `main`. No recibe argumentos porque el punto
# de entrada la llama sin parámetros; devuelve un entero (código de salida).
def main() -> int:
    # Crea el parser de argumentos con una descripción breve (se ve en --help).
    ap = argparse.ArgumentParser(description="Validador de historias de usuario (LangGraph)")
    # Argumento posicional `story` (opcional): la historia en texto plano.
    # nargs="?" lo hace opcional; si está ausente vale None.
    ap.add_argument("story", nargs="?", help="Texto de la historia")
    # Opción `--file`: ruta de un archivo con una historia por línea.
    ap.add_argument("--file", help="Archivo con una historia por línea")
    # Opción `--context` con valor por defecto "" (cadena vacía): describe el proyecto.
    ap.add_argument("--context", default="", help="Descripción del proyecto")
    # Opción `--json` (bandera): si está presente vale True y se imprime JSON.
    ap.add_argument("--json", action="store_true", help="Imprime el resultado completo en JSON")
    # Parsea los argumentos de la línea de comandos (sys.argv[1:]) y los guarda en `args`.
    args = ap.parse_args()

    # Lista de tipo list[str] que irá acumulando las historias a validar.
    stories: list[str] = []
    # Lógica: decide de dónde salen las historias (archivo, argumento o error).
    if args.file:
        # Si se pasó --file, abre el archivo en modo lectura con codificación UTF-8
        # (encoding utf-8 para soportar acentos/ñ). El bloque `with` cierra el archivo solo.
        with open(args.file, encoding="utf-8") as fh:
            # Comprensión de lista: recorre cada línea del archivo, le quita espacios
            # laterales (strip), y la conserva solo si NO está vacía y NO empieza por "#".
            # Lógica: ignora líneas en blanco y comentarios (#) del archivo de entrada.
            stories = [ln.strip() for ln in fh if ln.strip() and not ln.strip().startswith("#")]
    elif args.story:
        # Si no hay --file pero sí una historia pasada como argumento, la envuelve en una lista.
        stories = [args.story]
    else:
        # Ni archivo ni historia: muestra el mensaje de uso y termina con error (código 2).
        ap.error("Indica una historia o usa --file")

    # Construye el grafo LangGraph llamando a build_graph() (importado al inicio).
    # Lógica: el grafo se reutiliza para validar todas las historias.
    graph = build_graph()
    # Lista donde se guardarán los objetos resultado de cada validación.
    results = []
    # Bucle: itera sobre cada historia de la lista `stories`.
    for st in stories:
        # Lógica: invoca el grafo de LangGraph pasando un diccionario con la entrada
        # (la historia cruda y el contexto del proyecto). El grafo ejecuta el flujo
        # de validación y devuelve el estado final, que se guarda en `out`.
        out = graph.invoke({"raw_story": st, "project_context": args.context})
        # Del estado de salida extrae el campo "result" (el objeto con el veredicto).
        r = out["result"]
        # Añade el resultado a la lista acumuladora.
        results.append(r)
        # Lógica: solo imprime el formato legible si NO se pidió --json.
        if not args.json:
            # Imprime una línea por resultado usando el icono según el veredicto,
            # el id (o "-" si no existe), el veredicto, el puntaje de investigación,
            # y el resumen. El formateo con :6, :28 etc. alinea columnas.
            print(f"{ICONOS[r.veredicto]} {r.story_id or '-':6} {r.veredicto:28} INVEST={r.puntaje_invest}  {r.resumen}")
            # Si el resultado trae una reescritura sugerida, la imprime indentada.
            # Lógica: el atributo puede ser None, por eso se evalúa como condición.
            if r.reescritura:
                print(f"     ↳ Sugerida: {r.reescritura.historia_mejorada}")
            # Bucle: recorre los errores del resultado y los imprime en stderr
            # (flujo de errores estándar, para separarlos de la salida normal).
            for e in r.errores:
                print(f"     ! {e}", file=sys.stderr)
    # Lógica: si se pidió --json, imprime TODO el resultado (lista de resultados)
    # serializado a JSON con indentación de 2 espacios y sin escapar caracteres UTF-8.
    if args.json:
        print(json.dumps([r.model_dump(mode="json") for r in results], ensure_ascii=False, indent=2))
    # Devuelve código de salida 0 = ejecución exitosa.
    return 0


# Guardia de ejecución: solo ejecuta main() cuando el script se corre directamente
# (python -m validador.cli) y no cuando se importa como módulo.
# __name__ vale "__main__" solo en el módulo que se ejecuta directamente.
if __name__ == "__main__":
    # Llama a main() y usa su valor de retorno como código de salida del proceso.
    # raise SystemExit es lo que convierte el entero en código de terminación del shell.
    raise SystemExit(main())
