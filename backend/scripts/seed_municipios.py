"""Seed idempotente del catalogo DIVIPOLA (departamentos/municipios).

Lee backend/data/municipios_colombia.json (dataset CC-BY-4.0 de
open-admin-data/colombia-administrative-divisions, 1122 municipios) y
hace upsert por codigo_dane.
"""
import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.models.ubicacion import Municipio

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "municipios_colombia.json")


def seed_municipios(db, data_path=DATA_PATH) -> tuple:
    with open(data_path, encoding="utf-8") as f:
        registros = json.load(f)

    insertados = 0
    for reg in registros:
        codigo_dane = reg["code"]["id"][2:]
        departamento = reg["parent"]["name"]["local"]
        municipio = reg["name"]["local"]
        existente = db.query(Municipio).filter(Municipio.codigo_dane == codigo_dane).first()
        if existente:
            if existente.departamento != departamento or existente.municipio != municipio:
                existente.departamento = departamento
                existente.municipio = municipio
        else:
            db.add(Municipio(codigo_dane=codigo_dane, departamento=departamento, municipio=municipio))
            insertados += 1
    db.commit()
    return insertados, len(registros)


if __name__ == "__main__":
    db = SessionLocal()
    try:
        insertados, total_fuente = seed_municipios(db)
        print(f"Municipios en fuente: {total_fuente} | Insertados: {insertados}")
        print("[OK] Seed de municipios finalizado")
    finally:
        db.close()