# Prompt 05 — QA automático y validación de entregabilidad

Usa este prompt desde la raíz del repositorio en una rama nueva basada en `main`.

---

Estamos desarrollando **Tradux**, una aplicación web para traducir documentos preservando al máximo su maquetación original.

Las Fases 0, 1, 2, 2.5, 3 y 4 ya están completadas. Tradux dispone actualmente de:

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
- `RenderResult` con métricas de bloques renderizados, omitidos, `review_required`, sustituciones de fuente y warnings;
- Web Workbench específico de Tradux;
- jobs efímeros en memoria con API `/api/v1/jobs`;
- flujo MVP completo `PDF → análisis → traducción → layout → reconstrucción → descarga`;
- benchmark local MICRON de 90 páginas validado manualmente y nunca versionado.

Antes de modificar nada, lee completos:

- `README.md`
- `docs/architecture.md`
- `docs/roadmap.md`
- `docs/decisions/0001-initial-stack.md`
- `docs/decisions/0002-document-model-and-analyzer.md`
- `docs/decisions/0003-translation-engine-and-provider-abstraction.md`
- `docs/decisions/0004-layout-engine-and-pdf-reconstruction.md`
- `docs/decisions/0005-mvp-job-orchestration.md`
- `prompts/00-bootstrap.md`
- `prompts/01-document-analyzer.md`
- `prompts/02-translation-engine.md`
- `prompts/02-5-web-workbench.md`
- `prompts/03-layout-and-reconstruction.md`
- `prompts/04-mvp-application.md`
- `app/layout/models.py`
- `app/renderers/models.py`
- `app/renderers/pymupdf_renderer.py`
- `app/jobs/models.py`
- `app/jobs/store.py`
- `app/jobs/service.py`

## Objetivo de esta tarea

Implementar la **Fase 5 — QA automático**.

Tradux ya puede generar un PDF reconstruido. En esta fase debe poder determinar, mediante un conjunto de validaciones estructuradas y conservadoras, si ese resultado puede declararse entregable, si requiere advertencias/revisión humana o si presenta errores que deben bloquear el éxito del trabajo.

El criterio de salida de esta fase es:

> **Ningún job de traducción se declara exitoso sin haber generado y almacenado un `QAReport` estructurado.**

El pipeline objetivo debe quedar conceptualmente así:

```text
PDF fuente
    ↓
DocumentAnalyzer
    ↓
TranslationEngine
    ↓
LayoutEngine
    ↓
PyMuPDFRenderer
    ↓
QualityAnalyzer
    ↓
QAReport
    ↓
completed / failed según resultado QA
```

La Fase 5 no debe intentar convertir Tradux en una plataforma de producción. Persistencia durable, Redis, workers externos, autenticación, pagos y OCR siguen fuera de alcance.

---

# 1. Principios obligatorios

1. El QA debe ser una etapa independiente del `LayoutEngine` y del `PDFRenderer`.
2. Los modelos públicos de QA no deben depender de clases de PyMuPDF.
3. Un `QAReport` debe ser serializable, determinista y apto para API/UI.
4. El QA puede usar una implementación concreta basada en PyMuPDF internamente cuando necesite inspeccionar el PDF final, pero esa dependencia no debe filtrarse al dominio de QA.
5. Las comprobaciones deben ser conservadoras y evitar falsos positivos obvios.
6. No usar IA/LLM para decidir calidad visual o lingüística en esta fase.
7. No hacer llamadas de red en tests.
8. No registrar texto completo del documento, PDF completo, traducciones completas ni secretos en logs/excepciones.
9. El QA no debe modificar el PDF fuente, el `Document`, el `DocumentLayout` ni el PDF renderizado.
10. Los errores internos del QA deben quedar sanitizados.
11. El resultado del QA debe integrarse en el job MVP y ser visible desde la UI.
12. No declarar `completed` antes de terminar QA.

---

# 2. Dominio de QA

Implementa modelos tipados bajo `app/quality/`, por ejemplo:

```text
app/quality/
├── __init__.py
├── models.py
├── analyzer.py
└── visual.py        # solo si aporta claridad real
```

