import sys
import os

# Añadir el directorio raíz (backend) al sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from app.db.session import engine
from app.models.mantenimiento import ConfiguracionSistema
from app.models.flota import Vehiculo
from app.models.operaciones import Gasto

def verify():
    print("Iniciando verificación de ORM con PostgreSQL...")
    try:
        with Session(engine) as session:
            print("\nTest 1: Consultando 'configuracion_sistema'...")
            config_items = session.query(ConfiguracionSistema).all()
            for item in config_items:
                print(f" - {item.clave}: {item.valor}")
                
            print("\nTest 2: Consultando 'vehiculos'...")
            vehiculos = session.query(Vehiculo).all()
            print(f" - Total vehículos encontrados: {len(vehiculos)}")
            
            print("\nTest 3: Consultando 'gastos'...")
            gasto = session.query(Gasto).first()
            print(f" - Primer gasto: id={gasto.id if gasto else 'N/A'}")
            print(f" - Columnas mapeadas: {[c.name for c in Gasto.__table__.columns]}")
            
            print("\n[OK] Verificacion de mapeo ORM exitosa! Las clases Python estan correctamente conectadas a las tablas SQL.")
    except Exception as e:
        print(f"\n[ERROR] Error durante la verificacion: {e}")

if __name__ == "__main__":
    verify()
