# Prompt 03 — Layout Engine y reconstrucción de PDF

Usa este prompt desde la raíz del repositorio en una rama nueva basada en `main`.

---

Estamos desarrollando **Tradux**, una aplicación para traducir documentos preservando al máximo su maquetación original.

Las Fases 0, 1, 2 y 2.5 ya están completadas. Tradux dispone actualmente de:

- aplicación FastAPI reproducible;
- `DocumentAnalyzer` para PDFs digitales;
- `DocumentModel` tipado e independiente de PyMuPDF;
- geometría canónica no rotada para páginas y elementos;
- `TranslationEngine` desacoplado con `text` + `translated_text` por bloque;
- `MockTranslator` determinista y adaptador OpenAI-compatible configurable;
- protección de números, códigos, URLs, términos y placeholders;
- Web Workbench para cargar, analizar e inspeccionar PDFs;
- benchmark manual MICRON de 90 páginas usado solo localmente.

Antes de modificar nada, lee completos:

- `README.md`
- `docs/architecture.md`
- `docs/roadmap.md`
- `docs/decisions/0001-initial-stack.md`
- `docs/decisions/0002-document-model-and-analyzer.md`
- `docs/decisions/0003-translation-engine-and-provider-abstraction.md`
- `prompts/00-bootstrap.md`
- `prompts/01-document-analyzer.md`
- `prompts/02-translation-engine.md`
- `prompts/02-5-web-workbench.md`

## Objetivo de esta tarea

Implementar la **Fase 3 — Layout Engine + PDF Renderer / Reconstruction**.

El objetivo es que Tradux pueda recibir:

1. el PDF digital fuente;
2. el `Document` analizado correspondiente;
3. traducciones presentes en `TextBlock.translated_text`;

y producir un **nuevo PDF digital** conservando el número y dimensiones de páginas, imágenes y gráficos del original, mientras sustituye visualmente el texto fuente por el texto traducido dentro de la geometría disponible.

Esta es la primera fase en que Tradux modifica/genera un PDF.

La prioridad no es lograr perfección tipográfica universal. La prioridad es construir una base **correcta, medible, segura y extensible** que funcione bien con PDFs digitales razonables y permita detectar explícitamente cuándo un bloque no puede reconstruirse de forma legible.

## Principios obligatorios

1. **No modificar jamás el archivo fuente.** Trabaja siempre sobre una copia en memoria o una nueva instancia del PDF.
2. `Document.text` conserva el contenido fuente; `translated_text` sigue siendo la traducción.
3. La geometría canónica del `DocumentModel` sigue siendo el espacio **no rotado** definido en ADR 0002.
4. No mezclar coordenadas visuales rotadas con coordenadas del modelo.
5. El `LayoutEngine` decide cómo cabe el texto; el `PDFRenderer` ejecuta el plan sobre el PDF. No mezclar ambas responsabilidades en una única función gigante.
6. No reducir la fuente indefinidamente para forzar un texto dentro de una caja.
7. Si un bloque no puede resolverse de forma legible, debe quedar explícitamente marcado como `review_required` / `overflow`, no ocultarse el problema.
8. No borrar, rasterizar ni degradar imágenes o gráficos para facilitar la traducción.
9. Tests 100% offline. No realizar llamadas reales a proveedores de traducción.
10. No registrar texto completo de documentos en logs o excepciones.

---

# 1. Antes de implementar: probes obligatorios de PyMuPDF

Antes de elegir la estrategia final de reconstrucción, ejecuta pequeños experimentos reproducibles con la versión de PyMuPDF instalada y documenta los resultados.

Como mínimo comprueba:

### A. Redacción de solo texto

Crea una página sintética que tenga:

- un rectángulo vectorial de fondo de color;
- texto sobre ese fondo;
- una imagen cercana o parcialmente solapada;
- otro texto fuera de la región.

Prueba la API real de redactions de la versión instalada y determina qué combinación explícita de parámetros permite:

