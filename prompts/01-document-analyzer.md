# Prompt 01 — Document Analyzer

Usa este prompt desde la raíz del repositorio en una rama nueva basada en `main`.

---

Estamos desarrollando **Tradux**, una aplicación para traducir documentos preservando al máximo su maquetación original.

Antes de modificar nada, lee completos:

- `README.md`
- `docs/architecture.md`
- `docs/roadmap.md`
- `docs/decisions/0001-initial-stack.md`
- `prompts/00-bootstrap.md`

## Objetivo de esta tarea

Implementar la **Fase 1 — Document Analyzer**.

Tradux debe poder recibir un **PDF digital** y convertirlo en un modelo interno estructurado, independiente de PyMuPDF, que preserve la información necesaria para futuras fases de traducción, reconstrucción de layout y QA.

Esta fase **NO traduce** y **NO modifica** el PDF fuente.

## Alcance obligatorio

### 1. Modelo de dominio

Crea modelos tipados y serializables para representar como mínimo:

- `Document`
- `Page`
- `TextBlock`
- `TextLine`
- `TextSpan`
- `ImageElement`
- una representación reutilizable de `BoundingBox`

El dominio no debe importar ni exponer objetos `pymupdf.Rect`, `pymupdf.Page`, `pymupdf.Document` ni otras clases del proveedor PDF.

Datos mínimos esperados:

### Document

- identificador lógico opcional o nombre de archivo fuente;
- número de páginas;
- metadata PDF útil cuando exista;
- lista ordenada de páginas.

### Page

- número de página con convención explícita y documentada;
- ancho y alto en puntos PDF;
- rotación cuando esté disponible;
- bloques de texto;
- imágenes.

### TextBlock

- texto completo del bloque;
- bounding box;
- líneas;
- orden de lectura original cuando pueda derivarse de PyMuPDF;
- tipo/clasificación básica si PyMuPDF la expone de forma confiable.

### TextLine

- texto reconstruido;
- bounding box;
- spans ordenados.

### TextSpan

- texto;
- bounding box;
- nombre de fuente;
- tamaño de fuente;
- color normalizado en una representación estable;
- flags tipográficos de PyMuPDF conservados como dato primitivo si aportan valor;
- origen/baseline cuando esté disponible y pueda representarse sin acoplar el dominio a PyMuPDF.

### ImageElement

Como mínimo:

- referencia estable dentro del análisis;
- bounding box o posiciones conocidas cuando puedan obtenerse;
- ancho/alto nativos cuando estén disponibles;
- xref u otro identificador PDF solo como metadata primitiva, sin convertirlo en dependencia del dominio;
- formato/extensión si PyMuPDF la informa de forma confiable.

No es obligatorio extraer ni guardar los bytes de las imágenes en esta fase.

## 2. Implementación del analizador

Implementa un `DocumentAnalyzer` concreto basado en PyMuPDF dentro de `app/analyzers/`.

Debe poder analizar al menos:

- un path local seguro;
- idealmente bytes o stream en memoria si se puede hacer sin complicar innecesariamente la API interna.

Prioriza `page.get_text("dict")` o una representación equivalente de PyMuPDF que preserve bloques, líneas y spans.

No conviertas el diccionario crudo de PyMuPDF directamente en la API pública del dominio. Debe existir una capa explícita de mapeo.

## 3. Colores

Define una normalización estable para colores de texto.

Preferencia inicial:

- conservar valor RGB como tupla/lista de enteros `0..255`, o
- hexadecimal `#RRGGBB`.

Elige una sola representación canónica, documenta la decisión y prueba al menos negro y un color no negro.

## 4. Bounding boxes

Todas las geometrías deben usar la misma convención:

```text
(x0, y0, x1, y1)
```

en puntos PDF.

El modelo debe permitir validaciones básicas, por ejemplo que `x1 >= x0` y `y1 >= y0`.

No redondees agresivamente las coordenadas. Conserva suficiente precisión para reconstrucción posterior.

## 5. Fixture PDF propio y versionable

Crea una fixture pequeña bajo `tests/fixtures/` generada específicamente para Tradux, sin material con restricciones de distribución.

Debe contener al menos:

- 2 páginas;
- tamaños de texto distintos;
- al menos dos fuentes/estilos si PyMuPDF lo permite sin agregar fuentes externas al repo;
- texto negro y texto de otro color;
- varios bloques o líneas en posiciones distintas;
- al menos una imagen simple generada para la prueba, si puede hacerse sin incorporar dependencias pesadas.

La fixture puede generarse programáticamente durante tests o mediante un script reproducible. Evita archivos binarios opacos innecesarios si el mismo resultado puede generarse en memoria.

## 6. Serialización JSON

Los modelos deben poder serializarse de forma determinista a JSON mediante Pydantic.

Implementa una forma simple de exportar el análisis a JSON para debugging/desarrollo.

