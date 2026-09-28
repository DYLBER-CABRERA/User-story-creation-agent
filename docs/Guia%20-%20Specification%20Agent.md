# Guía de trabajo para el Specification Agent

Guía de trabajo para el Specification Agent

Contexto, conocimientos, responsabilidades, proceso y criterios de calidad
Desarrollo de software orientado por especificaciones y agentes de IA
Propósito de esta guía
Esta guía está dirigida a ingenieros y desarrolladores que deben comprender, diseñar y posteriormente
implementar un Specification Agent dentro de un proceso de desarrollo de software apoyado por agentes
de inteligencia artificial. El objetivo no es enseñar a configurar un agente específico, sino establecer qué
debe saber el equipo, qué problema debe resolver el agente, qué información debe recibir, qué decisiones
puede tomar, qué debe preguntar, qué artefactos debe producir y en qué momento debe detenerse para
solicitar validación humana.


1. El problema que resuelve el Specification Agent
En un desarrollo tradicional es frecuente que una necesidad expresada en lenguaje natural pase
rápidamente a historias, tareas y código. Cuando intervienen agentes de IA, este salto puede amplificar
errores: una interpretación incorrecta puede propagarse desde la conversación inicial hasta la arquitectura,
el código y las pruebas.
El Specification Agent introduce una etapa explícita de ingeniería de requisitos. Su responsabilidad es
reducir la ambigüedad antes de que el trabajo técnico sea ejecutado.
Necesidad humana
  ↓
Elicitación y análisis
  ↓
Preguntas y aclaraciones
  ↓
Especificación
  ↓
Validación humana
  ↓
Arquitectura
  ↓
Plan de implementación
  ↓
Código y pruebas


La referencia formal más importante para esta etapa es ISO/IEC/IEEE 29148:2018, que establece procesos
y productos de ingeniería de requisitos y define contenidos e información asociados a dichos procesos. A
septiembre de 2026, la edición 2018 continúa vigente; ISO tiene una nueva edición DIS 29148 en desarrollo
que la reemplazará cuando sea publicada. citeturn0search2turn0search7

---

2. Qué debe saber el equipo antes de construirlo
El equipo no necesita dominar una nueva tecnología de inteligencia artificial para comprender y diseñar el
Specification Agent. Antes de construirlo debe dominar la disciplina de ingeniería de software que el agente
va a apoyar y automatizar parcialmente. La pregunta no es solamente “¿cómo hacemos que el LLM genere
una SPEC?”, sino “¿qué conocimiento debe aplicar para que esa SPEC tenga calidad de ingeniería?”.
El objetivo es que el equipo pueda distinguir qué información está decidida, qué información falta, qué
puede inferirse de forma segura y qué debe ser decidido por una persona responsable del producto o del
dominio.

2.1. Ingeniería de requisitos
El equipo debe comprender el ciclo de los requisitos: elicitación, análisis, especificación, validación,
gestión y trazabilidad.

     Necesidad

        ↓

     Elicitación

        ↓

     Análisis

        ↓

     Especificación

        ↓

     Validación

        ↓

     Gestión de cambios
Ejemplo: el usuario dice “quiero que el cliente pueda pedir domicilios”. El agente debe reconocer que la
información es insuficiente y explorar cómo se selecciona el restaurante, cómo se seleccionan productos,
cómo se define la dirección, qué medios de pago existen, cuándo se puede cancelar y qué ocurre si el
restaurante rechaza el pedido.
El resultado correcto no es que el agente complete las respuestas por su cuenta, sino que identifique las
decisiones que necesitan aclaración.

2.2. Requisitos funcionales y no funcionales
El equipo debe distinguir entre el comportamiento que el sistema debe proporcionar y las condiciones de
calidad o restricciones bajo las cuales debe hacerlo.

     Requisito funcional:

     RF-001. El sistema debe permitir al cliente agregar

     productos disponibles al carrito.



     Requisito no funcional:

     RNF-001. La consulta de restaurantes debe responder

     en un máximo de 2 segundos bajo la carga definida.
