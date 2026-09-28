# SPEC-002 — Consulta de horarios

| Campo | Valor |
|-------|-------|
| Versión | 1.0 |
| Estado | Borrador — pendiente de aprobación humana |
| Funcionalidad | Consulta de horarios |
| Actores | Pasajero |
| Generado | 2026-09-27 (automático) |

> Fuente: `docs/alcance-contexto-proyecto.md` + historias de usuario generadas.
> Estructura según la sección 7 de la guía del Specification Agent.

## 1. Objetivo
Informar los horarios, frecuencia y días de operación de cada ruta.

## 2. Contexto
El público en general desconoce las rutas, los horarios y los tiempos de llegada de
las busetas en Manizales. No existe una forma sencilla de saber qué buseta pasa por
dónde, a qué hora pasa, ni cuánto falta para que llegue a una parada.

**BusetasApp** es una aplicación para consultar las rutas de las busetas de Manizales.
Permite:

* ver las rutas y sus paradas en un mapa,
* consultar horarios y días de operación,
* ver la ubicación de las busetas en tiempo real y el tiempo estimado de llegada (ETA),
* planificar un viaje indicando origen y destino,
* buscar rutas por número, nombre, barrio o punto de interés.

Además, incluye un módulo para administradores (gestionar la operación) y un módulo
para conductores (reportar la posición de la buseta durante el recorrido).

## 3. Alcance
- hora de inicio y fin de operación de cada ruta, frecuencia aproximada y días de servicio (lunes a viernes, sábados, domingos y festivos).

Ver también **Fuera de alcance** (§14 de esta SPEC).

## 4. Actores
- **Pasajero**

## 5. Requisitos funcionales
> **Pendiente:** sin historias asignadas en la corrida actual. Genere historias (app o CLI) y vuelva a exportar.

## 6. Requisitos no funcionales
> **Pendiente:** los requisitos no funcionales (rendimiento, disponibilidad, seguridad...)
> aún no están definidos en el documento de alcance. Responsable: Equipo.

## 7. Reglas de negocio
- **BR-01:** Cualquier persona puede consultar rutas, horarios y mapa sin crear una cuenta.

## 8. Flujos principales
> **Pendiente:** sin historias asignadas en la corrida actual. Genere historias (app o CLI) y vuelva a exportar.

## 9. Flujos alternativos
> **Pendiente:** sin historias asignadas en la corrida actual. Genere historias (app o CLI) y vuelva a exportar.

## 10. Casos límite
> **Pendiente:** sin historias asignadas en la corrida actual. Genere historias (app o CLI) y vuelva a exportar.
- Casos límite adicionales (concurrencia, valores extremos): **pendiente de análisis** (guía §2.6).

## 11. Criterios de aceptación
> **Pendiente:** sin historias asignadas en la corrida actual. Genere historias (app o CLI) y vuelva a exportar.

## 12. Dependencias
> **Pendiente:** corresponde a la etapa de arquitectura, no definida en este documento.

## 13. Restricciones
Proyecto académico. 4 integrantes: Dylber Cabrera, Miguel Rojas, Leidy Nieto,
Sophia Cardona. Plazo: 8 semanas desde cero.

---

## 14. Fuera de alcance
* Pago de pasajes, tarjetas de recarga y cualquier manejo de dinero.
* Transporte fuera de Manizales: taxis, transporte informal y rutas intermunicipales.
* Definiciones tecnológicas: plataforma (web, móvil), APIs, base de datos y
  arquitectura — se deciden en una etapa posterior a las historias de usuario.

## 15. Preguntas abiertas
| ID | Pregunta | Responsable | Estado |
|-----|----------|-------------|--------|
| OPEN-Q-001 | ¿Los datos de las rutas los suministra la empresa de transporte o se cargan manualmente? | Equipo | Pendiente |
| OPEN-Q-002 | ¿Las notificaciones salen fuera de la app o son avisos dentro de la misma? | Equipo | Pendiente |
| OPEN-Q-003 | ¿Qué ocurre con el ETA cuando una buseta no reporta su posición? | Equipo | Pendiente |

## 16. Trazabilidad
> **Pendiente:** sin historias para trazar.

## 17. Historial de cambios
| Versión | Fecha | Cambio | Aprobación |
|---------|-------|--------|------------|
| 1.0 | 2026-09-27 | Generación automática desde alcance + historias | Pendiente (humana) |
