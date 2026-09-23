# schemas.py: Modelos Pydantic que definen la estructura de datos del sistema.
# Lógica: cada nodo del grafo DEBE devolver datos que coincidan con estos modelos.
# Pydantic valida automáticamente que el LLM devuelva el formato correcto.
# Si el LLM falla, Pydantic lanza un error que el nodo captura.
# IMPORTANTE: estos modelos son el "contrato" entre nodos. Si cambias uno,
# asegúrate de que todos los nodos que lo usan sigan funcionando.

"""Modelos Pydantic: contratos de salida de cada nodo y del resultado final."""
from __future__ import annotations  # Anotaciones de tipo diferidas (PEP 563)

from typing import Literal  # Literal: tipo que solo acepta valores específicos

# BaseModel: clase base de Pydantic para modelos de datos con validación automática.
# Field: define metadata del campo (descripción, valores por defecto, validaciones).
# model_validator: validador que se ejecuta DESPUÉS de crear el modelo (valida relaciones entre campos).
# field_validator: validador que se ejecuta en un campo específico antes de asignarlo.
from pydantic import BaseModel, Field, model_validator, field_validator


# ───────────── Prevalidación (Python puro) ─────────────
# Lógica: este modelo se genera SIN usar el LLM. El nodo "prevalidar" lo construye
# analizando el texto con regex y reglas simples. Es el paso más barato del sistema.
class Prevalidation(BaseModel):
    ok: bool                                    # True si no hay errores bloqueantes
    story_id: str | None = None                 # ID extraído (ej: "HU-01"), None si no tiene
    clean_story: str = ""                       # Texto limpio (sin ID ni espacios extra)
    word_count: int = 0                         # Número de palabras
    has_role: bool = False                      # ¿Tiene "como ..."?
    has_action: bool = False                    # ¿Tiene "quiero ..."?
    has_benefit: bool = False                   # ¿Tiene "para ..."?
    blocking_errors: list[str] = Field(default_factory=list)  # Errores que bloquean el flujo
    warnings: list[str] = Field(default_factory=list)         # Advertencias no bloqueantes
    vague_terms: list[str] = Field(default_factory=list)      # Términos vagos detectados


# ───────────── Relevancia (LLM) ─────────────
# RelevanceResult: verifica si la historia es relevante para el proyecto.
# Lógica: se ejecuta después de prevalidación y antes del análisis.
# Si la historia no es relevante, se rechaza sin gastar tokens en INVEST/ambigüedad.
class RelevanceResult(BaseModel):
    """Verificación de relevancia de la historia para el proyecto."""
    es_relevante: bool = Field(
        description="True si la historia está relacionada con el dominio, objetivos o alcances del proyecto."
    )
    puntaje_relevancia: int = Field(
        ge=0, le=10,
        description="0 = nada que ver con el proyecto, 10 = funcionalidad central del proyecto."
    )
    explicacion: str = Field(
        max_length=300,
        description="Breve explicación de por qué es o no es relevante para el proyecto."
    )
    area_proyecto: str = Field(
        default="",
        description="Área del proyecto a la que pertenece (ej: rutas, horarios, GPS, planificación)."
    )


# ───────────── Análisis (LLM) ─────────────
# Lógica: el LLM descompone la historia en sus partes y confirma si es realmente
# una historia de usuario. Si no lo es, es_historia_usuario=False.
class StoryAnalysis(BaseModel):
    """Descomposición de la historia en sus partes."""

    es_historia_usuario: bool = Field(
        description="True si el texto describe una necesidad de un usuario y no un requisito técnico o una tarea."
    )
    rol: str = Field(default="", description="Quién quiere la funcionalidad. Vacío si no aparece.")
    accion: str = Field(default="", description="Qué quiere hacer. Vacío si no aparece.")
    beneficio: str = Field(default="", description="Para qué lo quiere. Vacío si no aparece.")
    resumen: str = Field(description="Resumen de la historia en una sola frase.", max_length=300)