## Severidades

Define un enum estable, por ejemplo:

```python
class QASeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
```

Semántica:

- `INFO`: hallazgo informativo, nunca bloquea;
- `WARNING`: el documento puede entregarse, pero requiere atención/revisión;
- `ERROR`: el documento no debe declararse exitoso/entregable.

No uses strings dispersos.

## Estado global

Define un estado global estable, por ejemplo:

```python
class QAStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
```

Regla mínima:

- cualquier `ERROR` → `FAIL`;
- sin errores pero con al menos un `WARNING` → `WARNING`;
- sin errores ni warnings → `PASS`.

## `QAIssue`

Como mínimo:

- código estable (`code`);
- severidad;
- mensaje humano corto y sanitizado;
- `page_number: int | None`;
- `reading_order: int | None`;
- metadata segura y primitiva opcional.

No incluyas texto completo fuente/traducido en los issues públicos.

## `QAReport`

Como mínimo:

- `status: QAStatus`;
- `issues: list[QAIssue]`;
- contadores `info_count`, `warning_count`, `error_count`;
- páginas fuente/final;
- cantidad de bloques evaluados;
- cantidad de bloques renderizados;
- `review_required_count`;
- `font_substitutions`;
- métricas visuales agregadas opcionales si se implementan de forma fiable;
- metadata de ejecución segura opcional.

Preferir modelos Pydantic v2 `frozen=True` cuando sean naturalmente inmutables.

Debe existir roundtrip JSON determinista.

---

# 3. Códigos de issue estables

Usa un enum o constantes centralizadas. Como mínimo contempla códigos equivalentes a:

- `INVALID_RESULT_PDF`;
- `PAGE_COUNT_MISMATCH`;
- `PAGE_DIMENSIONS_MISMATCH`;
- `PAGE_ROTATION_MISMATCH`;
- `MISSING_TRANSLATION`;
- `LAYOUT_REVIEW_REQUIRED`;
- `LAYOUT_SKIPPED_TRANSLATABLE`;
- `RENDER_INSERTION_DEFICIT`;
- `RENDERED_TEXT_MISSING`;
- `SOURCE_TEXT_REMAINS`;
- `FONT_SUBSTITUTION`;
- `VISUAL_ANOMALY`.

Los nombres exactos pueden ajustarse, pero deben ser estables y testeados.

No uses el mensaje humano como identificador lógico.

---

# 4. Entradas del `QualityAnalyzer`

Diseña una API explícita y pequeña, conceptualmente similar a:

```python
report = analyzer.analyze(
    source_pdf=source_pdf,
    source_document=source_document,
    translated_document=translated_document,
    layout=layout,
    render_result=render_result,
)
```

Puede ser síncrono; el job lo ejecutará mediante `asyncio.to_thread()` porque puede incluir parsing/renderizado con PyMuPDF.

No hagas que `QualityAnalyzer` consulte endpoints HTTP ni el `JobStore`.

Debe recibir los artefactos que necesita directamente.

---

# 5. Validaciones estructurales obligatorias

## 5.1 PDF final válido

- `render_result.pdf_bytes` debe poder abrirse como PDF;
- cero bytes o PDF corrupto → `ERROR / INVALID_RESULT_PDF`;
- no propagar mensajes crudos de PyMuPDF al API/log.

## 5.2 Número de páginas

Comparar:

- `source_document.page_count`;
- `render_result.page_count`;
- páginas realmente observadas al abrir el PDF final.

Cualquier discrepancia → `ERROR / PAGE_COUNT_MISMATCH`.

## 5.3 Dimensiones de página

Para cada página:

- comparar dimensiones del espacio canónico no rotado fuente contra el PDF final;
- usar tolerancia pequeña y explícita en puntos para diferencias numéricas inevitables;
- no mezclar `page.rect` rotado con `cropbox` canónico.

Discrepancia significativa → `ERROR / PAGE_DIMENSIONS_MISMATCH`.

Debe existir test específico de página rotada 90°/270° para evitar regresión del problema geométrico ya resuelto en Fases 1 y 3.

