# Prompt 02.5 — Tradux Web Workbench

Usa este prompt desde la raíz del repositorio en una rama nueva basada en `main`.

---

Estamos desarrollando **Tradux**, una aplicación para traducir documentos preservando al máximo su maquetación original.

Las Fases 0, 1 y 2 ya están completadas. Tradux ya dispone de:

- aplicación FastAPI reproducible;
- `DocumentAnalyzer` para PDFs digitales;
- modelo documental tipado (`Document`, `Page`, `TextBlock`, `TextLine`, `TextSpan`, `ImageElement`, `BoundingBox`);
- endpoint real `POST /api/v1/documents/analyze`;
- `TranslationEngine` desacoplado;
- `MockTranslator` determinista y proveedor HTTP OpenAI-compatible configurable;
- protección de números, códigos, términos y placeholders;
- CLI de análisis y traducción.

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

## Objetivo de esta tarea

Implementar una **Fase 2.5 — Tradux Web Workbench**: una interfaz web ligera, específica para Tradux y conectada a las capacidades reales ya implementadas.

Esta fase NO sustituye la futura Fase 4 (MVP web completo). Su objetivo es que podamos abrir Tradux en el navegador y visualizar el producto real antes de construir el `LayoutEngine`.

Debe permitir como mínimo:

1. seleccionar o arrastrar un PDF digital;
2. previsualizar localmente el PDF original en el navegador;
3. analizarlo usando el endpoint real existente;
4. mostrar estadísticas reales del `DocumentModel`;
5. elegir idioma origen/destino y términos protegidos;
6. ejecutar una **vista de traducción mock** usando el `TranslationEngine` real con `MockTranslator`, sin llamadas externas;
7. comparar bloques fuente/traducción en una vista técnica legible;
8. mostrar claramente que la generación del PDF traducido llegará en Fase 3.

## Principio principal de diseño

La interfaz debe sentirse como **Tradux**, no como una plantilla SaaS genérica.

Evita explícitamente:

- dashboards con tarjetas genéricas de métricas;
- navegación tipo `Home / Users / Analytics / Settings`;
- gradientes morados genéricos;
- estética de panel administrativo;
- componentes visuales sin relación con documentos;
- librerías UI pesadas solo por conveniencia.

La identidad visual debe transmitir:

- precisión documental;
- trabajo técnico/editorial;
- conservación de estructura;
- sensación de herramienta profesional de traducción, no chatbot.

### Dirección visual sugerida

Construye una interfaz **desktop-first**, sobria y editorial:

- fondo claro cálido o gris muy suave;
- texto grafito profundo;
- un único acento frío (azul/cian sobrio), sin gradientes llamativos;
- bordes finos y radios moderados;
- tipografía del sistema para UI;
- monospace del sistema para metadata técnica (páginas, bloques, dimensiones, coordenadas);
- sin dependencias de fuentes externas ni CDNs;
- iconografía mediante SVG inline simple cuando sea necesaria;
- buena jerarquía tipográfica y mucho espacio útil para el documento.

No hardcodees colores directamente por todas partes: usa variables CSS.

## 1. Stack frontend obligatorio para esta fase

Mantén la decisión de interfaz ligera ya documentada.

Usa:

- FastAPI;
- Jinja2 para el shell HTML;
- CSS propio;
- JavaScript vanilla moderno;
- APIs web nativas (`fetch`, `FormData`, `URL.createObjectURL`).

No introducir todavía:

- React;
- Next.js;
- Vue;
- Svelte;
- Vite;
- Node/npm;
- Tailwind;
- Bootstrap;
- Material UI;
- una SPA compleja.

Si Jinja2 no está declarado como dependencia runtime, agrégalo correctamente a `pyproject.toml`.

## 2. Estructura sugerida

Mantén módulos pequeños. Una estructura válida sería:

```text
app/
├── web/
│   ├── __init__.py
│   ├── router.py
│   ├── templates/
│   │   └── workbench.html
│   └── static/
│       ├── workbench.css
│       └── workbench.js
└── api/
    └── v1/
        └── workbench.py
```

Puedes adaptar nombres si existe una razón clara, pero no mezcles grandes bloques HTML/CSS/JS dentro de `app/main.py`.

## 3. Ruta web

La ruta:

```text
GET /
```

