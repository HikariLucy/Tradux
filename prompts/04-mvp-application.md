# Prompt 04 — Aplicación MVP y flujo real subir → traducir → descargar

Usa este prompt desde la raíz del repositorio en una rama nueva basada en `main`.

---

Estamos desarrollando **Tradux**, una aplicación web para traducir documentos preservando al máximo su maquetación original.

Las Fases 0, 1, 2, 2.5 y 3 ya están completadas. Tradux dispone actualmente de:

- aplicación FastAPI reproducible;
- `DocumentAnalyzer` para PDFs digitales;
- `Document` / `Page` / `TextBlock` tipados e independientes de PyMuPDF;
- geometría canónica no rotada documentada;
- `TranslationEngine` desacoplado;
- `MockTranslator` determinista;
- adaptador OpenAI-compatible configurable por entorno;
- protección de términos, números, códigos, URLs y placeholders;
- `LayoutEngine` con estados `FIT`, `SHRUNK`, `EXPANDED`, `REVIEW_REQUIRED`, `SKIPPED`;
- `PyMuPDFRenderer` separado del layout;
- reconstrucción de PDF preservando páginas, rotaciones, imágenes y gráficos;
- Web Workbench específico de Tradux para análisis, vista previa mock y descarga de reconstrucción;
- benchmark local MICRON de 90 páginas validado manualmente y nunca versionado.

Antes de modificar nada, lee completos:

- `README.md`
- `docs/architecture.md`
- `docs/roadmap.md`
- `docs/decisions/0001-initial-stack.md`
- `docs/decisions/0002-document-model-and-analyzer.md`
- `docs/decisions/0003-translation-engine-and-provider-abstraction.md`
- `docs/decisions/0004-layout-engine-and-pdf-reconstruction.md`
- `prompts/00-bootstrap.md`
- `prompts/01-document-analyzer.md`
- `prompts/02-translation-engine.md`
- `prompts/02-5-web-workbench.md`
- `prompts/03-layout-and-reconstruction.md`

## Objetivo de esta tarea

Implementar la **Fase 4 — Aplicación MVP**.

El criterio de salida es que una persona pueda utilizar Tradux desde la interfaz web para completar un flujo real:

```text
subir PDF digital
    ↓
analizar
    ↓
seleccionar idioma origen/destino y términos protegidos
    ↓
crear trabajo de traducción
    ↓
ver estado/progreso por etapas
    ↓
traducir mediante modo demo o proveedor real configurado
    ↓
calcular layout
    ↓
reconstruir PDF
    ↓
descargar resultado
```

No debe ser necesario ejecutar scripts ni comandos manuales para completar ese flujo desde el navegador.

La Fase 4 **no es aún la arquitectura de producción**. Debe ser un MVP claro, seguro y usable, sin introducir prematuramente PostgreSQL, Redis, workers externos, autenticación, pagos o almacenamiento permanente.

---

# 1. Principios obligatorios

1. Mantener la separación existente entre `DocumentAnalyzer`, `TranslationEngine`, `LayoutEngine` y `PDFRenderer`.
2. No convertir endpoints web en funciones gigantes que reimplementen lógica del dominio.
3. No exponer claves API, `base_url`, secretos ni configuración sensible al navegador.
4. Tests 100% offline. Ningún test puede realizar llamadas reales a un proveedor externo.
5. El modo demo con `MockTranslator` debe seguir disponible y ser inequívocamente identificado como demostración.
6. El modo de traducción real debe requerir una configuración válida del servidor y una acción explícita del usuario.
7. No ejecutar traducción real accidentalmente al analizar, previsualizar o abrir una página.
8. No registrar texto documental completo, JSON completo, claves ni respuestas crudas de proveedor en logs/excepciones.
9. No persistir PDFs ni traducciones en disco de forma permanente en esta fase.
10. El PDF fuente debe permanecer inmutable.
11. Mantener límites explícitos de tamaño y lectura acotada de uploads.
12. La interfaz debe seguir sintiéndose como una **herramienta documental Tradux**, no como un dashboard SaaS genérico.

---

# 2. Diseño del trabajo MVP

Implementa un concepto tipado de trabajo de traducción bajo una capa apropiada, por ejemplo `app/jobs/` o `app/services/`.