## 5.4 Rotación

La rotación final debe coincidir con la fuente (`0/90/180/270`).

Discrepancia → `ERROR / PAGE_ROTATION_MISMATCH`.

---

# 6. Validaciones de traducción

## 6.1 Bloques traducibles sin traducción

Para cada `TextBlock` con texto fuente no vacío/no whitespace que participe del flujo traducible:

- `translated_text is None` o vacío debe detectarse;
- bloques realmente vacíos/whitespace no deben generar error.

Resultado esperado: `ERROR / MISSING_TRANSLATION` con `page_number` + `reading_order`.

No incluir el texto del bloque en el issue.

## 6.2 Layout `SKIPPED`

Si un bloque no vacío con traducción esperada queda `SKIPPED`, debe producir un issue.

Por defecto:

- bloque vacío correctamente omitido → no issue o `INFO`;
- bloque no vacío traducible omitido → `ERROR / LAYOUT_SKIPPED_TRANSLATABLE`.

## 6.3 `REVIEW_REQUIRED`

Un `LayoutStatus.REVIEW_REQUIRED` significa que el layout no encontró una solución legible y el renderer conserva el texto fuente.

En V0.1 clasifícalo como **`WARNING`**, no como error automático, porque Tradux ya expone este estado como necesidad explícita de revisión humana y puede seguir siendo útil permitir descarga del documento con advertencia visible.

Debe generar `LAYOUT_REVIEW_REQUIRED` con localización segura.

No dupliques el mismo issue dos veces si layout y renderer reportan exactamente el mismo caso.

---

# 7. Validaciones del renderer

`RenderResult` ya expone:

- `rendered_blocks`;
- `skipped_blocks`;
- `review_required_blocks`;
- `font_substitutions`;
- `warnings`.

Aprovecha estas señales en vez de reimplementar toda la lógica del renderer.

## 7.1 Déficit de inserción

El renderer actual detecta `insert_textbox()` con retorno negativo y agrega un warning de déficit.

No dependas únicamente de parsear texto humano libre si puedes introducir una representación estructurada mínima sin romper compatibilidad.

Preferencia:

- si resulta limpio, extiende `RenderResult` con una lista tipada/estructurada de problemas de render (`page_number`, `reading_order`, `kind`);
- conserva `warnings` para compatibilidad humana;
- el QA convierte un déficit de inserción en `ERROR / RENDER_INSERTION_DEFICIT`.

Si modificar `RenderResult` de ese modo produce una refactorización excesiva, documenta la limitación y implementa la alternativa más pequeña y testeable. No sobrearquitectes.

## 7.2 Sustitución de fuentes

`is_font_substituted` / `font_substitutions` no es por sí mismo un fallo fatal.

Genera:

- `WARNING / FONT_SUBSTITUTION` por bloque o una agregación útil;
- evita producir cientos de issues idénticos si un documento grande sustituye la misma fuente en muchos bloques.

El reporte debe mantener el contador total aunque agrupe issues.

---

# 8. Verificación de texto en el PDF final

Esta validación debe ser **conservadora**.

No intentes demostrar calidad lingüística.

Para bloques `FIT`, `SHRUNK` o `EXPANDED`:

- debe existir `translated_text`;
- el `BlockLayout.text` debe corresponder a la traducción planificada;
- inspecciona el texto extraído de la página final y comprueba que la traducción esperada aparezca de forma razonable después de normalizar únicamente whitespace/line breaks necesarios para extracción PDF.

No hagas normalizaciones agresivas de signos, números o contenido.

Si una traducción que debía renderizarse no puede localizarse de forma fiable → `ERROR / RENDERED_TEXT_MISSING`.

### Fuente remanente

Detecta `SOURCE_TEXT_REMAINS` solo de forma conservadora:

- el bloque era renderizable (`FIT/SHRUNK/EXPANDED`);
- fuente y traducción son realmente diferentes;
- la traducción esperada no contiene el texto fuente como subcadena;
- aparece el texto fuente original en la página final mientras la traducción esperada no aparece.

Esto evita falsos positivos con `MockTranslator`, que puede incluir el texto fuente dentro de su salida sintética.

