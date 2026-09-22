from pydantic import BaseModel


class MunicipioResponse(BaseModel):
    id: int
    codigo_dane: str
    departamento: str
    municipio: str

    class ConfigDict:
        from_attributes = True