# Prompt 02 — Translation Engine desacoplado

Usa este prompt desde la raíz del repositorio en una rama nueva basada en `main`.

---

Estamos desarrollando **Tradux**, una aplicación para traducir documentos preservando al máximo su maquetación original.

Antes de modificar nada, lee completos:

- `README.md`
- `docs/architecture.md`
- `docs/roadmap.md`
- `docs/decisions/0001-initial-stack.md`
- `docs/decisions/0002-document-model-and-analyzer.md`
- `prompts/00-bootstrap.md`
- `prompts/01-document-analyzer.md`

## Objetivo de esta tarea

Implementar la **Fase 2 — Translation Engine desacoplado**.

Tradux ya puede transformar un PDF digital en un `Document` estructurado e independiente de PyMuPDF. En esta fase debe poder traducir el contenido textual de ese modelo **sin modificar todavía el PDF ni ejecutar lógica de layout**.

La arquitectura debe permitir cambiar el proveedor de traducción sin afectar el dominio documental ni el futuro `LayoutEngine`.

## Principios obligatorios

1. El proveedor de traducción no debe conocer PyMuPDF ni detalles del PDF.
2. El motor de traducción debe operar sobre el `DocumentModel` de Fase 1.
3. El documento fuente no debe mutarse silenciosamente; el flujo preferido es producir una copia profunda traducida.
4. La geometría, fuentes, colores, imágenes, rotación y orden estructural deben permanecer intactos durante la traducción.
5. Los tests deben funcionar 100% offline y no consumir APIs reales.
6. No registrar en logs contenido completo de documentos, API keys ni respuestas sensibles.

## 1. Extensión mínima del modelo documental

Extiende `TextBlock` de forma compatible para poder conservar ambos contenidos:

- `text`: texto fuente ya existente;
- `translated_text: str | None = None`: traducción resultante.

No renombres `text` ni rompas la serialización existente de Fase 1.

No guardes traducciones en `TextSpan` todavía. La unidad de traducción inicial será el bloque textual, porque ofrece más contexto lingüístico y evita acoplar traducción con decisiones futuras de reflow.

La estructura geométrica del bloque debe permanecer inalterada.

## 2. Modelos de traducción independientes

Crea modelos tipados, preferentemente bajo `app/translators/models.py`, para representar como mínimo:

### `TranslationRequest`

- `text: str`
- `source_language: str | None` — `None` significa detección automática cuando el proveedor la soporte;
- `target_language: str`
- `context: TranslationContext | None`
- `protected_terms: list[str]`

### `TranslationContext`

Contexto corto y opcional, por ejemplo:

- texto inmediatamente anterior;
- texto inmediatamente posterior;
- número de página / orden del bloque como metadata no lingüística.

El proveedor debe entender que el contexto es solo referencia y no forma parte del texto que debe devolver traducido.

### `TranslationResult`

Como mínimo:

- `translated_text: str`
- `detected_source_language: str | None`
- `provider: str`
- `model: str | None`
- métricas de uso opcionales como valores primitivos cuando el proveedor las informe de forma fiable.

No acoples estos modelos a un SDK externo.

## 3. Contrato `Translator`

Define una interfaz explícita mediante `Protocol` o ABC, por ejemplo conceptualmente:

```python
class Translator(Protocol):
    async def translate(self, request: TranslationRequest) -> TranslationResult:
        ...
```

El resto de Tradux debe depender de esta interfaz, nunca de un proveedor concreto.

## 4. Proveedor mock determinista

Implementa un `MockTranslator` para tests y desarrollo offline.

Requisitos:

- determinista;
- nunca usa Internet;
- permite comprobar el flujo completo;
- preserva placeholders protegidos exactamente;
- puede devolver una traducción sintética claramente reconocible, por ejemplo prefijando el idioma objetivo o usando un mapping configurable en tests.

No intentes simular calidad lingüística real.

## 5. Primer adaptador real configurable

Implementa un adaptador **OpenAI-compatible Chat Completions** mediante HTTP, aislado detrás de `Translator`.

Objetivo: tener un primer proveedor real configurable sin introducir su protocolo dentro del dominio.

Requisitos:

- no usar APIs reales durante tests;
- configuración solo por variables de entorno;
- `TRANSLATION_API_BASE_URL`;
- `TRANSLATION_API_KEY` como secreto;
- `TRANSLATION_MODEL`;
- timeout configurable;
- no hardcodear claves;
- no imprimir claves ni cuerpos completos en logs;
- errores HTTP, timeout, respuesta inválida y respuesta vacía deben convertirse en errores internos tipados de Tradux;
- el adaptador debe poder probarse con transporte HTTP simulado/mocking, sin Internet.

