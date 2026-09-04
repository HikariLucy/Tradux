# Tradux

Tradux es una aplicación para traducir documentos entre idiomas preservando al máximo su maquetación original.

## Objetivo inicial

Construir un MVP capaz de recibir un PDF digital, detectar o aceptar el idioma de origen, traducirlo al idioma de destino y generar un nuevo PDF conservando, en la medida de lo posible:

- dimensiones y número de páginas;
- imágenes y diagramas;
- posiciones de los bloques de texto;
- colores y jerarquía visual;
- tablas y numeración;
- encabezados y pies de página;
- tipografías o sustitutos métricamente compatibles.

El primer caso de referencia del proyecto es un manual técnico de 90 páginas cuya traducción neerlandés → español ya fue reconstruida manualmente. Ese documento servirá como benchmark de regresión visual y funcional para Tradux.

## Alcance V0.1

La primera versión se concentrará en PDFs digitales con texto seleccionable.

Incluye:

1. carga de PDF;
2. análisis de páginas y bloques de texto;
3. detección de idioma;
4. selección de idioma destino;
5. traducción mediante un proveedor desacoplado;
6. reconstrucción del texto sobre la maquetación original;
7. ajuste automático de fuente e interlineado cuando el texto traducido no quepa;
8. generación del PDF final;
9. validaciones básicas de calidad.

Fuera de alcance inicialmente:

- OCR de documentos escaneados;
- edición de texto incrustado dentro de imágenes;
- DOCX, PPTX u otros formatos;
- colaboración multiusuario;
- facturación o SaaS público.

## Arquitectura propuesta

- **Backend:** Python + FastAPI
- **Motor PDF:** PyMuPDF
- **Traducción:** interfaz de proveedor intercambiable
- **Frontend inicial:** interfaz web ligera; se evaluará React/Next.js cuando el flujo base esté estable
- **Persistencia:** inicialmente sistema de archivos y metadatos simples; PostgreSQL cuando exista historial de trabajos
- **Procesamiento asíncrono:** se incorporará Redis/worker cuando los trabajos largos lo requieran
- **Contenedores:** Docker
- **Pruebas:** pytest

Más detalle en [`docs/architecture.md`](docs/architecture.md).

## Principios del proyecto

- Preservar el documento antes que rediseñarlo.
- Nunca sacrificar legibilidad para forzar una traducción dentro de una caja.
- Mantener separados extracción, traducción, layout, renderizado y QA.
- Registrar decisiones y métricas para que los resultados sean reproducibles.
- Permitir cambiar el proveedor de traducción sin reescribir el motor documental.
- No enviar documentos a servicios externos sin que esa dependencia sea explícita y configurable.

## Roadmap

Consultar [`docs/roadmap.md`](docs/roadmap.md).

## Estado

- **Fase 0 — Definición e inicialización (Completada).**
- **Fase 1 — Análisis de PDF (Completada):** motor de análisis documental (`DocumentAnalyzer`), modelos de dominio desacoplados (`Document`, `Page`, `TextBlock`, `TextLine`, `TextSpan`, `ImageElement`, `BoundingBox`), endpoint HTTP `POST /api/v1/documents/analyze` y serialización canónica JSON.
- **Fase 2 — Traducción desacoplada (Completada):** interfaz abstracta `Translator`, servicio `TranslationEngine`, protección estricta de tokens/términos (`protection.py`), proveedor `MockTranslator` determinista y adaptador real HTTP OpenAI-compatible con `httpx`.
- **Fase 2.5 — Tradux Web Workbench (Completada):** interfaz web desktop-first ligera y editorial (`GET /`) servida con FastAPI + Jinja2 + CSS propio + vanilla JS; previsualización local del PDF en navegador, extracción y análisis documental mediante el endpoint real `POST /api/v1/documents/analyze`, métricas estructurales del `DocumentModel`, controles de idiomas y términos protegidos, vista de demostración del pipeline mediante `POST /api/v1/workbench/translate` (forzando `MockTranslator` offline y sin coste), comparativa de bloques fuente ↔ traducción.
- **Fase 3 — Motor de layout y reconstrucción de PDF (Completada):** motor de decisiones geométricas y reflow (`LayoutEngine`), medición ultrarrápida no destructiva (`TextMeasurer`), resolución determinista de tipografías a Base-14 (`app.layout.fonts`), selección de estilo representativo por ponderación de caracteres, renderizador PyMuPDF de alta fidelidad (`PyMuPDFRenderer`), preservación de vectores de fondo, imágenes y rotación de página, política de seguridad ante desbordamiento (`REVIEW_REQUIRED` sin mutilar texto original), script CLI `scripts/render_translated_document.py` y descarga de demostración interactiva en Web Workbench (`POST /api/v1/workbench/render`).
- **Fase 4 — Aplicación MVP (Completada):** orquestación end-to-end de trabajos de traducción documental (`DocumentAnalyzer` → `TranslationEngine` → `LayoutEngine` → `PyMuPDFRenderer`), modelo de trabajos y gestor efímero en memoria (`JobStore`) con control de capacidad y TTL, API pública de trabajos (`/api/v1/jobs`), endpoint seguro de capacidades (`/api/v1/capabilities`), soporte dual para modo demostración (`MockTranslator` determinista) y proveedor configurado en servidor (OpenAI), protección UX contra consumo accidental de tokens mediante modal explícito de confirmación, seguimiento visual reactivo por etapas y descarga directa del PDF traducido preservando bloques con desbordamiento.

