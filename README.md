# Tarjetas REFAX

Versión adaptada para una arquitectura separada:

- **Frontend:** GitHub Pages (`frontend/`)
- **Backend/API:** Flask en Azure App Service
- **Base de datos:** Azure Database for MySQL (SQLite disponible para desarrollo local)

Consulta [AZURE_GITHUB_PAGES.md](AZURE_GITHUB_PAGES.md) para la guía de despliegue.

## Desarrollo local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

En otra terminal:

```bash
cd frontend
python -m http.server 5500
```

Visita `http://127.0.0.1:5500`.