Si para implementar este adaptador se necesita `httpx` en runtime, muévelo/decláralo correctamente en `dependencies` sin duplicarlo innecesariamente en extras de desarrollo.

No agregues SDKs pesados de proveedores si `httpx` basta para esta fase.

### Detección automática de idioma

Cuando `source_language` sea `None`, el adaptador puede solicitar al modelo una respuesta estructurada mínima que incluya:

- idioma detectado;
- traducción.

El parseo debe ser estricto y fallar con un error tipado si la respuesta no cumple el contrato.

No inventes un detector heurístico frágil solo para evitar esta responsabilidad.

## 6. Protección de números, códigos y términos

Crea una capa independiente, por ejemplo `app/translators/protection.py`, que enmascare segmentos que Tradux debe conservar exactamente antes de enviar texto al proveedor y los restaure después.

Debe admitir al menos:

- `protected_terms` explícitos recibidos en la solicitud;
- URLs;
- emails;
- IPv4;
- direcciones MAC;
- identificadores/códigos técnicos razonablemente claros;
- valores numéricos que no deban alterarse.

Usa placeholders deterministas y reversibles, con detección de colisiones, por ejemplo una familia propia de tokens Tradux.

No sobreprotejas palabras normales ni intentes resolver semántica compleja mediante regex.

Después de recibir la traducción:

- todos los placeholders deben restaurarse;
- si falta, se duplica o se corrompe un placeholder, lanza un `TranslationIntegrityError` en vez de devolver una traducción potencialmente dañada.

Agrega tests para términos técnicos y valores repetidos.

## 7. Translation Engine sobre `Document`

Implementa un servicio, por ejemplo `TranslationEngine`, que reciba:

```python
await engine.translate_document(
    document,
    source_language=None,
    target_language="es",
    protected_terms=[...],
)
```

y devuelva un **nuevo `Document`** con `translated_text` completado en los bloques traducibles.

Requisitos:

- no mutar el objeto `Document` fuente;
- conservar exactamente páginas, dimensiones, rotación, bboxes, fuentes, colores, spans e imágenes;
- recorrer bloques en orden determinista de página + `reading_order`;
- saltar de forma limpia bloques cuyo texto sea vacío o solo whitespace;
- construir contexto básico con bloque anterior/siguiente de la misma página cuando exista;
- la salida debe seguir siendo serializable con Pydantic;
- `text` conserva siempre el texto fuente;
- `translated_text` contiene la traducción.

### Errores

Para V0.1 usa comportamiento **fail-fast**: si un proveedor falla o una protección de integridad falla, aborta la traducción del documento y devuelve un error interno claro con localización primitiva del bloque (`page_number`, `reading_order`) sin incluir el texto completo.

No implementes todavía reintentos distribuidos, colas ni persistencia de progreso.

## 8. Configuración y fábrica de proveedor

Agrega configuración mínima y una factoría sencilla para seleccionar proveedor sin condicionales repartidos por el código.

Valores sugeridos:

- `TRANSLATION_PROVIDER=mock` por defecto en desarrollo/tests;
- `TRANSLATION_API_BASE_URL`;
- `TRANSLATION_API_KEY`;
- `TRANSLATION_MODEL`;
- `TRANSLATION_TIMEOUT_SECONDS`.

No es obligatorio exponer todavía un endpoint HTTP de traducción. La Fase 4 será la responsable del flujo web completo.

## 9. CLI de desarrollo

Agrega una utilidad simple que permita probar el pipeline local sobre JSON analizado o directamente sobre una fixture, usando `MockTranslator` por defecto.

Ejemplo conceptual:

```powershell
python scripts/translate_document.py input-analysis.json --target es --provider mock --output output/translated-model.json
```

El CLI no debe requerir credenciales para su modo mock.

Si se habilita el proveedor real, debe leer configuración del entorno y nunca aceptar API keys como argumento visible en la línea de comandos.

## 10. Tests obligatorios

Añade tests suficientes para demostrar al menos:

