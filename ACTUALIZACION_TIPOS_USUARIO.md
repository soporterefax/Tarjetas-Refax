# Actualización: tipos de tarjeta GNs, B2B y Administrativo

## Qué cambia

- El administrador puede seleccionar `GNs`, `B2B` o `Administrativo` al crear/editar un usuario.
- GNs muestra: logo REFAX, nombre, celular, correo, Call Center fijo, oficina fija y logos de marcas.
- B2B muestra: logo REFAX, nombre, cargo fijo `Ejecutivo Web`, celular, atención web, central fija, oficina fija y frase e-commerce.
- Administrativo muestra: logo REFAX, nombre, cargo, celular, central fija, oficina fija, correo, logos de marcas y web fija.
- Los usuarios B2B tienen una sección privada para guardar múltiples clientes con RUC, usuario y contraseña.
- Las contraseñas de clientes B2B se almacenan cifradas y nunca aparecen en la tarjeta pública.

## Compatibilidad con usuarios existentes

Al iniciar el backend, `database.py` agrega automáticamente las columnas nuevas `tipo_usuario` y `atencion_web` si todavía no existen. Los usuarios existentes quedan como `Administrativo` por defecto. `db.create_all()` crea la tabla nueva `clientes_b2b`.

## Variable recomendada en Azure

Agregar en App Service > Variables de entorno:

`B2B_ENCRYPTION_KEY`

Puede ser una clave Fernet. Para generarla en PowerShell con el entorno virtual activo:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copiar el resultado como valor de `B2B_ENCRYPTION_KEY`, guardar y reiniciar App Service.

Si no se define, el código deriva una clave de `SECRET_KEY` para mantener compatibilidad, pero en producción se recomienda usar la variable dedicada.

## GitHub Pages

La carpeta `docs/` ya contiene una copia lista del frontend. GitHub Pages debe seguir configurado con:

- Branch: `main`
- Folder: `/docs`

## Despliegue

Copiar/reemplazar estos archivos en el repositorio actual y ejecutar:

```powershell
git status
git add .
git commit -m "Agrega tarjetas GNs B2B y Administrativo"
git pull --rebase origin main
git push origin main
```

El push dispara el GitHub Action existente para Azure App Service y GitHub Pages volverá a publicar `/docs`.