- eliminar el texto fuente de una región;
- **no eliminar ni rasterizar imágenes**;
- **no eliminar gráficos/vectoriales**;
- conservar el fondo existente cuando sea posible;
- evitar rellenar la región de blanco por defecto si eso destruiría fondos coloreados.

No asumas valores de flags de memoria: inspecciona la API/constantes instaladas y valida mediante tests.

### B. Inserción y overflow

Comprueba el comportamiento real y valor de retorno de `Page.insert_textbox()` (o API equivalente elegida) cuando:

- el texto cabe;
- el texto no cabe;
- el rectángulo tiene poco alto;
- se usa una fuente estándar de PyMuPDF.

### C. Página rotada

Crea una página 400×600 con `rotation=90`, texto e imagen. Verifica que:

- las coordenadas del `DocumentModel` se puedan usar de forma coherente para retirar e insertar texto;
- la salida preserve la rotación;
- no se intercambien accidentalmente `width` y `height`.

### D. Preservación visual básica

Reanaliza el PDF reconstruido y comprueba que imágenes, número de páginas, dimensiones y rotaciones sigan presentes.

Documenta las conclusiones del probe en el ADR de esta fase. Los scripts de prueba ad-hoc no necesitan permanecer en el repositorio si los comportamientos quedan cubiertos por tests automatizados.

---

# 2. Modelos de layout independientes

Crea modelos tipados bajo `app/layout/`, por ejemplo `app/layout/models.py`.

El diseño exacto puede variar, pero debe existir una representación explícita del resultado del cálculo de layout antes de modificar el PDF.

Como mínimo considera:

## `LayoutStatus`

Estados explícitos, por ejemplo:

- `fit`;
- `shrunk`;
- `expanded` si se implementa expansión segura;
- `review_required`;
- `skipped`.

Usa `Enum`/`Literal` tipado, no strings dispersos.

## `BlockLayout`

Debe contener al menos:

- `page_number`;
- `reading_order`;
- `bbox` original;
- `render_bbox` final;
- texto que se intentará renderizar;
- fuente original solicitada / familia original si está disponible;
- fuente resuelta para renderizado;
- tamaño original representativo;
- tamaño final;
- color final;
- line-height/interlineado usado si aplica;
- líneas calculadas o metadata suficiente para reproducir el ajuste;
- `status`;
- `warnings: list[str]` o equivalente;
- indicador de sustitución de fuente.

## `PageLayout`

- `page_number`;
- layouts de bloques en orden determinista.

## `DocumentLayout`

- páginas;
- conteos/estadísticas primitivas útiles: bloques procesados, fit, shrunk, review_required, skipped;
- serializable a JSON.

Estos modelos no deben exponer objetos `pymupdf.Rect`, `pymupdf.Font`, `Page` ni otras clases del proveedor PDF.

---

# 3. Selección del estilo representativo del bloque

`TextBlock` puede contener múltiples líneas y spans con estilos diferentes. En V0.1 el renderer trabajará principalmente a nivel de bloque.

Selecciona un estilo representativo de forma **determinista**.

Estrategia recomendada:

- considerar spans con texto no vacío;
- elegir el estilo dominante por cantidad de caracteres o una regla igualmente determinista y documentada;
- conservar color y tamaño representativos;
- detectar `bold` / `italic` de forma básica mediante nombre de fuente y/o flags cuando sea fiable.

No intentes reconstruir todavía estilos mezclados carácter por carácter.

Documenta como limitación que un bloque con múltiples estilos puede ser homogeneizado en V0.1.

---

# 4. Resolución de fuentes

El nombre de fuente extraído del PDF (por ejemplo `DINPro-Bold`, `MyriadPro-Regular`) no implica que PyMuPDF pueda reutilizar directamente esa fuente para insertar nuevo texto.

Implementa una estrategia explícita de resolución de fuente.

Requisitos mínimos:

1. intentar clasificar familia y estilo de forma conservadora;
2. usar una fuente estándar segura de PyMuPDF como fallback cuando la fuente original no pueda reutilizarse;
3. conservar de forma razonable bold/italic cuando pueda inferirse;
4. registrar en `BlockLayout` cuándo ocurrió sustitución;
5. no descargar fuentes de Internet;
6. no incorporar archivos de fuentes propietarios al repositorio.

