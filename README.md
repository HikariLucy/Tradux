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

**Fase 0 — Definición e inicialización.**

El siguiente paso es levantar el esqueleto del proyecto y construir un analizador capaz de convertir un PDF en un modelo interno de páginas, bloques, coordenadas, estilos e imágenes.