Debe existir un estado explícito, por ejemplo:

- `created`;
- `analyzing`;
- `translating`;
- `layout`;
- `rendering`;
- `completed`;
- `failed`;
- opcionalmente `cancelled` solo si puede implementarse correctamente sin complejidad artificial.

No uses strings dispersos.

Un trabajo debe exponer solo metadata segura, por ejemplo:

- `job_id` UUID;
- estado actual;
- etapa actual;
- `created_at` / `updated_at`;
- nombre de archivo sanitizado;
- idioma origen solicitado;
- idioma destino;
- modo `demo` o `configured`;
- proveedor lógico seguro si aplica (sin endpoint ni key);
- páginas;
- bloques totales / traducidos si están disponibles;
- métricas finales de layout (`fit`, `shrunk`, `expanded`, `review_required`);
- indicador `result_available`;
- código/mensaje de error sanitizado.

No incluyas texto completo del documento dentro del objeto de estado público.

---

# 3. Almacenamiento efímero en memoria

Para esta fase usa un **store en memoria del proceso**, claramente documentado como temporal y no durable.

Requisitos mínimos:

- jobs indexados por UUID;
- PDF fuente y resultado solo en memoria mientras el job sea necesario;
- límite de cantidad de trabajos o memoria razonable para evitar crecimiento ilimitado;
- TTL configurable o expiración simple;
- limpieza perezosa al crear/consultar jobs es suficiente;
- reiniciar FastAPI puede perder los trabajos: debe documentarse como limitación de Fase 4;
- no introducir PostgreSQL ni Redis todavía.

No escribas PDFs temporales permanentes al filesystem salvo que una API concreta lo requiera inevitablemente; si se usa un temporal, debe eliminarse de forma garantizada y estar cubierto por tests.

---

# 4. Ejecución del trabajo

Implementa un orquestador pequeño y explícito, por ejemplo `TranslationJobService` / `DocumentTranslationWorkflow`.

Debe reutilizar directamente los servicios existentes:

```text
DocumentAnalyzer
    ↓
TranslationEngine
    ↓
LayoutEngine
    ↓
PyMuPDFRenderer
```

No llames endpoints HTTP internos desde el backend para encadenar estas etapas.

## Ejecución en proceso

Para el MVP se permite ejecutar el trabajo mediante una tarea asíncrona **dentro del mismo proceso FastAPI** si esto permite que el navegador consulte estado mientras continúa el procesamiento.

Esto NO debe presentarse como arquitectura de producción.

- sin Celery;
- sin RQ;
- sin Redis;
- sin broker;
- sin workers externos;
- sin sistema distribuido.

Si usas `asyncio.create_task()` o equivalente, encapsula la creación/seguimiento de la tarea y maneja excepciones para que ningún job quede indefinidamente en un estado intermedio.

El layout/render síncrono puede moverse a `asyncio.to_thread()` si es necesario para no bloquear innecesariamente el event loop, pero no introduzcas abstracciones complejas sin necesidad.

---

# 5. Modos de traducción

Tradux debe distinguir claramente dos modos.

## A. `demo`

- usa `MockTranslator` de forma explícita;
- cero red;
- cero coste;
- siempre disponible;
- la UI debe indicar que no es traducción lingüística real.

## B. `configured`

- usa el proveedor configurado del servidor mediante la factory existente (`get_translator()` o equivalente actual);
- no acepta API key desde el cliente;
- no acepta `base_url` arbitrario desde el cliente;
- no permite que el navegador seleccione un proveedor no habilitado por el servidor;
- si falta la configuración requerida, el job no debe comenzar y debe devolverse un error 4xx estable y claro;
- las pruebas deben usar mocks / transportes HTTP falsos, nunca red real.

### Protección contra coste accidental

La UI debe requerir una acción explícita diferente para ejecutar modo real.

Antes de lanzar un trabajo real, debe mostrar al menos:

- páginas detectadas;
- cantidad de bloques de texto;
- idioma destino;
- aviso de que el proveedor configurado puede generar consumo/coste.

No inventes una estimación monetaria si no existe un cálculo real.

Para documentos grandes, muestra una advertencia reforzada basada en cantidad de páginas/bloques. No impidas arbitrariamente el proceso salvo que exista un límite configurable documentado.