Una expresión como “la aplicación debe ser rápida” es ambigua. El Specification Agent debería detectar la
ambigüedad y preguntar qué tiempo máximo se considera aceptable, en qué operación y bajo qué
condiciones de carga. El agente no debería inventar el valor.

---

2.3. Historias de usuario y casos de uso
El equipo debe comprender cómo expresar una necesidad desde la perspectiva de un actor y cómo
describir sus interacciones con el sistema.

     Historia:

     Como cliente, quiero consultar los restaurantes

     disponibles para seleccionar dónde realizar mi pedido.



     Actor: Cliente

     Necesidad: Consultar restaurantes

     Objetivo: Elegir dónde realizar el pedido
El Specification Agent debe poder ampliar la necesidad identificando el flujo normal y sus alternativas.

     Flujo normal:

     Cliente → consulta restaurantes → sistema muestra resultados.



     Alternativa:

     Cliente → consulta restaurantes → no existen restaurantes.



     Excepción:

     Cliente → consulta restaurantes → servicio temporalmente no disponible.

2.4. Reglas de negocio
El equipo debe separar las reglas del dominio de las decisiones de implementación.

     Regla de negocio:

     Un pedido solamente puede contener productos de un restaurante.



     Decisión técnica:

     La información del pedido se almacenará en PostgreSQL.
La primera pertenece a la especificación. La segunda corresponde a arquitectura o diseño técnico.

2.5. Criterios de aceptación
Una funcionalidad debe quedar expresada mediante condiciones observables que permitan determinar si
el comportamiento es correcto.

     Requisito:

     El cliente puede cancelar un pedido.



     Preguntas:

     - ¿En qué estados?

     - ¿Hasta cuándo?

     - ¿Se devuelve el pago?

     - ¿Se notifica al restaurante?



     Criterio:

---

Dado que el pedido está pendiente de aceptación,

     cuando el cliente solicita cancelarlo,

     entonces el sistema cancela el pedido

     y notifica al cliente.
El criterio de aceptación se convierte posteriormente en una entrada importante para QA y puede
relacionarse con pruebas automatizadas.

2.6. Escenarios y casos límite
El equipo debe aprender a pensar más allá del camino exitoso.

     Camino normal:

     Cliente → productos → confirmación → pedido creado.



     Alternativa:

     Cliente → confirmación → restaurante rechaza.



     Excepción:

     Cliente → confirmación → pago rechazado.



     Caso límite:

     Dos clientes intentan comprar simultáneamente

     el último producto disponible.
Los casos límite deben identificarse para que el equipo decida cuáles requieren especificación explícita.

2.7. Trazabilidad
El equipo debe comprender cómo relacionar una necesidad con los artefactos posteriores.

     Necesidad

       ↓

     REQ-012

       ↓

     SPEC-012

       ↓

     AC-012

       ↓

     TASK-025

       ↓

     Código

       ↓

     TEST-034
Esto permitirá posteriormente que el Planning Agent transforme los elementos aprobados en trabajo
técnico y que QA determine si los criterios tienen evidencia de cumplimiento.

---

2.8. Gestión de cambios
Una SPEC no debe tratarse como un documento estático. Cuando una decisión cambia, debe existir una
nueva versión y debe evaluarse el impacto.

     SPEC-001 v1.0

     El cliente puede cancelar antes de la aceptación.



     Cambio:

     También puede cancelar durante los primeros cinco minutos

     después de la aceptación.



     SPEC-001 v1.1
El cambio puede afectar reglas, estados, interfaz, servicios, notificaciones y pruebas. El Specification Agent
debe registrar el cambio y facilitar el análisis de impacto, pero la aprobación de la nueva regla sigue siendo
humana.

2.9. BDD y Specification by Example
El equipo debe conocer estas técnicas porque permiten describir comportamiento mediante ejemplos
concretos.

     Feature: Cancelación de pedidos



     Scenario: Cancelar pedido pendiente



     Given el cliente tiene un pedido pendiente

     When solicita la cancelación

     Then el pedido cambia a "Cancelado"

     And el cliente recibe confirmación
