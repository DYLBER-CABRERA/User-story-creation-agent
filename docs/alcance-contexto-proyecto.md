# BusetasApp Manizales — Alcance y contexto del proyecto

> **Nota:** este documento define únicamente el **alcance funcional** del proyecto.
> Las decisiones tecnológicas (plataforma, APIs, base de datos, arquitectura) **no se
> definen aquí**: corresponden a una etapa posterior. Primero se construyen las
> historias de usuario; después se decide cómo se implementan.

## 1. Descripción del problema

El público en general desconoce las rutas, los horarios y los tiempos de llegada de
las busetas en Manizales. No existe una forma sencilla de saber qué buseta pasa por
dónde, a qué hora pasa, ni cuánto falta para que llegue a una parada.

## 2. Descripción de la solución

**BusetasApp** es una aplicación para consultar las rutas de las busetas de Manizales.
Permite:

* ver las rutas y sus paradas en un mapa,
* consultar horarios y días de operación,
* ver la ubicación de las busetas en tiempo real y el tiempo estimado de llegada (ETA),
* planificar un viaje indicando origen y destino,
* buscar rutas por número, nombre, barrio o punto de interés.

Además, incluye un módulo para administradores (gestionar la operación) y un módulo
para conductores (reportar la posición de la buseta durante el recorrido).

## 3. Objetivos

### Objetivo general

Facilitar la movilidad de los pasajeros de buseta en Manizales.

### Objetivos específicos

* Dar a conocer las rutas de las busetas.
* Informar los horarios de funcionamiento y días hábiles de las busetas.
* Permitir ver la ubicación de las busetas en tiempo real y el tiempo estimado de
  llegada (ETA).
* Ayudar a planificar un viaje indicando origen y destino.

## 4. Público objetivo

* Estudiantes y trabajadores que se desplazan en buseta a diario.
* Visitantes o personas que no conocen las rutas de la ciudad.
* Personal encargado de administrar la información de las rutas.

## 5. Alcances del proyecto

* **Consulta de rutas:** catálogo de las rutas de buseta de Manizales, con recorrido
  dibujado en mapa, puntos de parada y sentido del trayecto.
* **Consulta de horarios:** hora de inicio y fin de operación de cada ruta,
  frecuencia aproximada y días de servicio (lunes a viernes, sábados, domingos y
  festivos).
* **Seguimiento en tiempo real:** ubicación de las busetas activas en el mapa y
  tiempo estimado de llegada (ETA) a una parada.
* **Planificación de viaje:** el usuario indica origen y destino y la app le sugiere
  qué ruta o rutas tomar.
* **Búsqueda y filtros:** por número o nombre de ruta, barrio, sector o punto de
  interés (universidades, hospitales, terminal, etc.).
* **Módulo administrativo:** crear y actualizar rutas, horarios, paradas y busetas.
* **Módulo de conductores:** reportar la posición de la buseta durante el recorrido.
* **Favoritas:** guardar rutas o paradas frecuentes para encontrarlas rápido.
* **Notificaciones:** avisar al pasajero cuando la buseta esté por llegar a una
  parada que le interesa.
* **Uso sin cuenta:** cualquier persona puede consultar sin registrarse.
* **Avisos generales:** el administrador publica cambios, suspensiones o festivos.
* **Estadísticas básicas:** al administrador, sobre el uso de la app.

## 6. Fuera de alcance

* Pago de pasajes, tarjetas de recarga y cualquier manejo de dinero.
* Transporte fuera de Manizales: taxis, transporte informal y rutas intermunicipales.
* Definiciones tecnológicas: plataforma (web, móvil), APIs, base de datos y
  arquitectura — se deciden en una etapa posterior a las historias de usuario.

## 7. Reglas de negocio

* **BR-01:** Cualquier persona puede consultar rutas, horarios y mapa sin crear una
  cuenta.
* **BR-02:** Guardar favoritas y recibir notificaciones requiere un usuario
  registrado en la app.
* **BR-03:** Solo el administrador crea, edita o elimina rutas, horarios, paradas y
  busetas.
* **BR-04:** Solo el administrador publica avisos generales.
* **BR-05:** Solo el conductor reporta la posición de la buseta que está conduciendo,
  y únicamente durante su recorrido.

## 8. Priorización

| Prioridad | Funcionalidades |
|-----------|-----------------|
| **Imprescindible** (entrega mínima) | Consulta de rutas, horarios, seguimiento en tiempo real con ETA, planificación de viaje, búsqueda y filtros, módulo administrativo, módulo de conductores |
| **Deseable** | Favoritas, avisos generales, estadísticas básicas |
| **Opcional** | Notificaciones, ampliación a Villamaría |

## 9. Roles de la aplicación

* **Pasajero:** consulta rutas, horarios y ubicación; planifica viajes; busca
  rutas; guarda favoritas y recibe avisos.
* **Conductor:** consulta su ruta asignada, inicia y finaliza el recorrido, y
  reporta la posición de la buseta.
* **Administrador:** gestiona rutas, horarios, paradas y busetas; publica avisos;
  consulta estadísticas básicas.

## 10. Preguntas abiertas

| ID | Pregunta | Responsable | Estado |
|-----|----------|-------------|--------|
| OPEN-Q-001 | ¿Los datos de las rutas los suministra la empresa de transporte o se cargan manualmente? | Equipo | Pendiente |
| OPEN-Q-002 | ¿Las notificaciones salen fuera de la app o son avisos dentro de la misma? | Equipo | Pendiente |
| OPEN-Q-003 | ¿Qué ocurre con el ETA cuando una buseta no reporta su posición? | Equipo | Pendiente |

## 11. Entregables y criterios de éxito

* Aplicación funcional con todas las funcionalidades **Imprescindibles** demostrables.
* Historias de usuario bien construidas (formato estándar, INVEST) para los tres
  roles.

## 12. Equipo y plazo

Proyecto académico. 4 integrantes: Dylber Cabrera, Miguel Rojas, Leidy Nieto,
Sophia Cardona. Plazo: 8 semanas desde cero.

---

## 13. Contexto para el generador de historias

> Párrafo listo para pegar en el campo **"Contexto del proyecto"** de la app.

```
BusetasApp es una aplicación para consultar las rutas de las busetas de Manizales:
catálogo de rutas con recorrido en mapa y paradas, horarios y días de operación
(lunes a viernes, sábados, domingos y festivos), ubicación de las busetas en tiempo
real con tiempo estimado de llegada (ETA) a una parada, planificación de viaje con
origen y destino, y búsqueda por número o nombre de ruta, barrio o punto de interés.
Incluye un módulo administrativo (crear y actualizar rutas, horarios, paradas y
busetas, publicar avisos generales y ver estadísticas básicas) y un módulo de
conductores (reportar la posición de la buseta durante el recorrido). El pasajero
puede consultar sin cuenta; guardar favoritas y recibir notificaciones requiere
usuario registrado. Fuera de alcance: pagos, tarjetas de recarga y transporte fuera
de Manizales. Roles: pasajero, conductor, administrador.
```
