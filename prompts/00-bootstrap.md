# Prompt 00 — Bootstrap de Tradux

Usa este prompt en Codex/OpenCode/Antigravity desde la raíz del repositorio.

---

Estamos iniciando **Tradux**, una aplicación para traducir documentos preservando al máximo su maquetación original.

Antes de modificar nada, lee completos:

- `README.md`
- `docs/architecture.md`
- `docs/roadmap.md`

## Objetivo de esta tarea

Implementar únicamente la **Fase 0 — Definición e inicialización**, dejando una base limpia y reproducible para comenzar después el analizador de PDFs.

## Stack obligatorio inicial

- Python 3.12+
- FastAPI
- PyMuPDF
- Pydantic
- pytest
- Ruff
- Docker

No agregues todavía PostgreSQL, Redis, Celery, OCR, frontend React ni ningún proveedor real de traducción.

## Trabajo solicitado

1. Crea una estructura Python mantenible bajo `app/` siguiendo, en lo posible, la arquitectura documentada.
2. Configura `pyproject.toml` con dependencias de runtime y desarrollo.
3. Implementa una aplicación FastAPI mínima con:
   - `GET /health` → HTTP 200 y JSON estable;
   - metadata básica del proyecto.
4. Crea un módulo de configuración basado en variables de entorno, sin secretos hardcodeados.
5. Agrega `.env.example` solo con variables no sensibles y valores de ejemplo.
6. Agrega `.gitignore` adecuado para Python, IDEs, archivos temporales y documentos procesados.
7. Agrega `Dockerfile` y, solo si aporta valor real, `docker-compose.yml` mínimo.
8. Crea tests para `/health` y configuración básica.
9. Configura Ruff.
10. Agrega un `Makefile` si es portable; si no, documenta los comandos directos en README. El entorno principal del usuario es Windows/PowerShell, por lo que no debe depender exclusivamente de Bash.
11. Actualiza README con instrucciones exactas para:
    - crear entorno virtual en PowerShell;
    - instalar dependencias;
    - ejecutar el servidor;
    - ejecutar tests;
    - ejecutar lint;
    - construir/ejecutar Docker.
12. Crea `docs/decisions/0001-initial-stack.md` documentando brevemente la decisión de usar Python + FastAPI + PyMuPDF y por qué todavía no incorporamos servicios adicionales.

## Reglas

- No implementes aún traducción real.
- No implementes aún extracción compleja de PDFs.
- No agregues dependencias sin justificar su uso.
- Mantén módulos pequeños y tipados.
- No guardes PDFs de prueba que tengan restricciones de distribución.
- No introduzcas credenciales ni API keys.
- Los tests deben funcionar sin conexión a Internet.
- Ejecuta todos los tests y lint antes de terminar.
- Ejecuta `git diff --check`.
- No hagas merge a `main` automáticamente.

## Entregable

Al finalizar, informa:

1. archivos creados/modificados;
2. decisiones tomadas;
3. comandos de validación ejecutados y resultado;
4. cualquier deuda técnica detectada;
5. `git status --short`;
6. una propuesta de mensaje de commit convencional.

Si existe una ambigüedad menor, elige la opción más simple y documenta la decisión; no detengas el trabajo con preguntas innecesarias.

---