# ───────────── INVEST (LLM) ─────────────
# InvestCriterion: puntaje individual de UN criterio INVEST.
# Lógica: cada criterio tiene un puntaje (1-5), justificación y sugerencia.
# El model_validator garantiza que si el puntaje < 5, DEBE haber sugerencia.
class InvestCriterion(BaseModel):
    puntaje: int = Field(ge=1, le=5, description="1 = incumple totalmente, 3 = parcial, 5 = cumple plenamente.")
    justificacion: str = Field(max_length=400, description="Máximo dos frases.")
    sugerencia: str = Field(max_length=400, description="Mejora concreta. Vacío solo si el puntaje es 5.")

    @property
    def cumple(self) -> bool:
        """Retorna True si el puntaje es >= 4 (cumple el criterio)."""
        return self.puntaje >= 4

    @model_validator(mode="after")
    def _sugerencia_si_no_perfecto(self):
        """Valida que si el puntaje es menor a 5, DEBE haber sugerencia."""
        if self.puntaje < 5 and not self.sugerencia.strip():
            raise ValueError("Si el puntaje es menor a 5 debe incluir una sugerencia de mejora.")
        return self


# InvestEvaluation: evaluación completa de los 6 criterios INVEST.
# Lógica: agrupa los 6 InvestCriterion y calcula promedio y mínimo.
# El promedio se usa para el veredicto (junto con la ambigüedad).
class InvestEvaluation(BaseModel):
    independent: InvestCriterion = Field(description="Independiente")
    negotiable: InvestCriterion = Field(description="Negociable")
    valuable: InvestCriterion = Field(description="Valiosa")
    estimable: InvestCriterion = Field(description="Estimable")
    small: InvestCriterion = Field(description="Pequeña")
    testable: InvestCriterion = Field(description="Verificable")

    def items(self) -> dict[str, InvestCriterion]:
        """Retorna los 6 criterios como diccionario (para iterar fácilmente)."""
        return {
            "Independent": self.independent,
            "Negotiable": self.negotiable,
            "Valuable": self.valuable,
            "Estimable": self.estimable,
            "Small": self.small,
            "Testable": self.testable,
        }

    @property
    def promedio(self) -> float:
        """Promedio de los 6 puntajes (redondeado a 2 decimales)."""
        vals = [c.puntaje for c in self.items().values()]
        return round(sum(vals) / len(vals), 2)

    @property
    def minimo(self) -> int:
        """Puntaje más bajo de los 6 criterios."""
        return min(c.puntaje for c in self.items().values())


# ───────────── Ambigüedad (LLM) ─────────────
# AmbiguityItem: una ambigüedad individual detectada en la historia.
# Lógica: contiene el fragmento exacto, el problema y una pregunta para el PO.
class AmbiguityItem(BaseModel):
    fragmento: str = Field(description="Texto exacto de la historia que es ambiguo.")
    problema: str = Field(description="Por qué es ambiguo.", max_length=300)
    pregunta_aclaratoria: str = Field(description="Pregunta para el Product Owner que resuelve la ambigüedad.")


# AmbiguityReport: reporte completo de ambigüedades.
# Lógica: agrupa las ambigüedades y clasifica el nivel (baja/media/alta).
# El model_validator garantiza coherencia: nivel "alta" requiere >= 2 ítems.
class AmbiguityReport(BaseModel):
    items: list[AmbiguityItem] = Field(default_factory=list, max_length=8)  # Máximo 8 ambigüedades
    nivel: Literal["baja", "media", "alta"]  # Nivel de severidad

    @model_validator(mode="after")
    def _coherencia(self):
        """Valida que el nivel sea coherente con la cantidad de ambigüedades."""
        if self.nivel == "alta" and len(self.items) < 2:
            raise ValueError("Nivel 'alta' exige al menos 2 ambigüedades listadas.")
        if self.nivel == "media" and not self.items:
            raise ValueError("Nivel 'media' exige al menos 1 ambigüedad listada.")
        return self


