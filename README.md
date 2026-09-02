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

**Fase 0 — Definición e inicialización (Completada).**

El siguiente paso es la **Fase 1 — Análisis de PDF**, construyendo el analizador capaz de convertir un PDF en un modelo interno de páginas, bloques, coordenadas, estilos e imágenes.

Decisiones arquitectónicas iniciales documentadas en [`docs/decisions/0001-initial-stack.md`](docs/decisions/0001-initial-stack.md).

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

### 6. Ejecutar pruebas unitarias

```powershell
pytest
```

### 7. Ejecutar linter y formateo

```powershell
# Verificar código con Ruff
ruff check .

# Aplicar correcciones automáticas seguras
ruff check --fix .

# Verificar formato
ruff format --check .
```

### 8. Ejecución con Docker

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