No es necesario agregar persistencia en base de datos.

## 7. API HTTP de desarrollo

Agrega un endpoint mínimo **solo si puede hacerse de forma limpia y segura** para analizar un PDF enviado al servicio.

Si se implementa, sugerencia:

```http
POST /api/v1/documents/analyze
Content-Type: multipart/form-data
```

Debe:

- aceptar solo PDF;
- respetar `MAX_UPLOAD_SIZE_MB`;
- no confiar en el nombre original para rutas locales;
- procesar mediante archivo temporal aislado o bytes en memoria;
- eliminar temporales al terminar;
- devolver el modelo estructurado en JSON.

Si agregar multipart obliga a introducir una dependencia adicional, justifícala (`python-multipart` es aceptable si realmente se implementa este endpoint).

El endpoint no debe ser el centro del diseño: el analizador debe poder probarse directamente sin FastAPI.

## 8. Errores

Define errores internos claros para al menos:

- archivo inexistente;
- archivo que no es PDF o PDF inválido;
- PDF protegido/cifrado que no puede abrirse sin contraseña;
- archivo vacío cuando aplique.

No expongas trazas internas completas en respuestas HTTP.

## 9. Tests obligatorios

Agrega tests unitarios/integración suficientes para comprobar:

1. análisis de PDF válido;
2. número de páginas;
3. dimensiones de página;
4. extracción de bloques;
5. líneas y spans;
6. texto completo esperado;
7. fuente/tamaño;
8. color;
9. bounding boxes válidos;
10. inventario de imágenes cuando exista;
11. serialización JSON y deserialización sin perder información relevante;
12. PDF inválido;
13. archivo inexistente;
14. endpoint HTTP, si se implementa;
15. que el analizador **no modifica** el archivo PDF original.

Los tests deben funcionar sin Internet y no deben utilizar el manual MICRON como fixture versionada.

## 10. Benchmark MICRON

El manual MICRON de 90 páginas es nuestro benchmark real de desarrollo, pero no debe copiarse al repositorio.

Si existe localmente fuera del control de versiones, puedes documentar un comando/script manual para analizarlo y generar un JSON local ignorado por Git.

No hagas que los tests dependan de que dicho manual esté presente.

## 11. Diseño y límites de esta fase

No implementes todavía:

- traducción;
- detección de idioma;
- proveedores de IA;
- OCR;
- modificación o redacción del PDF;
- reconstrucción de layout;
- sustitución de fuentes;
- comparación visual;
- Redis;
- PostgreSQL;
- workers;
- autenticación;
- frontend.

Evita sobrearquitectura. La prioridad es obtener un **DocumentModel correcto y estable**.

## 12. Documentación

Actualiza documentación solo cuando sea necesario para reflejar el comportamiento real.

Crea un ADR breve si durante la implementación se toma una decisión estructural importante, por ejemplo la representación del modelo documental o el criterio de extracción de PyMuPDF.

Documenta un ejemplo pequeño del JSON resultante, sin volcar documentos enteros al README.

## Reglas de trabajo

- Trabaja en una rama nueva, sugerida: `feat/document-analyzer`.
- No trabajes directamente en `main`.
- No hagas merge.
- No hagas push sin autorización.
- No hagas commit al terminar salvo que el usuario lo autorice.
- No agregues dependencias sin justificar su uso.
- Mantén Python 3.12 como baseline.
- Código tipado y módulos pequeños.
- No registres en logs el contenido completo de documentos por defecto.
- No guardes PDFs reales/confidenciales en Git.
- Si una ambigüedad menor existe, elige la opción más simple, documéntala y continúa.

## Validaciones antes de terminar

Ejecuta realmente:

```powershell
.venv\Scripts\pytest.exe
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
git diff --check
git status --short
git branch --show-current
```

Si se modifica Docker o una dependencia runtime, reconstruye además la imagen y valida `/health`.

## Criterio de salida de Fase 1

La fase se considera completada cuando un PDF digital de prueba puede transformarse consistentemente en un modelo `Document` independiente de PyMuPDF que conserva:

- páginas;
- dimensiones;
- bloques;
- líneas;
- spans;
- texto;
- geometría;
- tipografía;
- tamaños;
- colores;
- inventario de imágenes;

y el modelo puede serializarse a JSON y recuperarse sin pérdida estructural relevante.

## Entregable

Al finalizar informa:

1. resumen de lo implementado;
2. árbol de archivos creados/modificados;
3. modelo de dominio resultante;
4. decisiones técnicas y ADR creados;
5. dependencias agregadas y motivo;
6. comandos de validación y resultados;
7. número y resultado de tests;
8. ejemplo resumido de JSON producido;
9. limitaciones conocidas;
10. `git status --short`;
11. propuesta de mensaje de commit convencional.

No hagas merge ni push automáticamente.

---
