# 5. Orquestación de trabajos MVP (Job Pipeline) y almacenamiento efímero

Fecha: 2026-09-04

## Estado

Aceptada

## Contexto

Con las bases de extracción estructural (`DocumentAnalyzer`, Fase 1), motor de traducción desacoplado (`TranslationEngine`, Fase 2), mesa de trabajo visual (`Web Workbench`, Fase 2.5) y reconstrucción tipográfica con fidelidad visual (`LayoutEngine` + `PyMuPDFRenderer`, Fase 3), Tradux requiere consolidar el flujo completo en una aplicación MVP unificada:

$$\text{Subir PDF digital} \longrightarrow \text{Analizar} \longrightarrow \text{Configurar idiomas/términos} \longrightarrow \text{Crear trabajo de traducción} \longrightarrow \text{Progreso por etapas} \longrightarrow \text{Descarga de PDF traducido}$$

Para esta etapa MVP, la arquitectura resuelve tres desafíos fundamentales:
1. Orquestación limpia de los componentes existentes sin introducir infraestructura pesada ni permanente (PostgreSQL, Redis, Celery/RQ) antes de tiempo.
2. Protección estricta contra consumo accidental de tokens/créditos en proveedores externos de traducción y garantía de que ninguna credencial o secreto viaje hacia o desde el cliente web.
3. Monitoreo claro de etapas y preservación de la experiencia de usuario especializada en la "Mesa de traducción documental" desktop-first de Tradux, manteniendo los contratos anteriores intactos.

## Decisiones tomadas

### 1. Modelo de Trabajos y Almacenamiento Efímero en Memoria (`JobStore`)

- **Gestor en memoria indexado por UUID (`app.jobs.store.JobStore`):** Para el alcance del MVP, el estado de los trabajos se gestiona en memoria de proceso protegido por cerrojos de hilo estándar (`threading.Lock`).
- **Separación de metadatos y buffers binarios:** La metadata del trabajo (`Job`) se conserva separada de los payloads binarios en memoria (`_source_pdfs: dict[str, bytes]` y `_result_pdfs: dict[str, bytes]`). Esto permite deserializar e inspeccionar el estado sin clonar buffers pesados.
- **Control estricto de capacidad y TTL:**
  - `job_ttl_seconds = 3600` (1 hora de retención predeterminada).
  - `job_max_retained = 50` (límite máximo de trabajos en memoria). Al superar el límite, se purgan automáticamente los trabajos terminales más antiguos (LRU/FIFO por creación). Los trabajos activos en ejecución jamás son purgados por capacidad ni por TTL.
  - `job_max_active = 5` (límite de concurrencia activa en el servidor).
- **Liberación controlada de memoria:** El endpoint `DELETE /api/v1/jobs/{job_id}` elimina de forma atómica la metadata y purga los bytes del PDF original y resultado. Si el trabajo se encuentra en ejecución activa, la petición se rechaza con `409 Conflict`.
- **Transición futura a Fase 6:** Al encapsular el acceso detrás del contrato de interfaz `JobStore`, la migración futura hacia almacenamiento persistente (PostgreSQL / Redis / MinIO) y colas distribuidas no requerirá modificar la API REST ni el cliente web.

### 2. Orquestación en Pipeline desacoplado (`TranslationJobService`)

El servicio `TranslationJobService` ejecuta el ciclo de vida completo en etapas secuenciales discretas:

1. **`analyzing`:** Invoca `DocumentAnalyzer.analyze_bytes()` para extraer páginas, geometrías y bloques textuales canónicos de forma asíncrona mediante `asyncio.to_thread()`.
2. **`translating`:**
   - En `mode="demo"`: utiliza `MockTranslator`, sin realizar llamadas externas.
   - En `mode="configured"`: utiliza el adaptador configurado en el servidor vía `get_translator(settings)`.
   - Aplica preservación de términos protegidos mediante máscaras deterministas.