# ───────────── Criterios de aceptación (LLM) ─────────────
# AcceptanceCriterion: un criterio individual en formato Gherkin.
# Lógica: cada criterio tiene un escenario con Dado/Cuando/Entonces.
class AcceptanceCriterion(BaseModel):
    escenario: str = Field(description="Nombre corto del escenario.", max_length=120)
    dado: str = Field(description="Precondición (Dado que...).")
    cuando: str = Field(description="Acción del usuario (Cuando...).")
    entonces: str = Field(description="Resultado observable y verificable (Entonces...).")


# AcceptanceCriteria: lista de criterios de aceptación.
# Lógica: entre 2 y 6 criterios por historia.
class AcceptanceCriteria(BaseModel):
    criterios: list[AcceptanceCriterion] = Field(min_length=2, max_length=6)


# ───────────── Reescritura (LLM) ─────────────
# RewriteSuggestion: reescritura de la historia para que cumpla INVEST.
# Lógica: conserva la intención original, elimina implementación y términos vagos.
# El field_validator garantiza que la historia reescrita tenga el formato correcto.
class RewriteSuggestion(BaseModel):
    historia_mejorada: str = Field(description="Historia reescrita: Como [rol], quiero [acción], para [beneficio].")
    cambios: list[str] = Field(min_length=1, max_length=8, description="Qué se cambió y por qué.")
    preguntas_pendientes: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("historia_mejorada")
    @classmethod
    def _formato(cls, v: str) -> str:
        """Valida que la historia reescrita tenga el formato 'Como ..., quiero ..., para ...'."""
        low = v.lower()
        if not (low.strip().startswith("como") and "quiero" in low and "para" in low):
            raise ValueError("La historia debe tener el formato 'Como ..., quiero ..., para ...'.")
        return v.strip()


# ───────────── Resultado final ─────────────
# Veredicto: tipo literal que define los 6 posibles veredictos.
# Lógica: el veredicto NO lo decide el LLM. Lo decide Python con reglas fijas
# en la función compute_verdict() de nodes.py.
Veredicto = Literal[
    "aprobada",                    # Cumple INVEST, ambigüedad baja
    "aprobada_con_observaciones",  # Cumple parcialmente, tiene puntos por mejorar
    "requiere_reescritura",        # No cumple INVEST mínimo o ambigüedad alta
    "rechazada",                   # No es historia de usuario o falló prevalidación
    "no_relevante",                # La historia no es relevante para el proyecto
    "no_evaluada",                 # Fallaron los nodos LLM (error técnico)
]


# FinalResult: resultado completo de la validación.
# Lógica: agrupa TODA la información generada por el grafo.
# Se retorna al usuario final (CLI, API, Streamlit).
class FinalResult(BaseModel):
    historia_original: str                         # Texto original de entrada
    story_id: str | None = None                    # ID extraído (ej: "HU-01")
    veredicto: Veredicto                           # Veredicto determinista
    puntaje_invest: float | None = None            # Promedio INVEST (0-5)
    resumen: str                                   # Resumen del veredicto
    prevalidacion: Prevalidation | None = None     # Resultado de prevalidación
    relevancia: RelevanceResult | None = None      # Verificación de relevancia
    analisis: StoryAnalysis | None = None          # Descomposición del LLM
    invest: InvestEvaluation | None = None         # Evaluación INVEST
    ambiguedad: AmbiguityReport | None = None      # Reporte de ambigüedades
    criterios: AcceptanceCriteria | None = None    # Criterios Gherkin
    reescritura: RewriteSuggestion | None = None   # Historia reescrita
    proveedores_usados: list[str] = Field(default_factory=list)  # Proveedores LLM usados
    errores: list[str] = Field(default_factory=list)             # Errores acumulados
