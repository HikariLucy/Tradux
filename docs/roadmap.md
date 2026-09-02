# Roadmap de Tradux

## Fase 0 — Definición e inicialización

Objetivo: dejar el proyecto reproducible y con alcance claro.

- documentación base;
- arquitectura inicial;
- flujo de Git;
- entorno Python;
- linting y tests;
- Docker mínimo;
- fixture PDF pequeña para pruebas.

**Criterio de salida:** cualquier desarrollador puede clonar el repositorio, levantar el proyecto y ejecutar los tests.

## Fase 1 — Análisis de PDF

Objetivo: convertir un PDF digital en un modelo interno.

- lectura con PyMuPDF;
- páginas y dimensiones;
- extracción de bloques, líneas y spans;
- coordenadas;
- tipografías, tamaños y colores;
- inventario de imágenes;
- exportación opcional del modelo a JSON.

**Criterio de salida:** el analizador reconstruye de manera consistente la estructura textual de los PDFs de prueba.

## Fase 2 — Traducción desacoplada

Objetivo: traducir el contenido sin introducir dependencias del proveedor en el dominio documental.

- interfaz `Translator`;
- proveedor mock para tests;
- primer proveedor real configurable por variables de entorno;
- detección de idioma;
- idiomas origen/destino;
- preservación de números, códigos y términos protegidos;
- traducción por bloques con contexto básico.

**Criterio de salida:** un modelo documental puede recibir traducciones sin modificar el PDF todavía.

## Fase 3 — Reconstrucción y layout

Objetivo: producir el primer PDF traducido manteniendo la distribución original.

- sustitución de bloques;
- preservación de imágenes;
- cálculo de ajuste de texto;
- reflujo de líneas;
- reducción controlada de fuente;
- sustitución de fuentes cuando sea necesario;
- tratamiento inicial de encabezados, pies y tablas simples.

**Criterio de salida:** Tradux genera un PDF digital traducido y legible conservando el número y dimensiones de las páginas.

## Fase 4 — Aplicación MVP

Objetivo: permitir utilizar Tradux sin ejecutar comandos manuales.

- endpoint de carga;
- creación de trabajo;
- idioma origen automático/manual;
- idioma destino;
- progreso/estado;
- descarga del resultado;
- manejo de errores;
- interfaz web mínima.

**Criterio de salida:** flujo completo subir → traducir → descargar.

## Fase 5 — QA automático

Objetivo: detectar defectos antes de entregar un documento.

- overflow;
- bloques sin traducir;
- texto faltante;
- diferencias en número/tamaño de páginas;
- fuentes problemáticas;
- renderizado de páginas para comparación visual;
- reporte de QA por trabajo.

**Criterio de salida:** ningún trabajo se declara exitoso sin un reporte de validación.

## Fase 6 — Robustez y producción

- procesamiento en background;
- Redis/worker si es necesario;
- PostgreSQL para historial y trabajos;
- límites y cuotas;
- eliminación programada de temporales;
- observabilidad;
- seguridad de subida de archivos;
- CI/CD.

## Fase 7 — OCR

Para PDFs escaneados:

- clasificación digital/escaneado;
- OCR;
- detección de regiones;
- deskew/rotación;
- reconstrucción del texto traducido.

## Fase 8 — Contenido gráfico y otros formatos

- texto dentro de imágenes;
- diagramas e infografías;
- DOCX;
- PPTX;
- otros formatos según demanda.

## Benchmark principal

El manual técnico MICRON de 90 páginas será el caso de regresión funcional/visual inicial. No debe almacenarse en el repositorio público o compartido si existen dudas sobre derechos de distribución; para tests automatizados se utilizarán fixtures pequeñas creadas específicamente para Tradux.