Si no puedes demostrar el remanente con suficiente confianza, no generes el issue.

---

# 9. Overflow y geometría

No inventes detección de overflow basada en contar caracteres.

Usa señales existentes:

- `LayoutStatus.REVIEW_REQUIRED`;
- déficit real de `insert_textbox()`;
- `render_bbox`;
- métricas del renderer.

Si agregas una comprobación geométrica adicional, debe apoyarse en coordenadas reales y tolerancias explícitas.

No conviertas esta fase en un segundo `LayoutEngine`.

---

# 10. Comparación visual automatizada

El roadmap requiere renderizado de páginas para comparación visual. Implementa una señal **simple, reproducible y conservadora**, no un sistema de visión artificial.

Objetivo: detectar cambios inesperados fuera de las zonas donde Tradux esperaba modificar texto.

Enfoque recomendado:

1. renderiza fuente y resultado a resolución moderada/configurable usando PyMuPDF;
2. identifica las regiones esperadas de cambio usando los `bbox`/`render_bbox` de bloques `FIT`, `SHRUNK` y `EXPANDED`;
3. excluye o enmascara esas regiones del cálculo;
4. compara el resto de la página;
5. calcula una métrica simple de diferencia fuera de regiones esperadas;
6. si supera un umbral configurable y testeado, genera `WARNING / VISUAL_ANOMALY`.

Requisitos:

- no agregar Pillow/OpenCV si PyMuPDF + operaciones simples sobre buffers bastan;
- no guardar imágenes de páginas permanentemente;
- tests con fixtures pequeñas;
- incluir caso de página rotada;
- no marcar como error bloqueante en V0.1: `VISUAL_ANOMALY` es `WARNING`;
- documentar el umbral y sus limitaciones.

Si el mapeo de coordenadas rotadas a pixeles requiere transformación, usa las matrices documentadas de PyMuPDF y agrega una prueba/probe explícita. No mezcles espacios de coordenadas silenciosamente.

La comparación visual debe ser opcionalmente desactivable por configuración para facilitar tests/diagnóstico, pero activada por defecto en el flujo normal si su implementación es robusta.

---

# 11. Resultado global y política de bloqueo

El `QualityAnalyzer` debe determinar `QAStatus` únicamente a partir de issues estructurados.

Política inicial:

### Bloquean (`ERROR`)

- PDF final inválido;
- número de páginas distinto;
- dimensiones/rotación incorrectas;
- bloque traducible sin traducción;
- bloque traducible omitido inesperadamente;
- déficit real de inserción del renderer;
- traducción renderizable claramente ausente del PDF final.

### No bloquean pero requieren advertencia (`WARNING`)

- `REVIEW_REQUIRED`;
- sustituciones de fuentes;
- anomalía visual fuera de zonas esperadas;
- texto fuente posiblemente remanente cuando la evidencia sea conservadora.

No permitas que mensajes de warnings del renderer se conviertan ciegamente en errores sin clasificación explícita.

---

# 12. Integración con jobs

Actualmente `TranslationJobService` marca `completed` inmediatamente después de renderizar. Cambia el workflow para agregar QA antes del estado terminal exitoso.

Conceptualmente:

```text
analyzing
translating
layout
rendering
qa
completed | failed
```

Agrega `JobStatus.QA = "qa"` o una representación equivalente estable.

Después de `renderer.render(...)`:

1. NO marques todavía `completed`;
2. conserva `RenderResult` en memoria local del workflow;
3. ejecuta `QualityAnalyzer` con `asyncio.to_thread()`;
4. almacena el `QAReport` en el `JobStore`;
5. actualiza resumen QA seguro en `Job`/`JobResponse`;
6. si `QAStatus.FAIL` → job `FAILED`, `result_available=False`, código estable como `QA_FAILED`;
7. si `PASS` o `WARNING` → guarda/habilita el PDF final y marca `COMPLETED`;
8. un job `COMPLETED` debe tener siempre reporte QA disponible.

### Importante sobre almacenamiento