1. `TextBlock.translated_text` es opcional y compatible con modelos existentes;
2. roundtrip JSON con traducción presente;
3. contrato del `MockTranslator`;
4. traducción de un `Document` completo;
5. el `Document` fuente no se modifica;
6. geometría/estilos/imágenes no cambian tras traducir;
7. recorrido determinista de bloques;
8. bloques vacíos se omiten;
9. contexto anterior/siguiente se construye correctamente;
10. términos protegidos se preservan exactamente;
11. números/códigos/URLs/emails/IP/MAC cubiertos por la capa de protección;
12. placeholders repetidos y colisiones;
13. placeholder perdido/corrupto genera `TranslationIntegrityError`;
14. error del proveedor incluye localización de página/bloque sin filtrar texto fuente;
15. adaptador HTTP real probado con mock de transporte, sin Internet;
16. timeout HTTP normalizado a error interno;
17. HTTP no-2xx normalizado a error interno;
18. respuesta vacía o JSON inválido rechazada;
19. detección automática de idioma cuando el adaptador recibe una respuesta válida;
20. configuración/factoría selecciona mock y proveedor real correctamente.

Los tests no deben depender del manual MICRON ni de una API externa.

## 11. Benchmark MICRON

El manual MICRON puede usarse localmente para medir comportamiento, pero nunca debe agregarse al repositorio.

En esta fase el benchmark útil es:

1. analizar el PDF con `DocumentAnalyzer`;
2. traducir el modelo con `MockTranslator`;
3. comprobar que todas las páginas, bboxes, imágenes y estilos permanecen idénticos;
4. medir cantidad de bloques traducibles y tamaño del JSON resultante.

No gastes llamadas de API reales para traducir las 90 páginas durante validaciones automáticas.

## 12. Documentación y ADR

Crea un ADR breve, sugerido:

`docs/decisions/0003-translation-engine-and-provider-abstraction.md`

Debe documentar:

- contrato `Translator`;
- unidad de traducción por `TextBlock`;
- conservación de `text` + `translated_text`;
- estrategia de protección y restauración;
- comportamiento fail-fast inicial;
- proveedor mock;
- aislamiento del primer proveedor HTTP real;
- política de secretos y logs.

Actualiza README solo con comportamiento ya implementado.

## 13. Límites explícitos de esta fase

No implementes todavía:

- modificación del PDF;
- reflow;
- ajuste de fuentes;
- LayoutEngine;
- PDFRenderer;
- OCR;
- frontend;
- pagos;
- autenticación;
- PostgreSQL;
- Redis;
- workers;
- colas;
- reintentos distribuidos;
- glosarios persistentes en base de datos;
- traducción de texto dentro de imágenes.

Evita sobrearquitectura.

## Reglas de trabajo

- Trabaja en una rama nueva basada en `main`, sugerida: `feat/translation-engine`.
- No trabajes directamente en `main`.
- No hagas merge.
- No hagas push sin autorización.
- No hagas commit al terminar salvo que el usuario lo autorice.
- Mantén Python 3.12 como baseline.
- Código tipado y módulos pequeños.
- Tests offline.
- No logs con contenido documental completo ni secretos.
- Si una ambigüedad menor existe, elige la opción más simple, documenta la decisión y continúa.

## Validaciones antes de terminar

Ejecuta realmente:

```powershell
.venv\Scripts\pytest.exe -v
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
git diff --check
git status --short
git branch --show-current
```

Si cambian dependencias runtime, reconstruye Docker y valida `/health`.

Ejecuta además el CLI en modo mock sobre una fixture reproducible y verifica que el JSON traducido se genera correctamente.

## Criterio de salida de Fase 2

La fase se considera completada cuando un `Document` producido por Fase 1 puede pasar por un `TranslationEngine` desacoplado y producir un nuevo `Document` donde:

- `text` conserva el contenido fuente;
- `translated_text` contiene la traducción por bloque;
- la estructura y geometría originales permanecen intactas;
- números, códigos y términos protegidos se conservan;
- el proveedor puede sustituirse mediante una interfaz estable;
- existe un mock determinista para tests;
- existe un primer adaptador HTTP real configurable;
- todos los tests funcionan sin Internet.

## Entregable

Al finalizar informa:

1. resumen de lo implementado;
2. árbol de archivos creados/modificados;
3. cambios en el modelo de dominio;
4. contrato `Translator` y proveedores implementados;
5. estrategia de protección de términos/tokens;
6. configuración y secretos;
7. comandos de validación y resultados;
8. número y resultado de tests;
9. ejemplo resumido de JSON antes/después;
10. limitaciones conocidas;
11. `git status --short`;
12. propuesta de mensaje de commit convencional.

No hagas commit, push ni merge automáticamente.

---