El Specification Agent puede utilizar estructuras de este tipo para hacer explícito el comportamiento
esperado. Posteriormente, QA puede utilizarlas como base para pruebas.

2.10. Arquitectura y patrones de diseño
El equipo debe conocer arquitectura y patrones, pero no para que el Specification Agent diseñe la solución.
El objetivo es reconocer el límite entre especificación y diseño técnico.

     Necesidad:

     Calcular el costo del domicilio según la distancia.



     Specification Agent:

     El sistema debe calcular el costo en función de la distancia.



     Architecture Agent:

     Determina cómo implementar esa regla, por ejemplo mediante

     un componente o una estrategia de cálculo.
El Specification Agent no debería decidir que se utilizará Strategy Pattern, PostgreSQL, una API de mapas o
microservicios. Esas decisiones pertenecen a arquitectura.

---

El conocimiento de arquitectura permite al equipo delimitar correctamente qué información debe
permanecer en la SPEC y qué información corresponde al Architecture Agent.

2.11. Prueba práctica antes de construir el agente
Antes de programar el agente, el equipo debería poder tomar una solicitud como “construir una aplicación
de domicilios” y producir manualmente una pequeña SPEC.

     Solicitud

        ↓

     Actores

        ↓

     Preguntas

        ↓

     Requisitos

        ↓

     Reglas

        ↓

     Escenarios

        ↓

     Criterios de aceptación

        ↓

     Casos límite

        ↓

     Preguntas abiertas

        ↓

     SPEC aprobable
Si el equipo no puede realizar este proceso manualmente, todavía no está suficientemente definido qué
comportamiento se espera del agente. Primero debe definirse el método de trabajo; después se
automatiza.


3. Responsabilidad exacta del agente
La pregunta central del Specification Agent es:
¿Qué debe hacer el sistema y bajo qué condiciones debe considerarse correcto?
Para responderla, el agente debe:
• comprender el objetivo y contexto del producto;
• identificar actores y partes interesadas relevantes;
• extraer y estructurar requisitos;
• identificar reglas de negocio;
• detectar información contradictoria, ambigua o incompleta;
• formular preguntas de aclaración;
• proponer escenarios y flujos alternativos;
• definir criterios de aceptación verificables;

---

• identificar casos límite relevantes;
• documentar restricciones, dependencias y elementos fuera de alcance;
• mantener la trazabilidad de las decisiones;
• generar y versionar una SPEC lista para revisión humana.


4. Lo que NO debe hacer
El límite del agente es tan importante como sus capacidades. El Specification Agent no debe convertir
automáticamente una necesidad en decisiones técnicas.
• No debe diseñar la base de datos.
• No debe seleccionar PostgreSQL, MongoDB, React, FastAPI u otra tecnología.
• No debe decidir entre monolito, microservicios, arquitectura hexagonal u otra arquitectura.
• No debe crear clases, endpoints o componentes técnicos.
• No debe escribir código de producción.
• No debe transformar automáticamente la SPEC en un backlog técnico definitivo.
• No debe inventar reglas de negocio para cerrar una especificación aparentemente completa.
Estas actividades corresponden a etapas posteriores. Una separación clara facilita que los agentes tengan
responsabilidades acotadas y que cada resultado pueda ser revisado antes de continuar.


5. Proceso operativo recomendado
El agente debería trabajar como un proceso iterativo, no como una sola llamada al modelo.
1. Recibir contexto
2. Identificar objetivo y alcance inicial
3. Identificar actores
4. Extraer requisitos conocidos
5. Detectar ambigüedades y contradicciones
6. Formular preguntas
7. Recibir respuestas humanas
8. Construir escenarios y reglas
9. Definir criterios de aceptación
10. Revisar completitud y consistencia
11. Generar SPEC
12. Solicitar aprobación humana
13. Congelar versión aprobada


