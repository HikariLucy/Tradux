# 3. Motor de traducción desacoplado y abstracción de proveedores

Fecha: 2026-09-04

## Estado

Aceptada

## Contexto

En la Fase 1, Tradux implementó la extracción y representación estructurada de PDFs digitales mediante un modelo de dominio agnóstico (`DocumentModel`).

La Fase 2 requiere incorporar la capacidad de traducir el contenido textual del documento antes de abordar la maquetación y reconstrucción del PDF (Fase 3). Para evitar el acoplamiento temprano a un proveedor comercial específico de IA o a un protocolo particular, es indispensable definir una arquitectura desacoplada, con proveedores intercambiables y protección estricta de términos técnicos y tokens sensibles.

## Decisiones tomadas

### 1. Contrato abstracto de traducción (`Translator`)

- Se define una interfaz desacoplada mediante un protocolo tipado (`app.translators.base.Translator`).
- El contrato opera exclusivamente sobre `TranslationRequest` y devuelve `TranslationResult`.
- Ningún proveedor de traducción conoce objetos PDF, estructuras de PyMuPDF ni detalles de geometría documental.

### 2. Unidad de traducción por bloque textual (`TextBlock`)

- La unidad de traducción en Fase 2 es el bloque de texto (`TextBlock`).
- Razones:
  1. Ofrece el contexto semántico y gramatical adecuado para los modelos de lenguaje.
  2. Evita fragmentar oraciones a nivel de `TextSpan` (lo cual degradaría la coherencia gramatical).
  3. Desacopla la traducción de las decisiones posteriores de ajuste de línea y reflow (objeto de la Fase 3).
- Se extiende `TextBlock` añadiendo el campo opcional `translated_text: str | None = None`, manteniendo `text` intacto con el contenido fuente original y preservando total compatibilidad hacia atrás con la serialización de Fase 1.

### 3. Inmutabilidad del documento fuente y clonación profunda

- `TranslationEngine.translate_document()` nunca muta el objeto `Document` de entrada.
- Aplica una copia profunda (`document.model_copy(deep=True)`) y asigna `translated_text` en la nueva instancia resultante.
- Todas las geometrías (`BoundingBox`), fuentes, tamaños, colores, imágenes, páginas y orden estructural original permanecen inalterados.

### 4. Capa de protección de tokens y términos (`protection.py`)

- Antes de enviar texto al proveedor, se enmascaran los elementos que deben preservarse exactamente mediante una familia de placeholders deterministas:
  `__TRX_PH_{index:03d}__` (ej. `__TRX_PH_000__`, `__TRX_PH_001__`).
- Tipos de tokens protegidos automáticamente:
  - Términos explícitos (`protected_terms`) solicitados por el usuario;
  - URLs (`http://...`, `https://...`);
  - Direcciones de correo electrónico;
  - Direcciones IPv4 y direcciones MAC;
  - Códigos técnicos e identificadores (`MODEL-X100`, `ISO-9001`, etc.);
  - Valores numéricos independientes.
- **Validación estricta de integridad:** Cada ocurrencia recibe un placeholder único. Al recibir la traducción, el restaurador valida que cada placeholder esté presente exactamente una vez. Si un placeholder falta, se duplica o se corrompe, se aborta la operación lanzando `TranslationIntegrityError`.

### 5. Comportamiento Fail-Fast y localización de errores

- En esta etapa (V0.1), si un bloque falla o la integridad de tokens es violada, el proceso se detiene inmediatamente (*fail-fast*).
- El error incluye la localización primitiva del problema (`page_number`, `reading_order`), sin exponer en logs ni mensajes el contenido completo de bloques confidenciales.

### 6. Proveedores implementados

- **`MockTranslator`:** Proveedor determinista para desarrollo y tests 100% offline. Genera traducciones sintéticas preservando los placeholders intactos y soporta detección simulada de idioma.
- **`OpenAITranslator`:** Primer adaptador real HTTP sobre la API estándar de OpenAI-compatible Chat Completions, implementado mediante `httpx.AsyncClient` sin SDKs pesados externos. Soporta detección automática de idioma vía respuestas JSON estructuradas cuando `source_language is None`.
- **`get_translator`:** Factoría centralizada para seleccionar proveedor (`mock` o `openai`) según configuración.

### 7. Seguridad y gestión de credenciales

- Las credenciales (`TRANSLATION_API_KEY`) se cargan únicamente mediante variables de entorno (`Settings`).
- Ninguna clave se almacena en el repositorio ni se admite como argumento plano de línea de comandos en scripts CLI.
- No se registran claves ni cuerpos completos de peticiones en los logs.

## Consecuencias

- **Positivas:**
  - El motor documental es independiente de proveedores de IA o traducción.
  - La suite de pruebas corre velozmente de forma 100% offline y sin costos de tokens.
  - Se garantiza que códigos técnicos, URLs y números no sean corrompidos por el modelo de lenguaje.
- **Limitaciones conocidas:**
  - No se cuenta con persistencia de trabajos ni colas distribuidas (previsto para Fase 6).
  - No se realiza traducción de texto incrustado en imágenes (Fase 8).
  - No se efectúa aún el ajuste de layout ni reemplazo visual en el PDF (Fase 3).
