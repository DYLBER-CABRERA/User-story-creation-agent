# SPEC-010 — Uso sin cuenta

| Campo | Valor |
|-------|-------|
| Versión | 0.1 |
| Estado | Borrador v0.1 — pendiente de aprobación humana |
| Funcionalidad | Uso sin cuenta |
| Actores | Pasajero |
| Generado | 2026-09-29 (automático) |

> Fuente: `docs/alcance-contexto-proyecto.md` + historias de usuario generadas.
> Estructura según la sección 7 de la guía del Specification Agent.

## 1. Objetivo
Permitir consultar la app sin obligar a crear una cuenta.

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
- cualquier persona puede consultar sin registrarse.

Ver también **Fuera de alcance** (§14 de esta SPEC).

## 4. Actores
- **Pasajero**

## 5. Requisitos funcionales
> **Pendiente:** sin historias asignadas en la corrida actual. Genere historias (app o CLI) y vuelva a exportar.

## 6. Requisitos no funcionales
> Valores medibles definidos en `docs/alcance-contexto-proyecto.md` §14 (guía §8: las cifras las define el equipo; el agente no inventa).

| ID | Categoría | Requisito verificable | Valor |
|----|-----------|----------------------|-------|
| RNF-01 | Rendimiento | Las consultas principales (rutas, horarios, búsqueda) responden en un máximo de X segundos con N usuarios concurrentes | **[por definir]** |
| RNF-02 | Rendimiento | La posición GPS y el ETA se actualizan como máximo cada X segundos durante el recorrido | **[por definir]** |
| RNF-03 | Disponibilidad | El servicio está disponible al menos el X% del tiempo (ventana mensual) | **[por definir]** |
| RNF-04 | Seguridad | Los datos viajan cifrados (HTTPS/TLS 1.2+) y no se registran credenciales ni datos personales en logs | Definido |
| RNF-05 | Integridad | Las actualizaciones concurrentes del mismo recurso no pierden datos (control de versiones o bloqueo) | Definido |
| RNF-06 | Compatibilidad | La interfaz funciona en navegadores móviles y escritorio modernos, desde pantallas de 320 px | Definido |

Valores **[por definir]** → decisión abierta **SUG-RNF** (§15): RNF-01, RNF-02, RNF-03.

## 7. Reglas de negocio
- **BR-01:** Cualquier persona puede consultar rutas, horarios y mapa sin crear una cuenta.
- **BR-02:** Guardar favoritas y recibir notificaciones requiere un usuario registrado en la app.

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

**Estado de cada pregunta (control humano):**

- **OPEN-Q-001** — **Respondida** (Web, 2026-09-29): los subministra la empresa
- **OPEN-Q-002** — **Respondida** (Web, 2026-09-29): avisos dentro de la misma
- **OPEN-Q-003** — **Respondida** (Web, 2026-09-29): le reporta al usuario que perdio la ubicacion y le dice este pendiente de la siguiente buseta con la misma ruta

**Preguntas sugeridas por el agente (§5 pasos 5-6):**

- **SUG-RNF** — **Pendiente** (sugerida por el agente): Valores medibles de RNF sin definir en §14 del alcance (guía §8: el agente NO debe inventar cifras): RNF-01, RNF-02, RNF-03. ¿Cuál es el valor de cada uno (segundos, % de disponibilidad, etc.)?
- **SUG-010-CASOS** — **Pendiente** (sugerida por el agente): Casos límite sin analizar (§10) para Uso sin cuenta. ¿Qué casos deben especificarse (concurrencia, valores extremos, datos faltantes)?
- **SUG-010-DEP** — **Pendiente** (sugerida por el agente): Dependencias pendientes (§12) para Uso sin cuenta. ¿Hay dependencias externas (datos, APIs, permisos)? Responder 'ninguna' si no aplica.

## 16. Trazabilidad
> **Pendiente:** sin historias para trazar.

## 17. Historial de cambios
| Versión | Fecha | Cambio | Aprobación |
|---------|-------|--------|------------|
| 0.1 | 2026-09-29 | Generación automática desde alcance + historias | Pendiente (humana) |