No ejecutes el manual MICRON completo con proveedor real durante desarrollo o tests.

---

# 6. Idiomas y detección

La UI debe permitir:

- idioma origen `Auto (detectar)`;
- selección manual de origen;
- idioma destino obligatorio;
- términos protegidos.

Mantén los códigos de idioma como valores normalizados (`es`, `en`, `fr`, etc.) y etiquetas de presentación separadas.

No dupliques la lógica de traducción/detección del `TranslationEngine` en JavaScript.

Si el proveedor actual detecta idioma únicamente durante la traducción, no inventes un detector independiente solo para esta fase. La interfaz puede mostrar `Auto` hasta que el motor resuelva el idioma.

---

# 7. API MVP

Diseña endpoints claros bajo `/api/v1/jobs` (o una ruta equivalente bien justificada).

Contrato recomendado:

## `POST /api/v1/jobs`

Crea un trabajo.

Entrada multipart mínima:

- `file`: PDF digital;
- `source_language`: opcional / auto;
- `target_language`: obligatorio;
- `mode`: `demo | configured`;
- términos protegidos en una representación pequeña y validable.

Puede analizar el PDF dentro del workflow. No confíes en que un `DocumentModel` enviado por el navegador sea necesariamente auténtico si no es necesario para el contrato.

Respuesta sugerida:

- `202 Accepted`;
- `job_id`;
- `status`;
- URLs lógicas o campos suficientes para consultar estado y resultado.

## `GET /api/v1/jobs/{job_id}`

Devuelve estado/metadata segura.

- `404` si no existe o expiró;
- nunca devuelve PDF ni texto completo;
- si falló, expone mensaje/código sanitizado.

## `GET /api/v1/jobs/{job_id}/result`

- `200 application/pdf` si está completado;
- `409` si todavía no está listo;
- `404` si job no existe/expiró;
- `Content-Disposition` con nombre seguro.

## `DELETE /api/v1/jobs/{job_id}`

Recomendado si resulta simple: elimina el job y libera explícitamente bytes fuente/resultado.

No agregues endpoints de historial persistente.

---

# 8. Validación de uploads y errores

Reutiliza o extrae helpers de lectura acotada si existe lógica duplicada entre analyzer/workbench/jobs.

Requisitos:

- PDF ausente → 400/422 controlado;
- PDF vacío → 400;
- tamaño excedido → 413;
- PDF inválido → 4xx controlado, no 500;
- target language inválido/vacío → 422;
- mode inválido → 422;
- provider real no configurado → 409/422/503 documentado y estable;
- job inexistente → 404;
- resultado aún no listo → 409;
- error interno → 500 sanitizado;
- ninguna respuesta/log debe contener contenido documental completo ni secretos.

No devuelvas `str(e)` de excepciones que puedan contener input documental o respuestas del proveedor.

---

# 9. Estado y progreso

No inventes porcentajes de progreso extremadamente precisos si el motor no puede medirlos.

La UI debe mostrar progreso **por etapas reales**:

```text
Analizando documento
Traduciendo bloques
Calculando layout
Reconstruyendo PDF
Completado
```

Si resulta limpio exponer `translated_blocks / total_blocks`, hazlo. Si requeriría una refactorización riesgosa del `TranslationEngine`, difiérelo y muestra solo etapa + spinner.

Un job que falla debe quedar en `failed`, no quedar eternamente en `translating` o `rendering`.

---

# 10. Interfaz de usuario

Evoluciona el Web Workbench actual en lugar de reemplazarlo por una plantilla genérica.

Mantén la identidad actual:

- visor PDF central como objeto protagonista;
- estructura/métricas a la izquierda;
- configuración y pipeline a la derecha;
- inspección de bloques cuando aporte valor;
- estilo editorial/documental de Tradux.

## Cambios de UX requeridos

### Antes de crear el trabajo

Mostrar:

- archivo elegido;
- análisis real;
- páginas / bloques / imágenes;
- idioma origen;
- idioma destino;
- términos protegidos;
- selector claro:
  - `Demostración`;
  - `Traducción real` solo si servidor la ofrece.

### Confirmación para modo real

