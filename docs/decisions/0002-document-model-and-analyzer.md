# 2. Modelo de dominio documental desacoplado y analizador basado en PyMuPDF

Fecha: 2026-09-04

## Estado

Aceptada

## Contexto

La Fase 1 de Tradux (Document Analyzer) requiere transformar un PDF digital en un modelo interno estructurado, tipado y serializable que capture páginas, bloques de texto, líneas, spans, geometrías, fuentes, colores e inventario de imágenes.

Para evitar que el resto del sistema quede atado a PyMuPDF o a cualquier otro motor de renderizado PDF futuro, es imprescindible desacoplar estrictamente el dominio de las clases de terceros (`pymupdf.Rect`, `pymupdf.Page`, `pymupdf.Document`).

## Decisiones tomadas

### 1. Modelo de dominio agnóstico (`app/domain/models.py`)

- Se implementan modelos Pydantic v2 puros: `BoundingBox`, `TextSpan`, `TextLine`, `TextBlock`, `ImageElement`, `Page` y `Document`.
- El módulo de dominio no importa ni referencia clases de PyMuPDF.
- La consistencia entre `Document.page_count` y `Document.pages` es estricta: `page_count` se sincroniza automáticamente con `len(pages)` y valida que no existan discrepancias.
- La numeración de páginas (`Page.page_number`) es 1-indexada (`page_number >= 1`) para alinearse con la convención humana y documental.

### 2. Espacio de coordenadas canónico no rotado

- **Convención canónica:** Todas las geometrías del `DocumentModel` (`BoundingBox` de bloques, líneas, spans e imágenes) están expresadas en el **espacio de coordenadas NO ROTADO** de PyMuPDF:
  - Formato `(x0, y0, x1, y1)` en puntos PDF (1 punto = 1/72 de pulgada).
  - `(x0, y0)` representa la esquina superior izquierda en el espacio de la página no rotada (`page.cropbox`).
  - `(x1, y1)` representa la esquina inferior derecha.
  - Validación obligatoria: `x1 >= x0` e `y1 >= y0`. Las dimensiones `width` y `height` de cada `BoundingBox` se calculan como propiedades derivadas.
  - No se aplica redondeo destructivo sobre las coordenadas flotantes para garantizar fidelidad en la reconstrucción posterior.
- **Tratamiento de páginas rotadas:**
  - La documentación y comportamiento interno de PyMuPDF establece que métodos de extracción como `page.get_text()` y `page.get_image_info()` entregan coordenadas pertenecientes al espacio no rotado de la página.
  - Por tanto, para no mezclar dimensiones de espacios distintos, `Page.width` y `Page.height` representan las dimensiones del **mismo espacio no rotado** (`page.cropbox.width` y `page.cropbox.height`).
  - `Page.rotation` se conserva por separado como un entero primitivo (`0`, `90`, `180` o `270`).
  - En esta Fase 1 no se aplican matrices de transformación (`rotation_matrix`) a las coordenadas; cualquier transformación a espacio visual proyectado se realizará de forma explícita en fases posteriores cuando se requiera maquetación visual o renderizado.
  - Esto garantiza una única fuente de verdad geométrica coherente y auto-contenida.

### 3. Representación canónica de colores

- Se adopta la representación hexadecimal `#RRGGBB` en mayúsculas (por ejemplo, `#000000` para negro puro, `#FF0000` para rojo).
- PyMuPDF expone los colores de texto como enteros sRGB de 24 bits `(r << 16) + (g << 8) + b`. El analizador los convierte de forma determinista mediante `app.analyzers.color.normalize_color_to_hex()`.
- Esta representación es determinista, compacta, nativamente serializable en JSON y estándar en tecnologías web y de maquetación.

### 4. Reconstrucción fiel del texto sin heurísticas

- El texto original se preserva íntegramente de forma verbatim.
- Las líneas (`TextLine`) se reconstruyen concatenando los spans en su orden original exacto (`"".join(s.text for s in spans)`).
- Los bloques (`TextBlock`) se reconstruyen uniendo sus líneas con salto de línea (`"\n".join(l.text for l in lines)`).
- No se aplican sustituciones, recortes (`strip`) ni modificaciones heurísticas que alteren el contenido original.

### 5. Inventario e identificación determinista de imágenes

- Cada ocurrencia de una imagen en una página se modela como un `ImageElement` independiente con su propio `BoundingBox`.
- Si una misma imagen (mismo `xref`) se reutiliza múltiples veces en una página o documento, cada ubicación conserva su propio identificador y su geometría de colocación.
- Los identificadores son deterministas basados en página y secuencia de aparición: `p{page_number:03d}-img{index:03d}` (ej. `p001-img001`).
- Los campos `xref` y `format` son opcionales. Si un elemento de imagen carece de un `xref` válido (> 0), no se invoca `extract_image()`.

### 6. Serialización canónica

- Se utilizan los métodos estándar de Pydantic v2: `model_dump_json()` para serialización y `model_validate_json()` para deserialización determinista.
- Se proporcionan métodos de conveniencia triviales `to_json()` y `from_json()` en `Document` sin capas innecesarias.

### 7. Endpoint HTTP y validación de seguridad

- El endpoint `POST /api/v1/documents/analyze` procesa preferentemente en memoria vía `DocumentAnalyzer.analyze_bytes()`, evitando crear archivos temporales en disco si no son requeridos.
- Se impone el límite `MAX_UPLOAD_SIZE_MB` mediante lectura acotada por bloques (`chunked streaming`), evitando saturación de memoria.
- La validación del archivo se realiza con el parser real (PyMuPDF); la comprobación del tipo MIME y extensión es solo un filtro inicial.

## Consecuencias

- **Positivas:**
  - El modelo documental es 100% independiente de bibliotecas PDF externas.
  - La serialización a JSON es bidireccional y sin pérdida estructural.
  - El análisis es completamente determinista y reproducible.
  - El analizador garantiza inmutabilidad: el archivo o stream fuente nunca se modifica.
- **Limitaciones conocidas en esta fase:**
  - No se realiza OCR sobre imágenes o páginas escaneadas (previsto para Fase 7).
  - No se almacenan los bytes binarios de las imágenes en el modelo JSON (se extrae únicamente metadata e inventario geométrico).