No metas el reporte completo dentro del objeto `Job` si vuelve el polling innecesariamente pesado.

Preferencia:

- `Job`/`JobResponse`: resumen pequeño;
- `JobStore`: `QAReport` completo asociado por `job_id`;
- endpoint dedicado para leer el reporte.

Al eliminar/expirar un job, elimina también su QA report del store.

`clear()` debe limpiar también reportes QA.

---

# 13. Resumen QA dentro del job

Agrega una representación pequeña, por ejemplo `JobQASummary`, con:

- `status`;
- `info_count`;
- `warning_count`;
- `error_count`;
- `review_required_count`;
- `font_substitutions`;
- `report_available`.

No incluyas issues completos ni texto documental en el polling normal.

La UI debe poder distinguir:

- completado sin advertencias;
- completado con warnings;
- fallado por QA.

---

# 14. API de reporte QA

Agrega:

```text
GET /api/v1/jobs/{job_id}/qa
```

Comportamiento recomendado:

- `200` + `QAReport` cuando existe;
- `404` si job no existe/expiró;
- `409` si el job aún no llegó a QA o el reporte todavía no está disponible.

Nunca devolver secretos ni texto completo fuente/traducido.

No agregues historial global de reportes.

---

# 15. Descarga del resultado y QA fallido

Mantén una política inequívoca:

- `QAStatus.PASS` o `WARNING` → resultado descargable;
- `QAStatus.FAIL` → resultado NO disponible mediante el endpoint normal de descarga.

El PDF renderizado que falló QA puede existir transitoriamente dentro del método mientras se analiza, pero no debe publicarse como resultado exitoso.

No implementes un endpoint de “forzar descarga” en esta fase.

---

# 16. Interfaz Web Workbench

Evoluciona la UI existente, no la reemplaces.

## Durante procesamiento

Agrega etapa visible:

```text
Validando calidad
```

Polling debe reconocer `qa` como estado activo.

## Al completar

Muestra un bloque compacto de QA con:

- `Aprobado`, `Con advertencias` o `Fallido`;
- cantidad de warnings/errors;
- `review_required`;
- sustituciones de fuente;
- botón/acción `Ver reporte QA`.

### `PASS`

Mostrar claramente que el QA automático no encontró problemas bloqueantes.

### `WARNING`

Permitir descarga, pero mostrar advertencia visible antes/del lado del botón.

### `FAIL`

No mostrar `Descargar PDF traducido` como si fuese un resultado válido.

Mostrar resumen sanitizado y acceso al reporte QA.

## Reporte

Puede mostrarse en panel/modal existente, sin construir un sistema de dashboards.

Cada issue puede mostrar:

- severidad;
- código;
- página/bloque si existe;
- mensaje corto.

No mostrar texto completo del documento dentro del reporte.

---

# 17. Configuración

Agrega únicamente settings que aporten valor real y sean testeables, por ejemplo:

- habilitar/deshabilitar comparación visual;
- DPI/escala moderada para comparación;
- tolerancia de dimensiones de página;
- umbral de diferencia visual.

Nombres exactos pueden adaptarse a la convención actual de `Settings`.

No agregues docenas de knobs prematuramente.

Incluye valores seguros en `.env.example`.

---

# 18. Seguridad y privacidad

Tests obligatorios deben demostrar que:

- errores QA no incluyen texto documental completo;
- issues no incluyen API keys;
- logs no incluyen `source_text`, `translated_text`, JSON documental completo ni bytes;
- mensajes de PyMuPDF se sanitizan antes de llegar al API;
- endpoint QA devuelve únicamente estructuras seguras;
- el reporte visual no persiste imágenes de las páginas.

Usa textos/secretos falsos reconocibles en tests para detectar fugas, por ejemplo:

```text
SUPER_SECRET_QA_DOCUMENT_TEXT_123
sk-test-qa-secret-value
```

---

# 19. Tests obligatorios

Agrega tests suficientes para demostrar como mínimo:

1. enums/severidades y cálculo de `QAStatus`;
2. roundtrip JSON de `QAReport`;
3. PDF final válido produce reporte;
4. PDF final corrupto → `INVALID_RESULT_PDF`;
5. mismatch de número de páginas → `ERROR`;
6. mismatch de dimensiones → `ERROR`;
7. mismatch de rotación → `ERROR`;
8. páginas rotadas mantienen comparación en espacio canónico correcto;
9. bloque no vacío sin `translated_text` → `MISSING_TRANSLATION`;
10. whitespace no genera `MISSING_TRANSLATION`;
11. `SKIPPED` traducible → `ERROR`;
12. `REVIEW_REQUIRED` → `WARNING`;
13. déficit real de inserción del renderer → `ERROR`;
14. sustitución de fuente → `WARNING` y contador correcto;
15. traducción renderizada puede encontrarse en PDF final;
16. traducción claramente ausente → `RENDERED_TEXT_MISSING`;
17. `SOURCE_TEXT_REMAINS` evita falsos positivos cuando traducción contiene el texto fuente (modo mock);
18. comparación visual sin cambios fuera de regiones esperadas no genera issue;
19. modificación inesperada fuera de regiones esperadas genera `VISUAL_ANOMALY`;
20. comparación visual funciona con página rotada;
21. `TranslationJobService` pasa por estado QA antes de completed;
22. job PASS termina `completed` y resultado disponible;
23. job WARNING termina `completed` y resultado disponible con summary warning;
24. job FAIL termina `failed` y resultado no disponible;
25. todo job `completed` tiene `qa_report` almacenado;
26. `JobStore` elimina QA report con `delete`, TTL y `clear`;
27. `GET /api/v1/jobs/{id}/qa` devuelve 200 cuando existe;
28. endpoint QA devuelve 409 antes de disponibilidad;
29. endpoint QA devuelve 404 para job inexistente/expirado;
30. polling/API normal incluye solo `JobQASummary`, no reporte pesado;
31. Web Workbench reconoce estado `qa` y muestra summary;
32. descarga se bloquea cuando QA falla;
33. errores/logs/reportes no filtran texto sensible ni secretos;
34. pipeline completo fixture PDF → análisis → traducción mock → layout → render → QA → completed;
35. tests 100% offline y deterministas.

No reduzcas cobertura existente.

---

# 20. Benchmark MICRON

El manual MICRON de 90 páginas puede utilizarse **solo localmente** y nunca versionarse.

Benchmark útil de esta fase:

1. ejecutar el flujo completo en `demo`;
2. generar `QAReport`;
3. registrar métricas agregadas:
   - páginas;
   - bloques;
   - `fit/shrunk/expanded/review_required`;
   - sustituciones de fuente;
   - issues INFO/WARNING/ERROR;
   - páginas con anomalía visual;
   - tiempo de QA;
4. inspeccionar manualmente algunas páginas representativas para comparar la utilidad de los hallazgos automáticos.

No usar proveedor real para las 90 páginas durante benchmark automático.

No versionar PDF, screenshots ni reportes derivados si contienen contenido del manual.

---

# 21. Rendimiento

QA sobre documentos grandes no debe bloquear el event loop.

- ejecuta parsing/render/comparación visual síncrona mediante `asyncio.to_thread()` desde jobs;
- procesa página a página;
- no mantengas pixmaps de todas las páginas simultáneamente;
- libera referencias grandes tan pronto como sea razonable;
- evita copias completas innecesarias de PDFs grandes.

No agregues multiprocessing, Celery o workers en esta fase.

---

# 22. ADR y documentación

Crea:

```text
docs/decisions/0006-automatic-quality-assurance.md
```

Debe documentar al menos:

- dominio `QAReport` / `QAIssue`;
- severidades y política `PASS/WARNING/FAIL`;
- checks bloqueantes vs warnings;
- integración QA antes de `completed`;
- política de descarga cuando QA falla;
- comparación visual conservadora;
- geometría canónica y páginas rotadas;
- privacidad/sanitización;
- almacenamiento efímero del reporte en Fase 5;
- limitaciones conocidas.

Actualiza README únicamente con comportamiento realmente implementado y probado.

