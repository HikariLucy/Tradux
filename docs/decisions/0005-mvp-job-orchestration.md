# 5. Orquestacion de trabajos MVP (Job Pipeline) y almacenamiento efimero

Fecha: 2026-09-04

## Estado

Aceptada

## Contexto

Con las bases de extraccion estructural (DocumentAnalyzer, Fase 1), motor de traduccion desacoplado (TranslationEngine, Fase 2), mesa de trabajo visual (Web Workbench, Fase 2.5) y reconstruccion tipografica con fidelidad visual (LayoutEngine + PyMuPDFRenderer, Fase 3), Tradux requiere consolidar el flujo completo en una aplicacion MVP unificada:

Subir PDF digital -> Analizar -> Configurar idiomas/terminos -> Crear trabajo de traduccion -> Progreso por etapas -> Descarga de PDF traducido

Para esta etapa MVP, la arquitectura resuelve tres desafios fundamentales:
1. Orquestacion limpia de los componentes existentes sin introducir infraestructura pesada ni permanente (PostgreSQL, Redis, Celery/RQ) antes de tiempo.
2. Proteccion estricta contra consumo accidental de tokens/creditos en proveedores externos de traduccion y garantia de que ninguna credencial o secreto viaje hacia o desde el cliente web.
3. Monitoreo claro de etapas y preservacion de la experiencia de usuario especializada en la 'Mesa de traduccion documental' desktop-first de Tradux, manteniendo los contratos anteriores intactos.

## Decisiones tomadas

### 1. Modelo de Trabajos y Almacenamiento Efimero en Memoria (JobStore)

- **Gestor en memoria indexado por UUID (pp.jobs.store.JobStore):** Para el alcance del MVP, el estado de los trabajos se gestiona en memoria de proceso protegido por cerrojos reentrantes de hilo (	hreading.Lock).
- **Separacion de metadatos y buffers binarios:** La metadata del trabajo (Job) se conserva separada de los payloads binarios en memoria (_source_pdfs: dict[str, bytes] y _result_pdfs: dict[str, bytes]). Esto permite deserializar e inspeccionar el estado sin clonar buffers pesados.
- **Control estricto de capacidad y TTL:**
  - job_ttl_seconds = 3600 (1 hora de retencion predeterminada).
  - job_max_retained = 20 (limite maximo de trabajos en memoria). Al superar el limite, se purgan automaticamente los trabajos completados/fallidos mas antiguos (LRU/FIFO por creacion).
  - job_max_active = 5 (limite de concurrencia activa en el servidor).
- **Liberacion inmediata de memoria:** El endpoint DELETE /api/v1/jobs/{job_id} elimina de forma atomica la metadata y purga los bytes del PDF original y resultado.
- **Transicion futura a Fase 6:** Al encapsular el acceso detras del contrato de interfaz JobStore, la migracion futura hacia almacenamiento persistente (PostgreSQL / Redis / MinIO) y colas distribuidas no requerira modificar la API REST ni el cliente web.

### 2. Orquestacion en Pipeline desacoplado (TranslationJobService)

El servicio TranslationJobService ejecuta el ciclo de vida completo en 4 etapas secuenciales discretas:

1. **nalyzing:** Invoca DocumentAnalyzer.analyze_bytes() para extraer paginas, geometrias y bloques textuales canonicos.
2. **	ranslating:**
   - En mode='demo': utiliza MockTranslator, sin realizar llamadas externas.
   - En mode='configured': utiliza el adaptador configurado en el servidor via get_translator(settings).
   - Aplica preservacion de terminos protegidos mediante mascaras deterministas.
3. **layout:** Invoca LayoutEngine.build() para evaluar la cascada de ajuste tipografico (fit, shrinking, safe vertical expansion) y detectar bloques con necesidad de revision manual (
eview_required).
4. **
endering:** Invoca PyMuPDFRenderer.render() ejecutando la redaccion no destructiva y la insercion del texto traducido en el PDF original.
5. **completed:** Guarda los bytes del PDF final en el almacen efimero y marca 
esult_available=True.

En caso de fallo en cualquiera de las etapas, el trabajo transita a ailed, registrando la etapa exacta y un mensaje generico seguro.

### 3. Capacidades seguras del servidor (GET /api/v1/capabilities) y prevencion de consumo accidental

- **Aislamiento de credenciales:** El frontend jamas recibe ni transmite API keys, contraseñas, URLs internas o tokens de sesion.
- El endpoint GET /api/v1/capabilities expone unicamente metadatos seguros de alto nivel:
  - Disponibilidad del modo demo (demo.available = True).
  - Disponibilidad del modo configurado (configured.available, configured.provider).
  - Nombre publico del proveedor (ej. 'openai'), sin URLs privadas ni detalles de infraestructura.
- **Proteccion UX contra consumo accidental:**
  - Si el servidor no tiene credenciales validas configuradas, la opcion de proveedor real se deshabilita automaticamente en la interfaz con un mensaje descriptivo.
  - Al seleccionar traduccion configurada, se despliega un aviso de consumo destacado.
  - Al pulsar 'Iniciar trabajo de traduccion', se exige un **modal de confirmacion previo** donde se desglosa el nombre del archivo, paginas detectadas, cantidad de bloques y proveedor destino antes de emitir la peticion.

### 4. Sanitizacion estricta de errores y logs

- **Seguridad en respuestas HTTP:** Los endpoints POST /api/v1/jobs, GET /api/v1/jobs/{id}, etc., nunca devuelven trazas de excepciones (	raceback), fragmentos de texto documental ni cadenas con posibles credenciales de proveedores.
- **Logs sanitizados:** Las excepciones en el pipeline registran exclusivamente el identificador de trabajo, la etapa del fallo y el tipo de clase de la excepcion (	ype(e).__name__):
  logger.error('Job %s failed in stage %s with exception: %s', job_id, stage, type(e).__name__)

### 5. Preservacion y evolucion del Web Workbench

- Se mantiene la 'Mesa de traduccion documental' de Tradux desarrollada con HTML5, CSS3 semantico y Vanilla JavaScript modular.
- Se evoluciona el Stepper visual para reflejar las etapas del trabajo real:
  1. Documento -> 2. Analisis -> 3. Configuracion -> 4. Traduccion & Layout -> 5. PDF Final.
- Se incorpora una tarjeta reactiva de seguimiento del trabajo (#job-card) con sondeo ligero periodico (GET /api/v1/jobs/{id} cada 1.5 s), mostrando estado en vivo y badge de progreso.
- Si el documento contiene bloques con desbordamiento (
eview_required_count > 0), se despliega una alerta visible informando que dichos bloques se mantuvieron con el texto original para evitar truncamientos y perdidas de contenido.

## Consecuencias

### Positivas
- Flujo de usuario continuo e intuitivo para validar el pipeline completo en menos de un minuto.
- Respeto total de la seguridad y confidencialidad documental y de credenciales.
- Codigo 100% testeable de forma offline, sin dependencias de red en la suite de pruebas unitarias y de integracion.
- Arquitectura lista para escalar a colas distribuidas en Fase 6 sin deuda tecnica en los contratos de la API publica.

### Limitaciones conocidas (a resolver en Fase 6)
- El estado y los PDFs procesados se pierden si el proceso de Uvicorn se reinicia.
- La ejecucion en un unico nodo limita la concurrencia a la memoria RAM disponible del servidor local.