debe servir el Tradux Web Workbench.

Mantén intactos:

- `/health`;
- `/docs`;
- `/redoc`;
- `/api/v1/...`.

Monta los archivos estáticos de forma explícita y robusta usando rutas derivadas desde `Path(__file__)`, no dependiendo del current working directory.

## 4. Estado inicial del Workbench

Al abrir `/`, muestra un shell de producto reconocible con:

### Header compacto

- marca textual `Tradux`;
- descriptor corto, por ejemplo `Document Translation Workbench` o equivalente en español;
- badge discreto `Local workbench` / `V0.1`;
- sin navegación administrativa ficticia.

### Área principal de carga

Debe comunicar claramente:

> Traduce documentos conservando su estructura.

Incluye:

- zona drag & drop;
- selector de archivo accesible mediante teclado;
- restricción visual a PDF;
- nombre y tamaño del archivo seleccionado;
- botón principal `Analizar documento`.

No hagas análisis automático al mero arrastrar si eso hace la interacción confusa: el usuario debe entender cuándo empieza el procesamiento.

## 5. Preview del PDF original

Después de seleccionar un PDF:

- genera un `Object URL` del archivo en el navegador;
- muestra el documento original mediante `<object>`, `<embed>` o `<iframe>` compatible;
- no necesitas subir el PDF solo para visualizarlo;
- libera `URL.revokeObjectURL()` al reemplazar archivo y al desmontar/salir cuando corresponda;
- proporciona fallback visual si el navegador no puede renderizar PDF embebido.

No construyas todavía un renderer PDF propio en frontend.

## 6. Análisis real

Al pulsar `Analizar documento`:

- usa `FormData`;
- llama al endpoint existente:

```text
POST /api/v1/documents/analyze
```

- no dupliques la lógica de `DocumentAnalyzer` en frontend;
- maneja estados `idle`, `analyzing`, `ready`, `error` de manera explícita;
- evita doble submit mientras existe una operación en curso;
- si el backend devuelve error, muestra un mensaje útil sin stack trace.

### Métricas reales a mostrar

Deriva desde el JSON devuelto, sin inventar valores:

- nombre de archivo;
- número de páginas;
- total de bloques de texto;
- total de líneas;
- total de spans;
- total de ocurrencias de imágenes;
- número de fuentes únicas;
- lista corta de fuentes detectadas;
- rotaciones presentes si existen;
- dimensiones de página, resumidas cuando sean homogéneas.

No hace falta persistir estas métricas.

## 7. Layout principal después del análisis