Una estrategia V0.1 aceptable es mapear a variantes estándar Helvetica / Times / Courier según familia y estilo.

Si descubres una forma fiable y simple de reutilizar una fuente embebida ya contenida en el PDF sin introducir complejidad peligrosa, puedes documentarla y aplicarla, pero **no es requisito** de esta fase.

---

# 5. Medición y reflow

Implementa un algoritmo determinista de ajuste de texto.

Debe respetar este orden conceptual:

1. mantener `render_bbox` igual al bbox original;
2. intentar tamaño de fuente original representativo;
3. hacer reflow de líneas;
4. reducir interlineado dentro de un margen pequeño y configurable si es necesario;
5. reducir gradualmente la fuente hasta un límite legible configurable;
6. opcionalmente expandir la caja solo cuando exista espacio demostrado como seguro;
7. si aun así no cabe, marcar `review_required` / overflow.

### Límites de legibilidad

Define configuración explícita, por ejemplo mediante un `LayoutConfig`:

- tamaño mínimo absoluto, por ejemplo 7 pt;
- escala mínima respecto al original, por ejemplo 0.70–0.75;
- factor mínimo de interlineado;
- tolerancia geométrica pequeña.

Elige valores razonables, documéntalos y hazlos configurables. No hardcodees números mágicos dispersos.

### Reflow

- conserva saltos de línea explícitos cuando tengan significado;
- realiza wrapping determinista por palabras para idiomas con separación por espacios;
- maneja tokens largos sin entrar en loops ni perder caracteres;
- no uses heurísticas lingüísticas complejas;
- documenta que CJK/word-breaking avanzado queda fuera de esta primera versión si no se resuelve de forma limpia.

### Medición

Puedes usar PyMuPDF internamente para medir texto, pero evita filtrar objetos PyMuPDF hacia los modelos de layout.

Si introduces un `TextMeasurer`/helper concreto, mantenlo pequeño y testeable. No sobrearquitectures.

---

# 6. Expansión segura de bbox

La expansión de cajas es **secundaria**. No debe ser la primera respuesta al overflow.

Si la implementas en esta fase:

- prioriza expansión vertical pequeña;
- no salir de los límites de página;
- no invadir otros `TextBlock`;
- no invadir `ImageElement`;
- usar geometría del mismo espacio canónico no rotado;
- registrar `status=expanded` y bbox final.

Si no puedes demostrar de forma robusta que la expansión es segura, es preferible marcar `review_required` a mover contenido de forma agresiva.

---

# 7. LayoutEngine

Implementa un servicio bajo `app/layout/`, por ejemplo:

```python
layout = LayoutEngine(config=...).build(document)
```

El `Document` de entrada debe ser el documento analizado/traducido.

Reglas:

- solo intentar layout de bloques cuyo `translated_text` sea no vacío;
- bloques sin traducción deben quedar `skipped` y no deben borrar el texto fuente del PDF;
- procesar páginas por `page_number` y bloques por `reading_order`;
- no mutar el `Document` de entrada;
- resultados deterministas;
- no abrir/modificar PDFs aquí si no es necesario;
- devolver `DocumentLayout` serializable.

El LayoutEngine no debe llamar a ningún traductor.

---

# 8. PDFRenderer

Implementa un renderer concreto bajo `app/renderers/`, por ejemplo `PyMuPDFRenderer`.

Interfaz conceptual:

```python
rendered_bytes = renderer.render(
    source_pdf=...,
    document=document,
    layout=layout,
)
```

Puede aceptar path/bytes mediante métodos separados si eso mantiene una API clara.

## Estrategia de página base

En V0.1 reutiliza el PDF original como base y modifica únicamente regiones textuales traducidas.

No reconstruyas la página completa desde cero si eso implica perder imágenes, gráficos, links o metadata sin necesidad.

## Orden crítico por página

Para evitar que una redacción posterior borre texto ya insertado:

1. determinar todas las regiones textuales que realmente serán reemplazadas;
2. aplicar todas las operaciones de eliminación/redacción del texto fuente de esa página;
3. ejecutar/aplicar las redacciones una sola vez con parámetros explícitos que preserven imágenes/gráficos según lo validado por los probes;
4. insertar después todos los textos traducidos según su `BlockLayout`.

No intercalar `redact -> insert -> redact -> insert` si una redacción posterior puede afectar contenido recién insertado.

## Texto fuente

Para bloques renderizados con éxito:

- el texto fuente no debe seguir visible;
- idealmente tampoco debe permanecer como texto seleccionable/buscable en esa región;
- la traducción debe ser seleccionable como texto digital.

## Color

Convierte el color canónico `#RRGGBB` del dominio a la representación esperada por PyMuPDF de forma determinista.

## Rotación

Conserva exactamente la rotación de cada página y respeta la convención geométrica de ADR 0002.

## Fallos

Si un `BlockLayout` está `review_required`, **no borres el texto fuente silenciosamente**. En V0.1 es preferible conservar el bloque original y reportar que requiere revisión antes que producir una región vacía.

Si una inserción que el LayoutEngine había clasificado como fit no cabe realmente según PyMuPDF, registra un error/revisión estructurada. No ignores el valor de retorno de la API de inserción.

---

# 9. Resultado de renderizado

Define un resultado tipado, por ejemplo `RenderResult`, con:

- bytes o referencia lógica al PDF generado;
- número de páginas;
- bloques renderizados;
- bloques omitidos;
- bloques con review requerida;
- sustituciones de fuente;
- warnings estructurados y seguros.

No incluyas texto documental completo en warnings/logs.

El PDF generado debe poder abrirse nuevamente con PyMuPDF.

---

# 10. Integridad del PDF fuente y salida

Agrega tests que demuestren:

1. hash del PDF fuente idéntico antes/después;
2. salida es un PDF válido;
3. mismo número de páginas;
4. mismas dimensiones por página;
5. mismas rotaciones;
6. imágenes siguen presentes con cantidad, dimensiones y bbox equivalentes cuando corresponda;
7. gráficos de fondo usados en fixtures permanecen;
8. texto de bloques no traducidos permanece;
9. texto fuente de bloques reemplazados desaparece de extracción/búsqueda cuando la API lo permite;
10. texto traducido aparece en extracción/búsqueda;
11. output puede ser reanalizado por `DocumentAnalyzer` sin error.

No exijas igualdad byte-a-byte entre dos PDFs generados: IDs internos y metadata pueden variar. La determinación debe comprobarse en el `DocumentLayout` y en invariantes estructurales.

---

# 11. Fixtures obligatorias

Extiende el generador de fixtures de forma programática. No agregues PDFs binarios opacos al repositorio.

Incluye al menos fixtures/casos para:

### A. Fit simple

Texto traducido de longitud similar que cabe con tamaño original.

### B. Expansión lingüística

Texto fuente corto y traducción notablemente más larga para forzar reflow y/o reducción controlada de tamaño.

### C. Overflow no resoluble

Caja deliberadamente demasiado pequeña para demostrar `review_required` sin reducir a tamaño absurdo.

### D. Fondo vectorial coloreado

Texto sobre un rectángulo de color. Tras sustituir texto, el fondo debe permanecer.

### E. Imagen cercana o parcialmente solapada

La redacción de texto no debe borrar ni rasterizar la imagen.

### F. Página rotada 90°

Misma geometría canónica antes/después y rotación preservada.

### G. Múltiples bloques

Verifica que aplicar redacciones de una página antes de insertar evita borrar traducciones ya creadas.

### H. Fuente no reutilizable

Simula/usa un nombre de fuente no estándar y verifica fallback + warning/sustitución.

---

# 12. Tests mínimos obligatorios

Añade cobertura suficiente para demostrar al menos:

1. modelos de layout serializables;
2. estilo representativo determinista;
3. conversión de color `#RRGGBB`;
4. resolución/fallback de fuente;
5. fit conservando tamaño original;
6. reflow determinista;
7. reducción controlada de fuente;
8. respeto al tamaño mínimo;
9. overflow -> `review_required`;
10. bloques sin `translated_text` -> `skipped`;
11. `Document` de entrada no mutado;
12. orden determinista por página + reading_order;
13. renderer no modifica fuente original;
14. PDF final válido;
15. page count/dimensiones/rotaciones preservadas;
16. imagen preservada;
17. gráfico/fondo coloreado preservado;
18. fuente sustituida reportada;
19. texto fuente reemplazado ya no aparece donde corresponde;
20. texto traducido sí aparece;
21. bloque `review_required` conserva texto original en PDF;
22. página rotada renderizada correctamente;
23. múltiples redacciones en una página no borran traducciones insertadas;
24. reanálisis del output mediante `DocumentAnalyzer`;
25. errores/logs no contienen texto completo del documento.

Todos los tests deben ser offline y reproducibles.

---

# 13. CLI de desarrollo

Agrega una utilidad local, por ejemplo:

```powershell
python scripts/render_translated_document.py `
  source.pdf `
  translated-model.json `
  --output output/tradux-rendered.pdf `
  --layout-report output/layout-report.json
```

Debe:

1. abrir el PDF fuente sin modificarlo;
2. cargar un `Document` traducido desde JSON;
3. construir layout;
4. renderizar el PDF;
5. escribir opcionalmente reporte JSON de layout;
6. imprimir solo métricas seguras, no contenido completo.

No requiera API keys ni llamadas de traducción.

---

# 14. Integración mínima con Web Workbench

Una vez que el renderer y sus tests estén verdes, integra **solo lo mínimo** para poder demostrar la Fase 3 desde la interfaz existente.

Objetivo: después de `Generar vista previa` con `MockTranslator`, permitir generar un PDF reconstruido de demostración y descargarlo.

Una opción simple es un endpoint multipart de desarrollo que reciba:

- PDF original;
- `Document` traducido serializado como JSON;

y devuelva el PDF reconstruido o una respuesta descargable.

Requisitos:

- seguir forzando el flujo local/mock del Workbench;
- no llamar a proveedor externo;
- no persistir el archivo permanentemente;
- respetar `MAX_UPLOAD_SIZE_MB`;
- nombres de descarga seguros;
- mantener mensajes claros: es una **reconstrucción de demostración**, no una traducción lingüística real;
- mostrar conteos `fit / shrunk / review_required` antes o junto con la descarga si resulta simple.

No conviertas esta integración en un sistema de jobs, historial o almacenamiento. Eso sigue fuera de alcance.

Si la integración web amenaza con comprometer la corrección del renderer, prioriza primero el motor + CLI y deja una explicación concreta; pero intenta completarla si el núcleo está sólido.

---

# 15. Benchmark MICRON local

El manual MICRON de 90 páginas puede usarse localmente, nunca versionarse.

No uses una API real para traducir las 90 páginas automáticamente durante esta fase.

Benchmark sugerido:

1. analizar MICRON con `DocumentAnalyzer`;
2. producir un `Document` con `translated_text` mediante `MockTranslator` o un conjunto pequeño de traducciones manuales/locales;
3. construir `DocumentLayout`;
4. renderizar inicialmente páginas 1–5 para inspección visual;
5. si es estable, renderizar las 90 páginas en modo mock;
6. medir:
   - bloques totales;
   - fit;
   - shrunk;
   - review_required;
   - font substitutions;
   - tiempo de layout;
   - tiempo de render;
   - tamaño PDF fuente/salida;
7. comprobar estructuralmente páginas, dimensiones, rotaciones e imágenes.

La validación visual del benchmark es manual y complementaria; no debe reemplazar fixtures automatizadas.

---

# 16. ADR y documentación

Crea:

`docs/decisions/0004-layout-engine-and-pdf-reconstruction.md`

Debe documentar al menos:

- separación LayoutEngine / PDFRenderer;
- convención de coordenadas;
- resultados de probes de redaction/insertion de PyMuPDF;
- estrategia para eliminar texto preservando imágenes/gráficos;
- algoritmo de fit/reflow/shrink;
- límites de legibilidad;
- estrategia de fuentes y sustitución;
- manejo de páginas rotadas;
- comportamiento frente a `review_required`;
- limitaciones conocidas de V0.1.

Actualiza README únicamente con funcionalidad realmente implementada.

---

# 17. Límites explícitos de Fase 3

No implementes todavía:

- OCR;
- traducción de texto dentro de imágenes;
- reconstrucción avanzada de gráficos vectoriales;
- edición manual tipo editor PDF;
- tipografía mixta exacta por span si requiere complejidad excesiva;
- CJK avanzado si requiere un motor de shaping adicional;
- comparación visual automática completa;
- QualityAnalyzer completo de Fase 5;
- PostgreSQL;
- Redis;
- workers;
- jobs persistentes;
- autenticación;
- pagos;
- historial de usuario;
- SDKs de proveedores de IA;
- llamadas reales de traducción durante tests.

Evita sobrearquitectura.

---

# 18. Reglas de trabajo

- Trabaja en rama nueva basada en `main`, sugerida: `feat/layout-reconstruction`.
- No trabajes directamente en `main`.
- No hagas merge.
- No hagas push sin autorización.
- No hagas commit al terminar salvo autorización.
- Python 3.12 baseline.
- Usa PyMuPDF ya presente; no agregues librerías PDF pesadas salvo necesidad demostrada.
- Mantén funciones/módulos pequeños y tipados.
- Tests offline.
- No versionar PDF MICRON ni outputs generados.
- No logs con texto documental completo.
- Si una API de PyMuPDF tiene comportamiento ambiguo, prueba primero con un probe reproducible y documenta el resultado.

---

# 19. Validaciones antes de terminar

Ejecuta realmente:

```powershell
.venv\Scripts\pytest.exe -v
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
git diff --check
git status --short
git branch --show-current
```

Ejecuta además:

- CLI de reconstrucción sobre fixture reproducible;
- apertura/reanálisis del PDF generado;
- Docker rebuild si cambian dependencias o archivos necesarios en runtime;
- `/health` y `/` si se modifica integración web;
- endpoint/download de reconstrucción si se implementa integración Workbench.

---

# 20. Criterio de salida de Fase 3

La fase se considera completada cuando Tradux puede tomar un PDF digital fuente y un `Document` con `translated_text` y generar un nuevo PDF donde:

- el archivo fuente permanece byte-a-byte intacto;
- el output abre correctamente;
- se conservan número de páginas, dimensiones y rotaciones;
- imágenes y gráficos principales permanecen;
- bloques traducidos aptos sustituyen visualmente el texto fuente;
- el texto traducido sigue siendo texto digital/seleccionable;
- se intenta mantener tipografía/tamaño y se aplica reflow/shrink solo dentro de límites legibles;
- sustituciones de fuente se reportan;
- bloques irresolubles se marcan `review_required` sin borrar silenciosamente el original;
- existe `DocumentLayout`/reporte estructurado serializable;
- el PDF resultante puede volver a analizarse con `DocumentAnalyzer`;
- todo el flujo se prueba offline con fixtures reproducibles.

---

# 21. Entregable final

Al finalizar informa:

1. resumen de implementación;
2. árbol de archivos creados/modificados;
3. resultados exactos de los probes PyMuPDF;
4. modelos y estados de layout;
5. algoritmo de fit/reflow/shrink y límites;
6. estrategia de resolución/sustitución de fuentes;
7. estrategia concreta de redaction/render;
8. comportamiento en páginas rotadas;
9. pruebas de preservación de imágenes/gráficos;
10. tests añadidos y resultado total;
11. comandos de validación y salidas;
12. resultado del CLI sobre fixture;
13. resultado del benchmark MICRON si se ejecutó;
14. integración Web Workbench si se implementó;
15. limitaciones conocidas;
16. `git status --short`;
17. propuesta de commit convencional.

No hagas commit, push ni merge automáticamente.

---