Decisiones arquitectónicas:
- [`docs/decisions/0001-initial-stack.md`](docs/decisions/0001-initial-stack.md)
- [`docs/decisions/0002-document-model-and-analyzer.md`](docs/decisions/0002-document-model-and-analyzer.md)
- [`docs/decisions/0003-translation-engine-and-provider-abstraction.md`](docs/decisions/0003-translation-engine-and-provider-abstraction.md)
- [`docs/decisions/0004-layout-engine-and-pdf-reconstruction.md`](docs/decisions/0004-layout-engine-and-pdf-reconstruction.md)
- [`docs/decisions/0005-mvp-job-orchestration.md`](docs/decisions/0005-mvp-job-orchestration.md)

## Guía de ejecución (Windows / PowerShell)

### 1. Requisitos previos

- Python 3.12+ (o gestor `uv`)
- PowerShell 5.1 o PowerShell 7+
- Git
- Docker (opcional, para ejecución contenerizada)

### 2. Crear y activar el entorno virtual

Desde la raíz del repositorio en PowerShell:

```powershell
# Con Python estándar
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# O alternativamente con uv (recomendado por velocidad)
uv venv --python 3.12
.\.venv\Scripts\Activate.ps1
```

### 3. Instalar dependencias

Instala el paquete en modo editable con las dependencias de desarrollo:

```powershell
# Con pip
python -m pip install --upgrade pip
pip install -e ".[dev]"

# O con uv
uv pip install -e ".[dev]"
```

### 4. Configurar variables de entorno

Copia el archivo de ejemplo:

```powershell
Copy-Item .env.example .env
```

### 5. Iniciar el servidor de desarrollo

Ejecuta FastAPI usando Uvicorn:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Para verificar que el servicio está activo:

```powershell
# En PowerShell:
Invoke-RestMethod -Uri http://localhost:8000/health
```

Respuesta esperada (HTTP 200):
```json
{
  "status": "ok",
  "app": "Tradux",
  "version": "0.1.0",
  "environment": "development"
}
```

Documentación interactiva disponible en:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Redoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### 6. Usar el Tradux Web Workbench (Mesa de traducción documental)