Si existen preguntas críticas sin respuesta, el agente debe detener el cierre de la SPEC. El comportamiento
correcto no es adivinar: es hacer explícita la incertidumbre.

---

6. Ejemplo: aplicación de domicilios
Supongamos que el usuario proporciona únicamente la siguiente solicitud:
“Necesitamos una aplicación para pedir domicilios de restaurantes.”
Esta frase no es todavía una especificación. El agente debe explorar el dominio.
Actores potenciales:
• Cliente
• Restaurante
• Domiciliario
• Administrador
Preguntas que el agente debería plantear:
• ¿Un pedido puede contener productos de diferentes restaurantes?
• ¿Cuándo puede cancelar el cliente?
• ¿Quién asigna el domiciliario?
• ¿Qué ocurre si el restaurante rechaza el pedido?
• ¿Qué medios de pago se soportan?
• ¿Cómo se calcula el costo del domicilio?
• ¿Qué ocurre cuando no hay domiciliarios disponibles?
Después de recibir las respuestas, el agente puede estructurar reglas como:
BR-001: Un pedido solo puede contener productos de un restaurante.
BR-002: El restaurante debe aceptar el pedido antes de iniciar la entrega.
BR-003: El cliente puede pagar mediante tarjeta o contraentrega.
BR-004: Un pedido cancelado no puede continuar al proceso de entrega.


Luego puede construir un escenario verificable:
Feature: Realizar pedido


Scenario: Crear un pedido correctamente
Given el cliente está autenticado
And el carrito contiene productos disponibles
And todos pertenecen al mismo restaurante
When el cliente confirma el pedido
Then el sistema registra el pedido
And el pedido queda en estado "Pendiente de aceptación"


Given-When-Then permite expresar precondiciones, comportamiento y resultados esperados. Martin
Fowler describe este enfoque como una forma de representar pruebas o especificaciones de

---

comportamiento, y Cucumber documenta Gherkin como un lenguaje estructurado para especificaciones
ejecutables. citeturn0search0turn0search1


7. Estructura de la SPEC
Una estructura inicial, adaptable al proyecto, puede ser:
SPEC-001
Nombre de la funcionalidad
Versión
Estado


1. Objetivo
2. Contexto
3. Alcance
4. Actores
5. Requisitos funcionales
6. Requisitos no funcionales
7. Reglas de negocio
8. Flujos principales
9. Flujos alternativos
10. Casos límite
11. Criterios de aceptación
12. Dependencias
13. Restricciones
14. Fuera de alcance
15. Preguntas abiertas
16. Trazabilidad
17. Historial de cambios



8. Requisitos bien formados y verificables
El equipo debe aprender a detectar requisitos débiles. Por ejemplo:
Débil:
"El sistema debe ser rápido."


Mejor:
"El sistema deberá responder la consulta de disponibilidad
en un máximo de X segundos bajo las condiciones definidas."

---

La cifra X no debe ser inventada por el agente. Si el negocio o la arquitectura aún no la han definido, debe
aparecer como una decisión pendiente. ISO/IEC/IEEE 29148 aborda características y atributos de requisitos
y la información producida durante la ingeniería de requisitos. citeturn0search12


9. Criterios de aceptación y ejemplos
Cada funcionalidad relevante debe poder verificarse. Un criterio de aceptación debe describir una
condición observable y un resultado esperado.
AC-001
Dado un carrito válido,
cuando el cliente confirma el pedido,
entonces el sistema debe registrar el pedido
en estado "Pendiente de aceptación".


AC-002
Dado un restaurante cerrado,
cuando el cliente intenta confirmar el pedido,
entonces el sistema debe impedir la confirmación
e informar la causa.


Specification by Example utiliza ejemplos concretos para aclarar el comportamiento esperado. El material
de Martin Fowler es una referencia conceptual útil para profundizar. citeturn0search4


10. Estados, reglas y excepciones
El Specification Agent debe identificar comportamientos que dependan de estados. Para un pedido, por
ejemplo, podría existir una secuencia como:
CREADO
 ↓
