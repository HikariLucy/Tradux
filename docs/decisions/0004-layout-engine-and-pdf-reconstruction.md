# 4. Motor de layout y reconstrucción de PDF con PyMuPDF

Fecha: 2026-09-04

## Estado

Aceptada

## Contexto

En la Fase 1 se implementó la extracción y representación estructurada del PDF digital (`DocumentAnalyzer`, `DocumentModel`). En la Fase 2 se incorporó el motor de traducción desacoplado (`TranslationEngine`, `Translator`), y en la Fase 2.5 se desarrolló el Web Workbench para inspección visual comparativa.

La Fase 3 requiere reconstruir el documento PDF traducido manteniendo la fidelidad visual, tipográfica y espacial del documento original sin generar solapamientos, conservando elementos vectoriales de fondo, imágenes y la orientación de páginas rotadas. Al sustituir texto fuente por traducciones (por ejemplo, de inglés o neerlandés a español), el volumen textual típicamente se expande entre un 15% y un 30%, lo que exige una estrategia rigurosa de medición y ajuste tipográfico (reflow/shrink).

## Decisiones tomadas

### 1. Separación estricta entre LayoutEngine y PDFRenderer

- **`LayoutEngine` (`app.layout`):** Es un componente puramente analítico y decisional. Recibe el `Document` con traducciones en los bloques, evalúa la geometría de cada bloque mediante simulaciones en memoria, y produce un `DocumentLayout` inmutable con `BlockLayout` que detalla el tamaño de fuente final, interlineado, caja delimitadora asignada y estado de ajuste (`FIT`, `SHRUNK`, `EXPANDED`, `REVIEW_REQUIRED`, `SKIPPED`). No realiza redacciones ni escribe bytes en el documento PDF.
- **`PyMuPDFRenderer` (`app.renderers`):** Implementa el protocolo abstracto `PDFRenderer`. Toma los bytes del PDF original y el `DocumentLayout`, ejecutando las operaciones gráficas y redacciones en PyMuPDF para producir el PDF final (`RenderResult`).
- El `Document` de entrada y el archivo PDF original nunca se modifican en el proceso.

### 2. Hallazgos empíricos y sondas previas con PyMuPDF

Antes de implementar la reconstrucción, se ejecutaron pruebas de validación con PyMuPDF 1.28.2 arrojando conclusiones determinantes:
1. **Peligro de redacción en imágenes:** Por defecto, `apply_redactions()` destruye píxeles de imágenes solapadas (`images=2`). Es imprescindible invocarla con parámetros explícitos: `images=pymupdf.PDF_REDACT_IMAGE_NONE (0)`, `graphics=pymupdf.PDF_REDACT_LINE_ART_NONE (0)` y `text=pymupdf.PDF_REDACT_TEXT_REMOVE (0)`.
2. **Preservación de fondos vectoriales:** El uso de `fill=None` al añadir la anotación (`page.add_redact_annot(rect, fill=None)`) elimina el texto subyacente sin estampar parches rectangulares blancos, preservando cajas de color y gráficos vectoriales intactos.
3. **Estrategia de redacción en dos fases por página:** No debe redactarse e insertarse bloque a bloque de manera intercalada, pues una redacción posterior sobre un bloque cercano podría solapar y borrar texto recién insertado. La reconstrucción debe acumular todas las anotaciones de redacción de la página, aplicar `page.apply_redactions()` en lote, y posteriormente insertar todos los textos traducidos.
4. **Medición no destructiva ultrarrápida:** El uso de `page.new_shape().insert_textbox()` sin invocar `shape.commit()` permite medir en memoria si un texto encaja en un rectángulo determinado en menos de 0.35 ms por bloque, reportando el espacio vertical restante o el déficit en puntos.
5. **Diferenciación crítica entre cropbox y page.rect en páginas rotadas:**
   - En una página con dimensiones canónicas 400 × 600 pt y `rotation = 90`:
     - `page.cropbox.width = 400.0`, `page.cropbox.height = 600.0` (espacio canónico no rotado del documento);
     - `page.rect.width = 600.0`, `page.rect.height = 400.0` (espacio visual rotado proyectado por PyMuPDF).
   - Por tanto, `page.rect` **NO** debe describirse como equivalente a `cropbox`, ni utilizarse sus dimensiones (`page.rect.width`/`height`) para validar o limitar bounding boxes del `DocumentModel`.
   - Los límites geométricos, márgenes y expansión vertical segura deben calcularse exclusivamente sobre `page.cropbox` o las propiedades canónicas `Document.Page.width`/`height`.
   - Las operaciones de PyMuPDF (`get_text`, `add_redact_annot`, `insert_textbox`) operan sobre el espacio de coordenadas canónico del `cropbox`, de modo que un bloque en $y = 450..520$ es plenamente válido dentro del alto canónico de 600 pt y la visualización final respeta la rotación declarada.