Debe existir un paso/confirmación visible antes de iniciar llamadas al proveedor configurado, especialmente para documentos grandes.

No usar un simple toggle que pueda activarse accidentalmente y ejecutar inmediatamente.

### Durante el trabajo

Mostrar estado por etapas sin bloquear toda la interfaz innecesariamente.

El navegador debe consultar el job hasta `completed` o `failed` con un intervalo razonable (por ejemplo 750–1500 ms). Detener polling al salir de estados activos.

### Al completar

Mostrar:

- botón claro `Descargar PDF traducido`;
- páginas;
- bloques traducidos;
- `fit / shrunk / expanded / review_required`;
- advertencia visible si existen bloques `review_required`;
- modo utilizado (`Demo` o proveedor configurado lógico).

### En fallo

Mostrar un mensaje humano y sanitizado, con posibilidad de reintentar sin recargar toda la página cuando sea razonable.

---

# 11. Capacidades del servidor

La UI necesita saber si la traducción real está disponible sin exponer secretos.

Implementa una respuesta segura, por ejemplo:

`GET /api/v1/capabilities`

que pueda devolver únicamente algo como:

```json
{
  "demo_translation": true,
  "configured_translation_available": true,
  "configured_provider": "openai",
  "max_upload_size_mb": 25
}
```

No devolver:

- API key;
- `base_url` sensible/interno;
- headers;
- tokens;
- secretos;
- configuración completa de Settings.

Si ya existe un endpoint equivalente, reutilízalo.

---

# 12. Concurrencia y límites MVP

Mantén esto pequeño.

Como mínimo evita que un usuario pueda crear trabajos ilimitados que permanezcan en memoria eternamente.

Configura límites razonables y testeables, por ejemplo:

- máximo de jobs retenidos;
- TTL;
- upload máximo ya existente;
- opcionalmente un máximo pequeño de trabajos activos en paralelo.

No construyas rate limiting completo, cuotas comerciales ni multi-tenancy; corresponden a fases posteriores.

---

# 13. Tests obligatorios

Agrega cobertura offline para demostrar al menos:

1. modelos/estados de job serializables y tipados;
2. creación de job demo válida → 202;
3. transición demo completa hasta `completed`;
4. resultado PDF descargable y válido;
5. modo demo usa siempre `MockTranslator`;
6. modo configured usa factory/proveedor configurado sin exponer key;
7. modo configured sin configuración válida falla de forma controlada y no inicia job;
8. ninguna prueba hace red real;
9. job inexistente → 404;
10. result antes de completar → 409;
11. job fallido queda `failed` con error sanitizado;
12. marcador confidencial dentro de excepción no aparece en HTTP ni logs;
13. upload vacío/inválido/excedido se rechaza apropiadamente;
14. nombre de descarga sanitizado;
15. cleanup/TTL elimina jobs expirados;
16. límite de jobs evita crecimiento no acotado;
17. pipeline usa `DocumentAnalyzer → TranslationEngine → LayoutEngine → PDFRenderer` sin HTTP interno;
18. output puede abrirse con PyMuPDF;
19. original permanece inmutable;
20. métricas de layout finales llegan al estado del job;
21. `review_required > 0` se refleja en el resultado/estado;
22. capabilities nunca contiene secretos;
23. UI contiene controles de demo/real y aviso explícito de coste/consumo para modo real;
24. polling se detiene en `completed`/`failed`;
25. flujo web puede completarse con fixture pequeña sin comandos manuales.

Usa `httpx.MockTransport`, fake translator, monkeypatch o equivalentes para el modo configured. No uses una API key real.

---

# 14. Prueba E2E local obligatoria

Con una fixture programática o PDF local pequeño:

1. levantar FastAPI;
2. abrir `/`;
3. cargar PDF;
4. analizar;
5. ejecutar modo demo;
6. observar estados;
7. descargar resultado;
8. abrir el PDF generado con PyMuPDF;
9. comprobar páginas y texto esperado.

Después prueba el modo `configured` únicamente con proveedor falso/mockeado localmente, no con red real.

Si el manual MICRON está disponible localmente, úsalo solo en **modo demo** para verificar que el job de 90 páginas transita hasta `completed` y descarga el PDF. No lo copies al repositorio ni ejecutes traducción real sobre sus 1.894 bloques.

