# Guía de trabajo de Autos Colombia

Estas instrucciones se aplican a todo el repositorio. La documentación para
instalar y ejecutar los proyectos en Windows está en `README.md`.

## Estructura

- `backend/app/main.py`: aplicación FastAPI; `GET /health` devuelve HTTP 200 y
  `{"status": "ok"}`.
- `backend/tests/`: pruebas con pytest y `TestClient`.
- `backend/app/config.py`: carga `backend/.env` por ruta absoluta; el entorno tiene prioridad.
- `backend/app/database.py`: motor SQLAlchemy y sesiones bajo demanda con psycopg.
- `backend/check_db.py`: comprobación explícita mediante `SELECT 1`, sin DDL.
- `backend/app/models.py`: Base, Cliente, Vehiculo, Celda, Operador, Puerta, Estancia y Novedad;
  tablas en singular y minúsculas.
- `backend/app/services/panel.py` y `app/services/reporte.py`: mapa en vivo (RF-08), reporte de
  ocupación (RF-10) e historial (RF-11); `services/estancia.py` también cubre salida y novedades.
- `backend/app/schemas/vehiculo.py`: validación Pydantic y contratos de respuesta.
- `backend/app/routers/vehiculos.py`: rutas CRUD con APIRouter.
- `backend/app/services/vehiculo.py`: lógica de vehículos, transacciones y errores públicos.
- `backend/app/schemas/celda.py`, `app/routers/celdas.py` y `app/services/celda.py`:
  CRUD de celdas con código normalizado y tipo libre obligatorio.
- `backend/migrations/`: revisiones Alembic; `backend/alembic.ini` reutiliza la configuración privada.
- `backend/.env.example`: plantilla pública; conservar cualquier `.env` existente y privado.
- `backend/requirements.txt`: dependencias de ejecución y pruebas con versiones
  exactas, incluidas las transitivas.
- `backend/.venv/`: entorno virtual local, excluido de Git.
- `frontend/src/app/`: componentes standalone, configuración y rutas Angular.
- `frontend/src/app/home/`: bienvenida y estado de salud de la API.
- `frontend/src/app/vehiculos/`: formulario reactivo y listado paginado de vehículos.
- `frontend/src/app/celdas/`: gestión de celdas; `CeldasService` reutiliza la base de API.
- `frontend/src/app/mapa/`: mapa de celdas que consulta `/panel` cada 2 s y cambia celdas (RF-08, RF-09).
- `frontend/src/app/reportes/`: reporte de ocupación con exportación e historial con filtros.
- `frontend/src/app/services/api.service.ts`: llamadas HTTP y base de API centralizadas.
- `frontend/src/app/models/vehiculo.ts`: contratos de solicitudes, respuestas y tipos.
- `frontend/src/styles.css`: estilos globales; estilos de componentes en CSS.
- `frontend/public/`: recursos estáticos que sí se versionan.
- `frontend/package.json` y `frontend/package-lock.json`: scripts, dependencias
  y versiones resueltas. Ambos se versionan.
- `frontend/angular.json` y `frontend/tsconfig*.json`: configuración de compilación
  y comprobación estricta.

## Herramientas y dependencias

- Entorno verificado: Python 3.13.16, Node.js 24.22.0 y npm 11.7.0.
- Mantener Node.js en la rama 24 con versión mínima 24.15.0 para Angular 22.
- Usar exclusivamente `backend/.venv` para instalar paquetes y ejecutar Python
  del proyecto. No instalar dependencias del backend globalmente.
- Usar Angular CLI 22 y TypeScript como dependencias locales. No actualizar sus
  instalaciones globales. Para tareas de generación, usar CLI 22 mediante `npx`
  dentro de `frontend`; por ejemplo, `npx.cmd @angular/cli@22 generate component nombre`.
- Usar `npm.cmd ci` para reproducir la instalación existente. Cuando cambien las
  dependencias, actualizar y conservar `package-lock.json` junto con `package.json`.
- Al cambiar dependencias Python, actualizar las versiones fijadas en
  `requirements.txt` desde un entorno del proyecto limpio y verificar `pip check`.
- No editar manualmente `.venv`, `node_modules`, `dist` ni otros archivos generados.

## Convenciones

- Mantener cambios limitados al objetivo solicitado y respetar el trabajo existente.
- Documentar en español los comandos y las decisiones que afecten al desarrollo.
- Python: cuatro espacios, nombres `snake_case` para funciones y variables,
  `PascalCase` para clases y anotaciones de tipos en las funciones nuevas.
