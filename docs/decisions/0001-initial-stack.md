# 1. Stack inicial y alcance del bootstrap

Fecha: 2026-09-02

## Estado

Aceptada

## Contexto

Tradux tiene como objetivo traducir documentos PDF preservando su maquetación original (posiciones, tipografía, imágenes, tablas y diagramas). El primer hito de referencia es un manual técnico de 90 páginas.

Para iniciar el proyecto (Fase 0 — Bootstrap), es fundamental establecer una base técnica ligera, reproducible y fácil de operar sin incurrir tempranamente en sobreingeniería ni dependencias de infraestructura pesadas.

## Decisión

Se define el siguiente stack inicial:

1. **Python 3.12+:**
   - Ecosistema maduro y líder en manipulación de PDFs, procesamiento numérico/geométrico y modelos de lenguaje/IA.
   - Excelente soporte multiplataforma (con foco en Windows/PowerShell para desarrollo local).

2. **FastAPI + Pydantic v2:**
   - Permite exponer el motor como API REST moderna, asíncrona, con tipado estricto, validación automática de datos y documentación OpenAPI integrada.
   - `pydantic-settings` para gestión centralizada y segura de configuración basada en variables de entorno.

3. **PyMuPDF (`pymupdf`):**
   - Motor de renderizado y análisis documental de alto rendimiento basado en MuPDF.
   - Permite extraer bloques de texto, coordenadas precisas (`bbox`), fuentes, tamaños, spans, imágenes e insertar contenido sobre páginas existentes.

4. **pytest y Ruff:**
   - `pytest` para pruebas automatizadas rápidas y sin dependencias de red.
   - `ruff` como linter y formateador unificado ultrarrápido compatible con estándares modernos de Python.

5. **Docker:**
   - Empaquetado en contenedor ligero con Python 3.12-slim para garantizar reproducibilidad entre entornos de desarrollo y despliegue.

## Por qué NO se incorporan servicios adicionales en esta fase

No se incorporan todavía los siguientes componentes:

- **PostgreSQL / Bases de datos relacionales:** En las primeras fases, los trabajos de traducción y análisis se probarán directamente en memoria y con sistema de archivos local para acelerar el desarrollo del motor de layout y extracción.
- **Redis y Celery / Workers asíncronos:** La cola de tareas distribuida agregaría complejidad innecesaria antes de tener estabilizado el procesamiento unitario de un PDF. Se añadirá en la Fase 6 (Robustez y producción) cuando se manejen múltiples trabajos concurrentes de larga duración.
- **OCR (Tesseract / PaddleOCR):** La Fase 1 y V0.1 se enfocan estrictamente en PDFs digitales con texto seleccionable.
- **Frontend React / SPA:** En las primeras fases la interacción se realiza vía API y scripts/tests automatizados. Un frontend prematuro desviaría el esfuerzo del núcleo documental.
- **Proveedores reales de IA / traducción comercial:** Se mantendrán desacoplados mediante interfaces en la Fase 2, evitando costos, tokens o acoplamiento a APIs externas durante el bootstrap.

## Consecuencias

- **Positivas:**
  - El proyecto arranca inmediatamente con mínima fricción (`uv` / `pip install`).
  - La suite de tests corre en milisegundos y offline.
  - La superficie de fallos es muy reducida y la arquitectura bajo `app/` queda preparada para crecer modularmente.

- **Negativas / Mitigaciones:**
  - Los trabajos largos bloquearían el servidor HTTP si se ejecutaran síncronamente en producción, lo cual es aceptable temporalmente en Fase 0 y será abordado en el roadmap.