Abre en tu navegador la raíz del servidor local:
- **Web Workbench:** [http://localhost:8000/](http://localhost:8000/)

Flujo de trabajo en la interfaz MVP:
1. **Seleccionar documento:** arrastra o selecciona un archivo PDF digital. El navegador lo previsualizará de inmediato mediante un Object URL local, sin subirlo innecesariamente.
2. **Analizar documento:** pulsa el botón *Analizar documento* para invocar el endpoint real `POST /api/v1/documents/analyze`. La interfaz mostrará métricas estructurales (páginas, bloques, líneas, spans, imágenes, fuentes únicas y dimensiones).
3. **Configurar traducción:** selecciona idioma de origen (o detección automática), idioma de destino y añade términos protegidos como etiquetas interactivas.
4. **Seleccionar modo de ejecución:**
   - **Modo de demostración (`demo`):** utiliza `MockTranslator`, garantizando determinismo, coste cero y ejecución 100% offline.
   - **Proveedor configurado en servidor (`configured`):** utiliza la clave y proveedor configurados en el servidor (ej. OpenAI). Si no hay credenciales configuradas, la opción permanece deshabilitada con un mensaje informativo.
5. **Iniciar trabajo de traducción:** pulsa *Iniciar trabajo de traducción*. Si se seleccionó un proveedor real, se abrirá un modal de confirmación con el resumen de páginas, bloques y aviso de consumo para evitar gastos accidentales.
6. **Seguimiento reactivo de etapas:** la tarjeta de estado monitorea en vivo las etapas (`analizando` → `traduciendo` → `layout` → `reconstruyendo` → `completado`).
7. **Descargar resultado:** al finalizar, pulsa *Descargar PDF traducido 📥* para obtener el documento reconstruido. Si existen bloques con desbordamiento (`review_required`), una alerta destacará que dichos bloques conservaron su texto original para evitar pérdidas de contenido.

### 7. API REST de Tradux

#### Capacidades del servidor (`GET /api/v1/capabilities`)

Consulta de forma segura los modos y proveedores disponibles sin exponer credenciales:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/capabilities"
```

#### Ciclo de vida de trabajos (`/api/v1/jobs`)

**Crear un trabajo de traducción (`POST /api/v1/jobs`):**

```powershell
$form = @{
    file = Get-Item -Path "ruta\al\documento.pdf"
    target_language = "es"
    source_language = "en"
    mode = "demo" # O "configured" si el servidor tiene credenciales activas
    protected_terms = "Tradux,PyMuPDF"
}
$job = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/jobs" -Method Post -Form $form
$jobId = $job.job_id
```

**Consultar estado del trabajo (`GET /api/v1/jobs/{job_id}`):**

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/jobs/$jobId"
```

**Descargar el PDF traducido (`GET /api/v1/jobs/{job_id}/result`):**

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/jobs/$jobId/result" -OutFile "salida_traducida.pdf"
```

**Eliminar trabajo y liberar memoria (`DELETE /api/v1/jobs/{job_id}`):**

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/jobs/$jobId" -Method Delete
```

#### Análisis documental directo (`POST /api/v1/documents/analyze`)

```powershell
# En PowerShell:
$form = @{
    file = Get-Item -Path "ruta\al\documento.pdf"
}
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/documents/analyze" -Method Post -Form $form
```

O mediante `curl`:

```bash
curl -X POST "http://localhost:8000/api/v1/documents/analyze" \
  -F "file=@ruta/al/documento.pdf"
```

#### Vía script CLI

Para analizar cualquier PDF local (incluyendo el benchmark manual MICRON si existe fuera del repo) y generar un JSON de inspección:

```powershell
python scripts/analyze_document.py ruta/a/documento.pdf [--output output/analisis.json]
```

Para traducir el modelo de documento analizado (o directamente un PDF) usando el motor desacoplado:

```powershell
# Usando proveedor mock determinista (offline por defecto):
python scripts/translate_document.py output/analisis.json --target es --provider mock --output output/traducido.json

# O usando el adaptador HTTP real (requiere TRANSLATION_API_KEY en entorno):
python scripts/translate_document.py output/analisis.json --target es --provider openai --output output/traducido.json
```

Para reconstruir el PDF traducido aplicando el motor de layout y PyMuPDF:

```powershell
# Reconstruir PDF traducido y opcionalmente guardar informe de layout:
python scripts/render_translated_document.py ruta/a/original.pdf output/traducido.json --output output/reconstruido.pdf [--layout-report output/layout_report.json]
```

#### Ejemplo resumido del JSON producido

```json
{
  "filename": "documento.pdf",
  "page_count": 2,
  "metadata": {
    "title": "Manual de Referencia"
  },
  "pages": [
    {
      "page_number": 1,
      "width": 595.0,
      "height": 842.0,
      "rotation": 0,
      "blocks": [
        {
          "text": "Título del documento",
          "translated_text": "[ES] Título del documento",
          "bbox": { "x0": 72.0, "y0": 60.5, "x1": 328.0, "y1": 85.0 },
          "lines": [
            {
              "text": "Título del documento",
              "bbox": { "x0": 72.0, "y0": 60.5, "x1": 328.0, "y1": 85.0 },
              "spans": [
                {
                  "text": "Título del documento",
                  "bbox": { "x0": 72.0, "y0": 60.5, "x1": 328.0, "y1": 85.0 },
                  "font_name": "Helvetica",
                  "font_size": 18.0,
                  "color": "#000000",
                  "flags": 0,
                  "origin": [72.0, 80.0]
                }
              ]
            }
          ],
          "reading_order": 0,
          "block_type": "text"
        }
      ],
      "images": [
        {
          "image_id": "p001-img001",
          "bbox": { "x0": 400.0, "y0": 80.0, "x1": 460.0, "y1": 140.0 },
          "width": 20,
          "height": 20,
          "xref": 5,
          "format": "png"
        }
      ]
    }
  ]
}
```

### 7. Ejecutar pruebas unitarias

```powershell
pytest
```

### 8. Ejecutar linter y formateo

```powershell
# Verificar código con Ruff
ruff check .

# Aplicar correcciones automáticas seguras
ruff check --fix .

# Verificar formato
ruff format --check .
```

### 9. Ejecución con Docker

Construir y levantar el contenedor (por defecto expuesto en el puerto host **8008** para evitar colisiones):

```powershell
# Usando Docker Compose
docker compose up --build -d

# O con Docker CLI directo
docker build -t tradux:0.1.0 .
docker run -d --name tradux-api -p 8008:8000 tradux:0.1.0
```

Verificar estado:

```powershell
Invoke-RestMethod -Uri http://localhost:8008/health
```

Detener el contenedor:

```powershell
docker compose down
# O si se ejecutó con Docker directo:
# docker stop tradux-api; docker rm tradux-api
```