- Angular/TypeScript: respetar `frontend/.editorconfig` y `.prettierrc`, usar dos
  espacios, componentes standalone, CSS y el enrutamiento existente.
- Mantener `strict` y `strictTemplates` activados; no desactivar comprobaciones
  para ocultar errores de tipos o de plantillas.
- Añadir o ajustar pruebas cuando cambie el comportamiento. Los endpoints nuevos
  deben probar su estado HTTP y su respuesta esperada.
- Conservar el contrato de `/health` salvo que se solicite cambiarlo.
- Mantener restricciones de integridad en modelos y migraciones. Nunca aplicar
  migraciones a la base del usuario sin autorización; para revisión usar
  `python -m alembic -c alembic.ini upgrade head --sql` con el intérprete de `.venv`.
- Mantener `/health` independiente de PostgreSQL. No conectar ni crear tablas al
  importar módulos. No registrar credenciales, URL de conexión ni errores crudos
  del controlador. Verificar PostgreSQL con `backend/check_db.py`; las pruebas
  simuladas no prueban que exista una conexión local real.
- La pantalla consulta `/health` mediante `HttpClient` al cargarse. El proxy de
  desarrollo en `frontend/proxy.conf.json` dirige también `/panel` y `/reportes/**`; incluye `/health`, `/vehiculos` y
  `/vehiculos/**` a `127.0.0.1:8000`. La pantalla de gestión usa `/gestion/vehiculos`
  para no colisionar con las rutas API. Las llamadas pasan por `ApiService`.
  Mantener rutas relativas y documentar cualquier integración que se añada.

## Secretos y archivos excluidos

El `.gitignore` de la raíz excluye entornos virtuales, dependencias instaladas,
cachés, compilaciones, cobertura, logs, datos locales y patrones habituales de
secretos. `frontend/.gitignore` añade las exclusiones generadas por Angular CLI.

- Nunca incluir credenciales, tokens, contraseñas ni claves privadas en código,
  pruebas, documentación o commits. Los patrones de `.gitignore` no detectan
  todos los posibles secretos; revisar el contenido antes de versionarlo.
- Usar variables de entorno para configuración privada. Las plantillas
  `.env.example` y `.env.template` pueden versionarse solo con valores ficticios.
- No colocar secretos en el frontend: su código y configuración compilados son
  públicos para el navegador.
- No versionar `.npmrc` ni `.pypirc` privados. Documentar la configuración pública
  necesaria sin tokens.
- `.gitignore` no deja de rastrear archivos ya versionados; si se detecta un
  secreto existente, informar del hallazgo sin reproducir su valor.
- Conservar fuentes, pruebas, documentación, configuraciones compartidas,
  `requirements.txt` y `package-lock.json`.

## Comandos de verificación (PowerShell)

Ejecutar desde la raíz del repositorio. `Push-Location` y `Pop-Location` permiten
volver a la raíz aunque falle una comprobación.

### Backend

```powershell
Push-Location backend
try {
    .\.venv\Scripts\python.exe -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependencias del backend inconsistentes.' }
    .\.venv\Scripts\python.exe -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Fallaron las pruebas del backend.' }
} finally {
    Pop-Location
}
```

La prueba actual comprueba `/health` sin iniciar un servidor externo. Starlette
puede emitir un aviso de deprecación sobre `httpx`; distinguirlo de un fallo.

Las pruebas de integración de vehículos se habilitan con `RUN_POSTGRES_TESTS=1`
y requieren `autos_colombia` con la revisión `0001`. Usan rollback exterior y
savepoints: no crear tablas ni alterar migraciones para probar. Los valores de
las secuencias pueden avanzar. Ver `backend/README.md` para comandos completos.

### Frontend

```powershell
Push-Location frontend
try {
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación del frontend.' }
    npm.cmd test -- --watch=false
    if ($LASTEXITCODE -ne 0) { throw 'Fallaron las pruebas del frontend.' }
} finally {
    Pop-Location
}
```

Ejecutar las comprobaciones del proyecto afectado. Para cambios solo de
documentación o exclusiones, revisar rutas, comandos y reglas sin reinstalar
dependencias ni ejecutar suites ajenas al cambio. Informar qué se comprobó y
cualquier limitación pendiente.

Cuando se haya inicializado Git, revisar antes de preparar un commit:

```powershell
git status --short
git diff --check
git diff
```

No crear commits ni publicar cambios salvo que el usuario lo solicite.