### 3. Cascada de ajuste y reflow tipográfico (`LayoutEngine`)

Para cada bloque de texto traducido, el motor de layout evalúa las siguientes estrategias en orden secuencial estricto:
1. **Ajuste en tamaño original:** Se prueba el tamaño de fuente representativo y el interlineado estándar (`default_line_height = 1.15`). Si encaja sin déficit, se marca como `FIT`.
2. **Reducción sutil de interlineado:** Se decrementa el factor de interlineado progresivamente hasta `min_line_height = 0.95`. Si encaja, se marca como `FIT`.
3. **Reducción de tamaño de fuente (Font Shrinking):** Se decrementa el tamaño en pasos de `font_size_step = 0.5 pt` hasta alcanzar el límite inferior de legibilidad (`min_font_scale = 0.75` respecto al original, con corte absoluto en `min_font_size = 7.0 pt`). Si encaja, se marca como `SHRUNK`.
4. **Expansión vertical segura (opcional):** Si `allow_safe_vertical_expansion = True` y el espacio inferior lo permite sin solapar bloques contiguos ni salirse de los márgenes de página, se expande la altura de la caja hasta un máximo de `max_vertical_expansion_ratio = 0.50`. Si encaja, se marca como `EXPANDED`.
5. **Política de seguridad ante desbordamiento:** Si ninguna de las opciones anteriores logra encajar el texto dentro de los límites de legibilidad, el bloque se marca como `REVIEW_REQUIRED`.

### 4. Protección estricta contra pérdida de contenido

- Si un bloque tiene estado `REVIEW_REQUIRED` (desbordamiento insalvable) o `SKIPPED` (bloque sin traducción), **el renderizador no redacta el bloque**.
- Se conserva intacto el texto original en la página en lugar de generar una caja vacía, texto truncado o mutilación silenciosa. El resultado registra advertencias detalladas en `RenderResult.warnings`.

### 5. Resolución y mapeo a fuentes Base-14

- Para garantizar portabilidad, renderizado consistente y evitar dependencias de archivos de tipografías externas en disco, se mapean las fuentes originales a la familia de fuentes estándar PDF Base-14 (`helv`, `hebo`, `heit`, `hebi`, `tiro`, `tibo`, `tiit`, `tibi`, `cour`, `cobo`, `coit`, `cobi`, `symb`, `zadb`).
- El módulo `app.layout.fonts` limpia prefijos de subset (ej. `ABCDEF+Helvetica`), detecta peso (`bold`, `heavy`, `black`) e inclinación (`italic`, `oblique`), resolviendo al identificador estándar Base-14 óptimo y registrando cualquier sustitución para trazabilidad.

### 6. Estilo representativo ponderado por caracteres

- Los bloques documentales extraídos contienen líneas y `TextSpan` con propiedades individuales.
- `app.layout.styles.select_representative_style` analiza la longitud de caracteres de cada span dentro del bloque y selecciona de forma determinista la fuente, tamaño de letra y color hexadecimal predominantes para renderizar el bloque completo traducido.

### 7. Integración en Web Workbench y CLI

- Se incorpora el script independiente `scripts/render_translated_document.py` para reconstrucción en lotes desde terminal, con opción de exportar el informe de layout en JSON.
- Se añade el endpoint `POST /api/v1/workbench/render` en FastAPI y un control de descarga en el Web Workbench, permitiendo a los operadores probar la reconstrucción visualmente en tiempo real tras la previsualización.

## Consecuencias

- **Positivas:**
  - El PDF resultante es visualmente fidedigno, vectorial, searchable y seleccionable.
  - Se eliminan por completo solapamientos destructivos sobre imágenes o fondos de color.
  - La suite de pruebas de reconstrucción corre de manera 100% offline y determinista con fixtures sintéticos.
- **Limitaciones conocidas:**
  - La reconstrucción actual opera a nivel de bloque consolidado con un estilo tipográfico representativo; estilos mixtos intra-bloque (ej. una sola palabra en negrita en medio de un párrafo) se homogenizan al estilo representativo del bloque.
  - No se realiza traducción ni renderizado de texto rasterizado dentro de imágenes (alcance de Fase 8).
  - La detección visual multi-página de solapamientos complejos será complementada y automatizada en la Fase 5 (QA Engine).
