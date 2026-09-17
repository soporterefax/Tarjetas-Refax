# Tarjetas REFAX — GitHub Pages + Azure

## Arquitectura

- `frontend/`: sitio estático para GitHub Pages.
- Flask (`app.py` + blueprints): API para Azure App Service.
- Base de datos: SQLite para desarrollo local y Azure Database for MySQL para producción.

## 1. Probar localmente

Backend:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

El backend queda en `http://127.0.0.1:5000`.

Frontend:

```bash
cd frontend
python -m http.server 5500
```

Abre `http://127.0.0.1:5500`.

`frontend/assets/js/config.js` ya apunta a `http://127.0.0.1:5000` para desarrollo.

## 2. Variables de Azure App Service

En App Service > Settings > Environment variables agrega:

- `SECRET_KEY`
- `ADMIN_USER`
- `ADMIN_PASSWORD`
- `DEFAULT_USER_PASSWORD`
- `TOKEN_HOURS=8`
- `DATABASE_URL`
- `BACKEND_PUBLIC_URL=https://NOMBRE-APP.azurewebsites.net`
- `FRONTEND_URL=https://USUARIO.github.io/NOMBRE-REPO`
- `CORS_ORIGINS=https://USUARIO.github.io`

No guardes contraseñas reales en GitHub.

## 3. MySQL

Crea una base de datos llamada, por ejemplo, `tarjetas_refax` dentro de Azure Database for MySQL Flexible Server.

Ejemplo de `DATABASE_URL`:

```text
mysql+pymysql://USUARIO:PASSWORD@SERVIDOR.mysql.database.azure.com:3306/tarjetas_refax?ssl_ca=/home/site/wwwroot/certs/DigiCertGlobalRootG2.crt.pem
```

La aplicación crea la tabla `usuarios` automáticamente al iniciar.

> Para producción, usa TLS/SSL y configura correctamente la conectividad/firewall entre App Service y MySQL.

## 4. Azure App Service

El proyecto expone el objeto Flask `app` en `app.py`, compatible con Gunicorn:

```text
gunicorn --bind=0.0.0.0:$PORT --timeout 120 app:app
```

El `Procfile` ya contiene ese comando.

Una vez publicado, prueba:

```text
https://NOMBRE-APP.azurewebsites.net/api/health
```

Debe responder:

```json
{"status":"ok"}
```

## 5. GitHub Pages

Antes de publicar, cambia en:

`frontend/assets/js/config.js`

```javascript
window.REFAX_CONFIG = {
  API_URL: "https://NOMBRE-APP.azurewebsites.net"
};
```

Luego publica el contenido de `frontend/` mediante GitHub Pages.

Si Pages se sirve desde una rama con la carpeta `/docs`, puedes copiar el contenido de `frontend/` a `docs/` o configurar un workflow para desplegar esa carpeta.

## 6. QR

El QR ya no se guarda en el disco del servidor. Se genera dinámicamente en:

```text
GET /api/qr/<public_id>.png
```

El QR contiene la URL pública del frontend:

```text
https://USUARIO.github.io/NOMBRE-REPO/tarjeta.html?id=<public_id>
```

Así seguirá funcionando desde celulares y otros dispositivos aunque el backend y frontend estén en servicios distintos.

## Endpoints principales

### Públicos

- `GET /api/health`
- `GET /api/tarjeta/<public_id>`
- `GET /api/qr/<public_id>.png`

### Autenticación

- `POST /api/auth/login`
- `GET /api/auth/me`

### Usuario autenticado

- `GET /api/user/mi-tarjeta`

### Administrador

- `GET /api/admin/usuarios`
- `POST /api/admin/usuarios`
- `PUT /api/admin/usuarios/<public_id>`
- `DELETE /api/admin/usuarios/<public_id>`
- `POST /api/admin/usuarios/<public_id>/reset-password`