---

# 15. Documentación

Crea un ADR nuevo, por ejemplo:

`docs/decisions/0005-mvp-job-orchestration.md`

Documenta:

- por qué el store es efímero/in-memory en Fase 4;
- estados del job;
- forma de ejecución dentro del proceso;
- límites/TTL;
- separación entre modo demo y configured;
- política para evitar consumo accidental;
- endpoints;
- seguridad de errores/logs;
- limitaciones frente a producción;
- qué se moverá a Fase 6 (workers, Redis, PostgreSQL, persistencia, cuotas, observabilidad de jobs).

Actualiza `README.md` solo con funcionalidad realmente implementada.

No cambies el roadmap salvo que sea necesario para reflejar una decisión real ya implementada.

---

# 16. Fuera de alcance

No implementar todavía:

- PostgreSQL;
- Redis;
- Celery/RQ/Arq u otros workers externos;
- jobs durables entre reinicios;
- autenticación;
- usuarios;
- pagos;
- planes/quotas comerciales;
- historial persistente;
- almacenamiento S3/MinIO;
- OCR;
- traducción de texto dentro de imágenes;
- DOCX/PPTX;
- QA visual automático completo;
- edición manual avanzada de bloques;
- exactitud tipográfica por span;
- streaming complejo del PDF;
- WebSockets si polling simple es suficiente;
- React/Next.js si el frontend actual puede soportar limpiamente el MVP.

Evita sobrearquitectura.

---

# 17. Reglas de trabajo

- Rama sugerida: `feat/mvp-application` basada en `main`.
- No trabajar directamente en `main`.
- No merge automático.
- No push sin autorización.
- No commit al terminar salvo autorización.
- Python 3.12 baseline.
- Mantener tests offline.
- No versionar PDFs reales ni outputs.
- No registrar texto completo de documentos ni secretos.
- No cambiar algoritmos de layout/render si no existe un bug reproducible relacionado con esta fase.
- Si una decisión de jobs amenaza con introducir infraestructura de Fase 6, elige la opción más simple y documenta la limitación.

---

# 18. Validaciones finales

Ejecuta realmente:

```powershell
.venv\Scripts\pytest.exe -v
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
git diff --check
git status --short
git branch --show-current
```

Además:

- Docker rebuild si cambian runtime/dependencias;
- `/health`;
- `/`;
- `GET /api/v1/capabilities`;
- creación/consulta/resultado de job demo;
- validación de errores 404/409/413/422/500;
- comprobación de ausencia de secretos;
- apertura del PDF final con PyMuPDF;
- prueba E2E web local.

---

# 19. Criterio de salida de Fase 4

La Fase 4 queda completada cuando una persona puede, desde la interfaz web de Tradux:

1. subir un PDF digital;
2. analizarlo;
3. configurar origen/destino y términos protegidos;
4. elegir de forma consciente modo demo o traducción real configurada;
5. iniciar un trabajo;
6. observar su estado por etapas;
7. obtener un fallo comprensible y seguro si algo sale mal;
8. descargar un PDF reconstruido cuando termina;
9. ver métricas básicas de layout/revisión;
10. completar todo el flujo sin ejecutar comandos manuales.

Y, técnicamente:

- el flujo reutiliza los motores existentes;
- no hay red real en tests;
- secretos no llegan al cliente;
- jobs están acotados y expiran;
- el proceso puede perder trabajos al reiniciar y esto está documentado;
- no se introdujo infraestructura de producción prematuramente.

---

# 20. Entregable final

Al finalizar informa:

1. resumen de implementación;
2. árbol de archivos creados/modificados;
3. modelo y estados de job;
4. estrategia de almacenamiento efímero;
5. orquestación del pipeline;
6. diferencia demo/configured;
7. política anti-consumo accidental;
8. endpoints y contratos;
9. progreso/estado expuesto;
10. cambios de UI;
11. manejo de errores y seguridad;
12. TTL/límites de memoria;
13. tests añadidos y resultado total;
14. prueba E2E local;
15. resultado MICRON demo si se ejecutó;
16. limitaciones conocidas;
17. `git status --short`;
18. propuesta de commit convencional.

No hagas commit, push ni merge automáticamente.
