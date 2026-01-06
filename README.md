# SaaS Boilerplate con Django (Desarrollo Local con Docker para la BD)

Este es un boilerplate de SaaS (Software as a Service) construido con Django y Django Rest Framework (DRF). Utiliza Docker únicamente para gestionar la base de datos PostgreSQL, permitiendo que la aplicación Django se ejecute directamente en la máquina local para un desarrollo más rápido y sencillo.

## Características Principales

- **Backend:** Django 
- **API:** Django Rest Framework con autenticación JWT.
- **Base de Datos:** PostgreSQL (gestionado con Docker).
- **Modelo de Usuario Personalizado:** Autenticación basada en email.
- **Auditoría:** Middleware que registra todas las peticiones de modificación.
- **Internacionalización (i18n):** Configurado para Inglés y Español.

---

## Cómo Empezar (Flujo de Trabajo Híbrido)

### Prerrequisitos
- Docker y Docker Compose instalados.
- Python 3.12 instalado en tu máquina local.

### Pasos

1.  **Configurar el Entorno Local:**
    ```bash
    # (Si es un repo git) git clone <url_del_repo>
    # cd saas_boilerplate

    # Crear y activar el entorno virtual
    python3.12 -m venv .venv
    source .venv/bin/activate

    # Instalar dependencias
    pip install -r requirements.txt

    # Configurar variables de entorno
    cp .env.example .env
    ```
    *Asegúrate de que en `.env` tienes `DB_HOST=localhost`.*

2.  **Iniciar la Base de Datos (Terminal 1):**
    En una terminal, inicia el contenedor de la base de datos. Déjala corriendo.
    ```bash
    docker-compose up
    ```

3.  **Ejecutar la Aplicación Django (Terminal 2):**
    En una segunda terminal, con el entorno virtual activado, puedes usar los comandos de Django.
    
    *   **Aplica las migraciones iniciales:**
        ```bash
        python manage.py migrate
        ```

    *   **Crea un superusuario:**
        ```bash
        python manage.py create_admin_auto
        # O manualmente:
        # python manage.py createsuperuser
        ```

    *   **Inicia el servidor de desarrollo:**
        ```bash
        python manage.py runserver
        ```

4.  **¡Listo!**
    El servicio estará corriendo en `http://localhost:8000`.
    - La API de autenticación está en `http://localhost:8000/api/v1/auth/`.
    - El panel de administración de Django está en `http://localhost:8000/admin/`.

---

## Cómo Renombrar el Proyecto

Para usar este boilerplate en un nuevo proyecto (ej. `my_new_app`), el nombre del proyecto interno (`core`) debe ser cambiado.

La forma más sencilla es usar "Buscar y Reemplazar" en todo el proyecto con tu editor de código:
1.  Busca la cadena `core`.
2.  Reemplázala por el nombre de tu nuevo proyecto (ej. `my_new_app`).

**Archivos y carpetas a revisar:**
- `core/` -> `my_new_app/` (renombra la carpeta).
- En `manage.py`, cambia `os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')`.
- En `my_new_app/settings.py`, revisa `ROOT_URLCONF = 'core.urls'`.
- En `my_new_app/wsgi.py` y `my_new_app/asgi.py`, cambia la referencia a `core.settings`.

---

## Internacionalización (i18n)

El proyecto está configurado para soportar múltiples idiomas (inglés y español por defecto).

### Cómo generar y compilar traducciones:

1.  **Marcar textos para traducción:**
    En tu código Python, usa la función `gettext_lazy`.
    ```python
    from django.utils.translation import gettext_lazy as _
    
    class MyModel(models.Model):
        name = models.CharField(_("name"), max_length=100)
    ```

2.  **Generar los archivos de traducción (.po):**
    Asegúrate de que tu entorno virtual está activado.
    ```bash
    python manage.py makemessages -l es -l en
    ```

3.  **Editar los archivos `.po`:**
    Abre `locale/es/LC_MESSAGES/django.po` y `locale/en/LC_MESSAGES/django.po` y añade las traducciones.

4.  **Compilar las traducciones (.mo):**
    ```bash
    python manage.py compilemessages
    ```