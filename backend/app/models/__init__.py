from .flota import Vehiculo, Conductor, Usuario, ConductorVehiculo
from .operaciones import Proveedor, ViajeODT, Gasto, TarjetaBancaria
from .financiero import Ingreso, LiquidacionConductor, MovimientoBancario, FlypassTransaccion
from .mantenimiento import MantenimientoRegla, MantenimientoRegistro, DocumentoVencimiento, ConfiguracionSistema

# Reexportar todo para simplificar importaciones en otras partes de la app
__all__ = [
    "Vehiculo", "Conductor", "Usuario", "ConductorVehiculo",
    "Proveedor", "ViajeODT", "Gasto", "TarjetaBancaria",
    "Ingreso", "LiquidacionConductor", "MovimientoBancario", "FlypassTransaccion",
    "MantenimientoRegla", "MantenimientoRegistro", "DocumentoVencimiento", "ConfiguracionSistema"
]