PENDIENTE DE ACEPTACIÓN
 ↓
ACEPTADO
 ↓
DOMICILIARIO ASIGNADO
 ↓
EN PREPARACIÓN
 ↓
LISTO PARA RECOGER
 ↓

---

EN CAMINO
 ↓
ENTREGADO


La especificación debe determinar qué actor puede provocar cada transición y qué condiciones deben
cumplirse. También debe documentar estados terminales como RECHAZADO o CANCELADO cuando
correspondan.


11. Preguntas abiertas y control de incertidumbre
Una buena SPEC no es necesariamente la que contiene más texto. Es la que hace explícito qué está
decidido y qué no.
OPEN-Q-001
¿Cuánto tiempo antes puede cancelarse un pedido?


Estado: Pendiente
Responsable: Producto


OPEN-Q-002
¿El costo del domicilio depende de distancia?


Estado: Pendiente
Responsable: Negocio


El agente debe diferenciar entre información confirmada, inferencias, propuestas y decisiones aprobadas.
Una inferencia del modelo nunca debe convertirse silenciosamente en una regla de negocio.


12. Punto de control humano
SPEC v0.x
 ↓
Preguntas pendientes
 ↓
Humano responde
 ↓
SPEC v1.0
 ↓
Revisión humana
 ↓
APROBADA

---

↓
SPEC FROZEN
 ↓
Architecture Agent


El humano debe aprobar especialmente objetivos, alcance, reglas de negocio, criterios críticos,
restricciones y decisiones que tengan impacto contractual, económico, legal, de seguridad o de
experiencia de usuario.


13. Trazabilidad
La especificación debe permitir recorrer el camino desde la necesidad hasta la verificación.
Necesidad
 ↓
REQ-001
 ↓
SPEC-001
 ↓
BR-003 / AC-004
 ↓
Implementación
 ↓
TEST-004
 ↓
Resultado


Esta trazabilidad será posteriormente muy útil para el Planning Agent y el QA Agent. El Planning Agent podrá
transformar los elementos aprobados de la SPEC en trabajo técnico, mientras QA podrá verificar que los
criterios definidos tengan evidencia de cumplimiento.


14. Relación con los demás agentes
     HUMANO
      ↓
    Specification Agent
      ↓
      SPEC
      ↓
    Architecture Agent
      ↓

---

ARQUITECTURA
      ↓
    Planning Agent
      ↓
    IMPLEMENTATION PLAN
      ↓
     Coding Agent
      ↓
     CÓDIGO
      ↓
    QA Agent
      ↓
     VERIFICACIÓN


La frontera conceptual es: Specification Agent = qué debe hacer el sistema; Architecture Agent = cómo se
estructurará técnicamente; Planning Agent = qué trabajo debe realizarse; Coding Agent = implementación;
QA Agent = verificación.


15. Qué debe aprender el equipo
Ruta recomendada de aprendizaje:
• Ingeniería de requisitos y características de buenos requisitos.
• Elicitación y análisis de requisitos.
• Historias de usuario y casos de uso.
• Reglas de negocio.
• Requisitos no funcionales y atributos de calidad.
• Criterios de aceptación.
• Specification by Example.
• BDD y Given-When-Then.
• Modelado de estados y escenarios alternativos.
• Trazabilidad y gestión de cambios.
• Versionamiento de especificaciones.
• Principios de Spec-Driven Development.
• Context engineering para agentes.
• Diseño de prompts y contratos de salida estructurados.
• Evaluación de agentes: precisión, consistencia, completitud y tasa de preguntas necesarias.

---

16. Qué debe aprender el agente
El conocimiento del agente debería organizarse en capas:
Capa 1: Dominio
- contexto del negocio
- glosario
- actores
- reglas


Capa 2: Ingeniería de requisitos
- requisitos
- escenarios
- criterios de aceptación
- restricciones


Capa 3: Convenciones del proyecto
- plantilla de SPEC
- nomenclatura
- versionamiento
- trazabilidad