La vista debe convertirse en un **workspace documental** de tres zonas lógicas:

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Tradux · nombre.pdf                                  V0.1 Workbench │
├───────────────┬───────────────────────────────────┬─────────────────┤
│ Documento     │ Preview del PDF original          │ Traducción      │
│ / estructura  │                                   │                 │
│               │                                   │ origen → destino│
│ stats reales  │                                   │ términos        │
│               │                                   │ pasos           │
├───────────────┴───────────────────────────────────┴─────────────────┤
│ Vista de bloques: fuente ↔ traducción mock                           │
└─────────────────────────────────────────────────────────────────────┘
```

No es obligatorio que las columnas tengan exactamente estos anchos, pero en escritorio el PDF debe ser visualmente protagonista.

## 8. Controles de traducción

En el panel derecho incluye:

- `Idioma origen`: opción `Auto` y una lista corta útil (es, en, nl, de, fr, pt, it) sin pretender ser todavía un catálogo completo;
- `Idioma destino`: al menos los mismos idiomas, con `es` como valor inicial razonable;
- términos protegidos como chips/tags editables o un input donde Enter agregue términos;
- posibilidad de eliminar un término;
- botón `Vista de traducción`.

No es necesario implementar intercambio visual complejo de idiomas si añade demasiado código.

## 9. Traducción de demostración real del pipeline

La vista de traducción debe usar la implementación real de Fase 2, pero **forzar `MockTranslator`** en esta fase para garantizar:

- cero costo;
- cero red;
- determinismo;
- seguridad durante desarrollo.

Agrega un endpoint de workbench claramente identificado como herramienta de desarrollo, por ejemplo:

```text
POST /api/v1/workbench/translate
```

### Request sugerido

```json
{
  "document": { "...": "DocumentModel completo" },
  "source_language": null,
  "target_language": "es",
  "protected_terms": ["Tradux", "MODEL-X100"]
}
```

### Response sugerido

```json
{
  "mode": "mock",
  "translated_blocks": 12,
  "document": { "...": "nuevo Document traducido" }
}
```

Requisitos:

- valida request con Pydantic;
- llama a `TranslationEngine(MockTranslator())`;
- no dupliques lógica de traducción;
- no modifiques el documento recibido;
- no uses proveedor real aunque `.env` tenga `TRANSLATION_PROVIDER=openai`;
- no expongas ni leas API keys para este endpoint;
- errores de integridad/proveedor deben convertirse en respuesta HTTP segura;
- el endpoint debe quedar claramente documentado como **workbench/dev preview**, no API definitiva de producción.

## 10. Vista de bloques fuente ↔ traducción

Después de la traducción mock, muestra una sección inferior o panel deslizable con bloques comparables.

Cada fila debe permitir identificar:

- página;
- `reading_order`;
- texto fuente;
- `translated_text`;

No muestres automáticamente todos los bloques de un manual de 90 páginas de una sola vez si eso degrada el navegador.

Implementa una estrategia simple como:

- primeros 30–50 bloques inicialmente;
- filtro por número de página;
- o paginación simple en cliente.

No necesitas virtual scrolling complejo.

El propósito es inspeccionar el pipeline, no editar traducciones todavía.

## 11. Stepper / estado del pipeline

Incluye un indicador discreto que represente el producto real:

```text
1. Análisis       ✓
2. Traducción     ✓ / pendiente
3. Layout         Próxima fase
4. QA             Pendiente
```

No marques como completadas capacidades inexistentes.

Después de la traducción mock, puede mostrarse algo como:

- `Análisis · listo`;
- `Traducción · preview mock`;
- `Layout · todavía no disponible`;
- `QA · todavía no disponible`.

Esto debe ayudar a visualizar el roadmap dentro del producto.

## 12. Estados visuales y UX

Implementa de forma cuidada:

- estado vacío;
- archivo seleccionado pero no analizado;
- analizando;
- análisis listo;
- traduciendo preview;
- traducción preview lista;
- error.

Los botones deben deshabilitarse cuando la acción no corresponde.

Muestra feedback de carga mediante texto/spinner CSS discreto; no agregues librerías externas.

Errores deben ser humanos y compactos.

## 13. Accesibilidad mínima obligatoria

- labels asociados a inputs;
- foco visible;
- botones y zona de carga utilizables por teclado;
- `aria-live` para estados/progreso o errores cuando sea útil;
- contraste suficiente;
- no depender solo de color para representar estado;
- respeta `prefers-reduced-motion` para animaciones.

## 14. Seguridad y privacidad

- no almacenes el PDF en `localStorage` ni `sessionStorage`;
- no almacenes el `DocumentModel` permanentemente en navegador;
- no uses CDN externos;
- no cargues analytics;
- no hagas llamadas a terceros desde frontend;
- la traducción preview debe ser siempre mock;
- no renderices texto documental mediante `innerHTML`; utiliza `textContent` para evitar inyección;
- cualquier metadata proveniente del PDF debe tratarse como texto no confiable.

## 15. CSS y mantenibilidad

Usa CSS propio con variables, por ejemplo conceptualmente:

```css
:root {
  --bg: ...;
  --surface: ...;
  --ink: ...;
  --muted: ...;
  --border: ...;
  --accent: ...;
}
```

No hace falta copiar estos valores literalmente.

Requisitos:

- responsive razonable hasta tablet/móvil;
- no más complejidad de la necesaria;
- evita cientos de clases utilitarias manuales;
- nombres de clases semánticos;
- sin estilos inline salvo casos técnicamente justificados.

## 16. Tests obligatorios

Mantén todos los tests existentes verdes y agrega cobertura offline para al menos:

1. `GET /` devuelve 200 y HTML del Workbench;
2. los assets estáticos necesarios son servibles;
3. el HTML contiene los elementos críticos de interfaz sin depender de JavaScript para existir estructuralmente;
4. `POST /api/v1/workbench/translate` acepta un `Document` válido;
5. la respuesta usa `mode="mock"`;
6. `translated_text` se completa mediante el `TranslationEngine` real;
7. `text` permanece intacto;
8. geometría/imágenes permanecen intactas;
9. términos protegidos funcionan también a través del endpoint;
10. un payload documental inválido devuelve 422 de validación sin 500;
11. el endpoint no selecciona accidentalmente el proveedor real aunque settings indiquen `openai`;
12. ningún test requiere Internet.

No es necesario introducir Playwright/Selenium en esta fase.

## 17. Smoke test manual obligatorio

Después de implementar:

1. levanta Tradux localmente;
2. abre o consulta `GET /`;
3. verifica que CSS y JS carguen;
4. usa la fixture PDF reproducible;
5. realiza análisis desde el Workbench;
6. ejecuta la vista de traducción mock;
7. comprueba visualmente que aparecen métricas reales y bloques fuente/traducción.

Si no puedes automatizar el navegador desde el agente, documenta exactamente las URLs y pasos para que el usuario lo compruebe en su navegador.

## 18. Docker

Si agregas Jinja2 u otra dependencia runtime, reconstruye Docker.

Verifica al menos:

```text
GET /health -> 200
GET / -> 200
```

Asegúrate de que templates y static files se copien dentro de la imagen Docker. El Dockerfile actual puede requerir ajuste porque inicialmente solo copiaba el paquete Python; valida realmente el contenido del contenedor.

## 19. README

Actualiza README solamente con comportamiento realmente implementado:

- cómo abrir el Workbench;
- qué permite actualmente;
- aclaración explícita de que la traducción visual usa `MockTranslator`;
- aclaración de que aún NO se genera el PDF traducido;
- enlace al Swagger sigue disponible.

No declares Fase 3 como completada.

## 20. Límites explícitos

No implementes todavía:

- modificación/reconstrucción del PDF;
- LayoutEngine;
- reflow;
- sustitución/ajuste de fuentes;
- PDFRenderer;
- descarga de PDF traducido;
- QA visual;
- OCR;
- autenticación;
- usuarios;
- historial persistente;
- PostgreSQL;
- Redis;
- workers;
- pagos;
- cuotas;
- frontend React/Next;
- edición manual de bloques;
- almacenamiento de documentos;
- llamadas reales de traducción desde la interfaz.

Evita convertir esta fase en Fase 4 anticipadamente.

## 21. Reglas de trabajo

- Trabaja en rama `feat/web-workbench` basada en `main` actualizado.
- No trabajes directamente en `main`.
- No hagas commit al terminar salvo autorización.
- No hagas push ni merge sin autorización.
- Python 3.12 baseline.
- Tests 100% offline.
- No introducir Node.
- No registrar contenido documental completo en logs.
- No versionar PDFs benchmark ni outputs temporales.
- No modificar los prompts anteriores.
- Si una ambigüedad menor existe, elige la solución más simple, documenta y continúa.

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

Si cambian dependencias runtime:

```powershell
docker build -t tradux:workbench .
```

y valida `/health` y `/` desde el contenedor.

Ejecuta también un smoke real del endpoint de workbench usando una fixture reproducible.

## Criterio de salida

La Fase 2.5 se considera completada cuando al ejecutar Tradux localmente el usuario puede abrir `/` y obtener una interfaz propia de Tradux que:

- permite seleccionar/previsualizar un PDF;
- analiza el archivo mediante el backend real;
- presenta estadísticas del `DocumentModel` real;
- permite configurar idiomas y términos protegidos;
- ejecuta una traducción de demostración con `TranslationEngine(MockTranslator())`;
- presenta bloques fuente ↔ traducción;
- representa honestamente que Layout y QA aún están pendientes;
- no utiliza servicios externos;
- mantiene tests y Docker verdes.

## Entregable final

Al terminar informa:

1. resumen de implementación;
2. archivos creados/modificados;
3. decisiones de UX y diseño visual;
4. flujo funcional del Workbench;
5. endpoint mock de preview y seguridad;
6. dependencias agregadas;
7. tests agregados y resultado total;
8. validaciones ejecutadas;
9. Docker/smoke test;
10. pasos exactos para que el usuario abra la interfaz en Windows;
11. limitaciones visuales/funcionales actuales;
12. `git status --short`;
13. propuesta de commit convencional.

No hagas commit, push ni merge automáticamente.

---