3. **`layout`:** Invoca `LayoutEngine.build()` mediante `asyncio.to_thread()` para evaluar la cascada de ajuste tipográfico (fit, shrinking, safe vertical expansion) y detectar bloques con necesidad de revisión manual (`review_required`).
4. **`rendering`:** Invoca `PyMuPDFRenderer.render()` mediante `asyncio.to_thread()` ejecutando la redacción no destructiva y la inserción del texto traducido en el PDF original.
5. **`completed`:** Guarda los bytes del PDF final en el almacén efímero y marca `result_available=True`.

En caso de fallo en cualquiera de las etapas, el trabajo transita a `failed`, registrando la etapa exacta y un mensaje genérico seguro.

### 3. Capacidades seguras del servidor (`GET /api/v1/capabilities`) y prevención de consumo accidental

- **Aislamiento de credenciales:** El frontend jamás recibe ni transmite API keys, contraseñas, URLs internas o tokens de sesión.
- **Contrato plano de capacidades (`ServerCapabilitiesResponse`):** El endpoint expone metadatos de configuración pública:
  ```json
  {
    "demo_translation": true,
    "configured_translation_available": false,
    "configured_provider": "mock",
    "max_upload_size_mb": 50
  }
  ```
- **Confirmación backend obligatoria para `mode="configured"`:**
  - `mode="demo"` no requiere confirmación.
  - Para `mode="configured"`, el backend exige explícitamente `confirm_configured=true` en el formulario multipart.
  - Si `confirm_configured` es falso o se omite, la petición es rechazada de inmediato con `409 Conflict`, sin crear el trabajo en el almacén ni invocar a la factoría de proveedores (`get_translator`).
- **Protección UX contra consumo accidental:**
  - Si el servidor no tiene credenciales válidas configuradas, la opción de proveedor real se deshabilita automáticamente en la interfaz con un mensaje descriptivo.
  - Al seleccionar traducción configurada, se despliega un aviso de consumo destacado.
  - Al pulsar "Iniciar trabajo de traducción", se exige un modal de confirmación previo que resume páginas, bloques y proveedor antes de que la UI envíe `confirm_configured=true`.

### 4. Sanitización estricta de errores y logs

- **Seguridad en respuestas HTTP:** Los endpoints `POST /api/v1/jobs`, `GET /api/v1/jobs/{id}`, etc., nunca devuelven trazas de excepciones (`traceback`), fragmentos de texto documental ni cadenas con posibles credenciales de proveedores.
- **Logs sanitizados:** Las excepciones en el pipeline registran exclusivamente el identificador de trabajo, la etapa del fallo y el tipo de clase de la excepción (`type(e).__name__`):
  ```python
  logger.error(
      "Job %s failed in stage %s with exception: %s", job_id, stage, type(e).__name__
  )
  ```

### 5. Preservación y evolución del Web Workbench

- Se mantiene la "Mesa de traducción documental" de Tradux desarrollada con HTML5, CSS3 semántico y Vanilla JavaScript modular.
- Se evoluciona el Stepper visual para reflejar las etapas del trabajo real:
  `1. Documento -> 2. Análisis -> 3. Configuración -> 4. Traducción & Layout -> 5. PDF Final`.
- Se incorpora una tarjeta reactiva de seguimiento del trabajo (`#job-card`) con sondeo ligero periódico (`GET /api/v1/jobs/{id}` cada 1.5 s), mostrando estado en vivo y badge de progreso.
- Si el documento contiene bloques con desbordamiento (`review_required_count > 0`), se despliega una alerta visible informando que dichos bloques se mantuvieron con el texto original para evitar truncamientos y pérdidas de contenido.

## Consecuencias

### Positivas
- Flujo de usuario continuo e intuitivo para validar el pipeline completo en menos de un minuto.
- Respeto total de la seguridad y confidencialidad documental y de credenciales.
- Código 100% testeable de forma offline, sin dependencias de red en la suite de pruebas unitarias y de integración.
- Arquitectura lista para escalar a colas distribuidas en Fase 6 sin deuda técnica en los contratos de la API pública.

### Limitaciones conocidas (a resolver en Fase 6)
- El estado y los PDFs procesados se pierden si el proceso de Uvicorn se reinicia.
- La ejecución en un único nodo limita la concurrencia a la memoria RAM disponible del servidor local.