Actualiza `docs/roadmap.md` solo si necesitas reflejar de forma mínima que la Fase 5 está implementada; no reescribas el roadmap completo.

---

# 23. Límites explícitos de Fase 5

No implementes todavía:

- evaluación lingüística con LLM;
- puntuación semántica de traducción;
- OCR;
- texto dentro de imágenes;
- revisión humana colaborativa;
- editor visual de bloques;
- almacenamiento permanente de reportes;
- PostgreSQL;
- Redis;
- Celery/RQ/workers externos;
- autenticación;
- pagos;
- cuotas comerciales;
- historial de usuario;
- observabilidad de producción;
- CI/CD completo;
- comparación visual basada en modelos de visión;
- soporte DOCX/PPTX.

Evita sobrearquitectura.

---

# 24. Reglas de trabajo

- Trabaja en una rama nueva basada en `main`, sugerida: `feat/automatic-qa`.
- No trabajes directamente en `main`.
- No hagas merge.
- No hagas push sin autorización.
- No hagas commit al terminar salvo autorización explícita.
- Mantén Python 3.12 como baseline.
- Código tipado y módulos pequeños.
- Tests offline.
- Reutiliza modelos/señales existentes antes de duplicar lógica.
- No uses `str(e)` en respuestas/logs donde la excepción pueda contener contenido documental.
- No elimines ni relajes tests existentes para hacer pasar la fase.
- Si una ambigüedad menor existe, elige la opción más simple, documenta la decisión y continúa.

---

# 25. Validaciones antes de terminar

Ejecuta realmente:

```powershell
.venv\Scripts\pytest.exe -v
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
git diff --check
git status --short
git branch --show-current
```

Si cambian dependencias runtime:

```powershell
docker build -t tradux:qa .
docker run -d --name tradux_qa_test -p 8001:8000 tradux:qa
curl.exe -s http://localhost:8001/health
docker rm -f tradux_qa_test
```

Valida además mediante fixture reproducible el pipeline real completo en modo mock:

```text
PDF → análisis → traducción → layout → render → QA
```

y comprueba que:

- se genera `QAReport`;
- el job no llega a `completed` antes de QA;
- PASS/WARNING permite resultado;
- FAIL bloquea resultado;
- el reporte puede consultarse por API;
- ningún test realiza llamadas externas.

---

# 26. Criterio de salida de Fase 5

La fase se considera completada cuando:

1. existe un dominio QA desacoplado y serializable;
2. el PDF final se valida estructuralmente contra la fuente;
3. se detectan traducciones ausentes y fallos de render relevantes;
4. `REVIEW_REQUIRED`, sustituciones de fuente y anomalías visuales quedan reportadas;
5. existe comparación visual conservadora fuera de regiones esperadas de cambio;
6. existe política estable `PASS / WARNING / FAIL`;
7. el job incluye una etapa real `qa`;
8. ningún job puede quedar `completed` sin QA report;
9. un QA `FAIL` bloquea la descarga normal;
10. PASS/WARNING permite descarga y la UI muestra el estado QA;
11. el reporte completo se almacena efímeramente y se elimina junto al job;
12. existe endpoint seguro para consultar el reporte;
13. la UI presenta resumen e issues sin filtrar contenido documental;
14. tests permanecen 100% offline;
15. benchmark MICRON puede ejecutarse localmente sin versionar artefactos.

---

# 27. Entregable

Al finalizar informa:

1. resumen de lo implementado;
2. árbol de archivos creados/modificados;
3. modelos de QA y códigos/severidades;
4. checks estructurales implementados;
5. checks de traducción/render implementados;
6. estrategia de comparación visual;
7. política PASS/WARNING/FAIL;
8. integración exacta con `TranslationJobService`;
9. cambios en `Job`, `JobStore` y API;
10. cambios del Web Workbench;
11. seguridad y sanitización;
12. configuración nueva;
13. comandos de validación y resultados;
14. número total de tests y tests nuevos;
15. resultado del benchmark local si se ejecutó;
16. limitaciones conocidas;
17. `git status --short`;
18. propuesta de mensaje de commit convencional.

No hagas commit, push ni merge automáticamente.

---