Capa 4: Contexto del producto
- documentos existentes
- decisiones aprobadas
- alcance
- cambios anteriores


El agente no debería recibir indiscriminadamente todo el repositorio y todos los documentos. El contexto
debe ser pertinente a la especificación que está construyendo.


17. Cómo evaluar si el Specification Agent funciona bien
No basta con preguntar si la SPEC “se ve bien”. Deben establecerse criterios de evaluación.
• Completitud: ¿faltan requisitos o escenarios importantes?
• Consistencia: ¿existen contradicciones entre reglas?
• No ambigüedad: ¿hay términos que admiten interpretaciones incompatibles?
• Verificabilidad: ¿los criterios de aceptación pueden probarse?
• Trazabilidad: ¿cada requisito relevante puede seguirse hasta su criterio de aceptación?
• No invención: ¿el agente distingue hechos, decisiones y preguntas abiertas?

---

• Delimitación: ¿evita introducir decisiones propias de arquitectura o implementación?
• Utilidad: ¿el Architecture Agent y el Planning Agent pueden utilizar la SPEC sin reinterpretar el problema?


18. Primer ejercicio recomendado
Antes de programar el agente, el equipo debería realizar manualmente el proceso sobre una funcionalidad
pequeña de la aplicación de domicilios.
Funcionalidad:
Realizar pedido


Entrada:
Una solicitud informal del negocio.


Trabajo:
1. Identificar actores.
2. Formular preguntas.
3. Definir requisitos.
4. Definir reglas.
5. Definir escenarios.
6. Definir criterios de aceptación.
7. Identificar casos límite.
8. Registrar preguntas pendientes.
9. Construir SPEC v1.0.
10. Revisarla con un responsable humano.


Este ejercicio permite definir qué comportamiento se espera del agente antes de automatizarlo. Una buena
práctica es construir primero un conjunto pequeño de ejemplos de entrada y una salida esperada; ese
conjunto puede convertirse posteriormente en un mecanismo de evaluación del agente.


19. Recursos para profundizar
• ISO/IEC/IEEE 29148:2018 – Requirements engineering — referencia internacional vigente en 2026 para
ingeniería de requisitos
• ISO/IEC/IEEE DIS 29148 – nueva edición en desarrollo — borrador de la tercera edición, todavía no es la
norma publicada
• ISO Online Browsing Platform – 29148:2018 — consulta del contenido disponible del estándar
• Cucumber – Gherkin Reference — referencia oficial del lenguaje Gherkin
• Cucumber – documentación — documentación oficial y guías
• Cucumber – 10 Minute Tutorial — tutorial práctico para comprender el flujo de especificaciones
ejecutables

---

• Martin Fowler – Specification by Example — introducción conceptual a Specification by Example
• Martin Fowler – Given When Then — explicación del patrón Given-When-Then
• Martin Fowler – The Practical Test Pyramid — referencia para comprender la relación entre tipos de
pruebas y estrategia de validación


20. Resultado esperado del trabajo
El equipo debe finalizar esta etapa entendiendo que el Specification Agent no es un generador automático
de documentos. Es un componente de ingeniería cuyo propósito es convertir intención humana en una
especificación explícita, verificable y aprobable.
El agente debe saber cuándo continuar, cuándo preguntar y cuándo detenerse. Su calidad se mide menos
por la cantidad de texto que genera y más por su capacidad para eliminar ambigüedades, preservar
decisiones humanas, detectar información faltante y producir una SPEC que pueda ser utilizada
directamente por los agentes de arquitectura, planificación y verificación.
La primera implementación recomendada no debería intentar resolver todo el ciclo de desarrollo. Debe
concentrarse en una unidad pequeña: recibir una necesidad, construir preguntas, producir una SPEC
estructurada, registrar incertidumbres y solicitar aprobación humana. Una vez que este ciclo sea confiable,
se puede conectar progresivamente con Architecture Agent, Planning Agent y QA Agent.
