# Arquitectura inicial de Tradux

## Objetivo arquitectónico

Separar el procesamiento documental en etapas independientes para poder mejorar traducción, maquetación y QA sin acoplar todo el sistema a una sola implementación.

```text
PDF
 ↓
DocumentAnalyzer
 ↓
DocumentModel
 ↓
TranslationEngine
 ↓
LayoutEngine
 ↓
PDFRenderer
 ↓
QualityAnalyzer
 ↓
PDF traducido + reporte QA
```

## 1. DocumentAnalyzer

Responsable de leer el PDF fuente y producir una representación estructurada del documento.

Datos mínimos por bloque:

- número de página;
- texto original;
- bounding box `(x0, y0, x1, y1)`;
- fuente;
- tamaño;
- color;
- alineación aproximada;
- información de línea/span cuando esté disponible;
- relación con imágenes y elementos gráficos cercanos.

El analizador no debe traducir ni modificar el PDF.

## 2. DocumentModel

Modelo intermedio independiente de PyMuPDF. Permite persistir y probar el análisis sin depender permanentemente del archivo original.

Entidades iniciales sugeridas:

```text
Document
 └── Page[]
      ├── TextBlock[]
      ├── ImageElement[]
      └── GraphicElement[]
```

Cada `TextBlock` deberá mantener tanto el contenido fuente como el traducido, además de la geometría y estilo necesarios para reconstrucción.

## 3. TranslationEngine

Interfaz desacoplada del proveedor real.

Responsabilidades:

- detectar idioma cuando se solicite;
- traducir bloques;
- conservar términos protegidos;
- respetar glosarios;
- devolver errores y métricas de uso de forma normalizada.

Interfaz conceptual:

```python
translate(text, source_language, target_language, context=None) -> TranslationResult
```

El proveedor no debe conocer detalles de PDF.

## 4. LayoutEngine

Determina cómo insertar la traducción dentro del espacio disponible.

Orden de ajuste propuesto:

1. mantener fuente y tamaño originales;
2. reflujo de líneas;
3. reducir ligeramente interlineado;
4. reducir tamaño de fuente dentro de límites configurables;
5. expandir la caja únicamente cuando exista espacio seguro;
6. marcar el bloque para revisión si no existe una solución legible.

No se debe reducir texto indefinidamente para evitar overflow.

## 5. PDFRenderer

Responsable de crear el PDF final.

En V0.1 se priorizará reutilizar cada página original como base y sustituir/reconstruir las regiones de texto necesarias, manteniendo imágenes y gráficos intactos cuando sea posible.

## 6. QualityAnalyzer

Validaciones iniciales:

- número de páginas original/final;
- dimensiones de página;
- bloques que no pudieron renderizarse;
- overflow;
- texto fuente posiblemente remanente;
- fuentes sustituidas;
- diferencias visuales anómalas;
- errores de traducción/proveedor.

Debe producir un reporte estructurado además del PDF final.

## Estructura de carpetas objetivo

```text
tradux/
├── app/
│   ├── api/
│   ├── domain/
│   ├── analyzers/
│   ├── translators/
│   ├── layout/
│   ├── renderers/
│   ├── quality/
│   └── services/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── docs/
├── prompts/
├── scripts/
├── samples/
├── pyproject.toml
├── Dockerfile
└── README.md
```

## Decisiones iniciales

### Python

Se utilizará Python por la madurez del ecosistema para PDF, OCR futuro, procesamiento de imágenes y APIs.

### PyMuPDF

Será la primera implementación del motor PDF por su capacidad para obtener coordenadas, spans, fuentes, imágenes y realizar inserciones sobre páginas existentes.

### FastAPI

Permitirá exponer el motor como servicio sin acoplar el procesamiento a una interfaz concreta.

### Traducción desacoplada

Tradux no tendrá un proveedor de IA codificado directamente en el dominio. Esto permitirá usar APIs comerciales, modelos locales o distintos proveedores según costo, privacidad y calidad.

## Requisitos no funcionales iniciales

- archivos temporales aislados por trabajo;
- nombres de archivo generados de forma segura;
- límites de tamaño y páginas configurables;
- eliminación configurable de documentos temporales;
- logs sin contenido sensible del documento por defecto;
- procesamiento reproducible;
- tests con PDFs pequeños versionables y sin material confidencial.