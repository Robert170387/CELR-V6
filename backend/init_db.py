import importlib
import pkgutil

from app.db.base_class import Base
from app.db.session import engine
import app.models

print("1. Cargando todos los modelos de SQLAlchemy...")
for _, module_name, _ in pkgutil.walk_packages(app.models.__path__, app.models.__name__ + "."):
    importlib.import_module(module_name)

print("2. Creando tablas en PostgreSQL si no existen...")
Base.metadata.create_all(bind=engine)

print("--- BASE DE DATOS ESTRUCTURADA CON EXITO ---")