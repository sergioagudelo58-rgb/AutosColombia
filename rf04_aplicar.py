"""RF-04 (Leydi): aplica todos los cambios en el repositorio."""
import re
import sys
from pathlib import Path

textos: dict[str, str] = {}
crlf: dict[str, bool] = {}
errores: list[str] = []


def cargar(ruta: str) -> None:
    p = Path(ruta)
    if not p.exists():
        errores.append(f"No existe {ruta} (ejecuta el script desde la raiz del repositorio)")
        return
    t = p.read_bytes().decode("utf-8")
    crlf[ruta] = "\r\n" in t
    textos[ruta] = t.replace("\r\n", "\n")


def editar(ruta: str, viejo: str, nuevo: str) -> None:
    if ruta not in textos:
        return
    n = textos[ruta].count(viejo)
    if n != 1:
        errores.append(f"{ruta}: se esperaba 1 coincidencia y hubo {n}: {ascii(viejo[:70])}")
        return
    textos[ruta] = textos[ruta].replace(viejo, nuevo)


ARCHIVOS = [
    "backend/app/schemas/vehiculo.py",
    "backend/app/schemas/pago.py",
    "backend/app/services/vehiculo.py",
    "backend/tests/test_vehiculos.py",
    "backend/tests/test_vehiculos_postgres.py",
    "backend/tests/test_pagos_postgres.py",
    "frontend/src/app/models/vehiculo.ts",
    "frontend/src/app/pagos/pagos.ts",
    "frontend/src/app/clientes/clientes.ts",
    "frontend/src/app/clientes/clientes.html",
    "frontend/src/app/clientes/clientes.spec.ts",
]
for a in ARCHIVOS:
    cargar(a)

# ---------------------------------------------------------------- schemas/vehiculo.py
f = "backend/app/schemas/vehiculo.py"
editar(f, '''from datetime import date
from typing import Annotated, Literal
''', '''from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
''')
editar(f, '''class VehiculoCrear(BaseModel):
    """RF-02: todo vehículo nuevo pertenece a un cliente y trae su fecha de pago."""
    model_config = ConfigDict(extra="forbid")

    placa: Placa
    color: Texto
    modelo: Anio
    marca: Texto
    tipo: TipoVehiculo
    cliente_id: IdCliente
    linea: Texto
    fecha_pago: date
''', '''MedioPago = Literal["BANCO", "EFECTIVO", "QR"]
# Igual que la columna pago.valor: NUMERIC(12, 2), mayor que cero (RNF-04).
ValorPago = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


class VehiculoCrear(BaseModel):
    """RF-02 y RF-04: todo vehículo nuevo pertenece a un cliente y trae su primer pago.

    fecha_pago, valor y medio se guardan como el primer pago del vehículo (RN-08).
    """
    model_config = ConfigDict(extra="forbid")

    placa: Placa
    color: Texto
    modelo: Anio
    marca: Texto
    tipo: TipoVehiculo
    cliente_id: IdCliente
    linea: Texto
    fecha_pago: date
    valor: ValorPago
    medio: MedioPago
''')
editar(f, '''class VehiculoActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")
''', '''class VehiculoActualizar(BaseModel):
    """RF-04: fecha_pago ya no se edita aquí; la mensualidad solo cambia con un pago (POST /pagos)."""
    model_config = ConfigDict(extra="forbid")
''')
editar(f, '''    linea: Texto | None = None
    fecha_pago: date | None = None
''', '''    linea: Texto | None = None
''')

# ---------------------------------------------------------------- schemas/pago.py
f = "backend/app/schemas/pago.py"
editar(f, '''from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.cliente import ClienteRespuesta, Documento
from app.schemas.vehiculo import Placa, VehiculoRespuesta
from app.services.mensualidad import Mensualidad

MedioPago = Literal["BANCO", "EFECTIVO", "QR"]
# Igual que la columna pago.valor: NUMERIC(12, 2), mayor que cero (RNF-04).
ValorPago = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
''', '''from datetime import date, datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.cliente import ClienteRespuesta, Documento
# MedioPago y ValorPago viven en schemas.vehiculo: el vehículo nuevo guarda su primer pago (RF-04).
from app.schemas.vehiculo import MedioPago, Placa, ValorPago, VehiculoRespuesta
from app.services.mensualidad import Mensualidad
''')

# ---------------------------------------------------------------- services/vehiculo.py
f = "backend/app/services/vehiculo.py"
editar(f, '''from app.models import Vehiculo
from app.services.auditoria import registrar as auditar
from app.schemas.vehiculo import VehiculoActualizar, VehiculoCrear
''', '''from app.models import Pago, Vehiculo
from app.services.auditoria import registrar as auditar
from app.services.mensualidad import hoy_colombia
from app.schemas.vehiculo import VehiculoActualizar, VehiculoCrear

FECHA_FUTURA = "La fecha de pago no puede ser posterior a hoy."
''')
editar(f, '''@database_operation
def create_vehicle(session: Session, data: VehiculoCrear, actor: Actor) -> Vehiculo:
    vehicle = Vehiculo(**data.model_dump())
    session.add(vehicle)
    session.flush()
    auditar(session, accion="VEHICULO_CREADO", entidad="vehiculo", entidad_id=vehicle.id, placa=vehicle.placa,
            actor=actor, nuevo=data.model_dump())
    session.commit()
    session.refresh(vehicle)
    return vehicle
''', '''@database_operation
def create_vehicle(session: Session, data: VehiculoCrear, actor: Actor) -> Vehiculo:
    """Registra el vehículo y su primer pago en una sola transacción (RF-04, RN-08)."""
    if data.fecha_pago > hoy_colombia():
        raise VehiculoError(422, FECHA_FUTURA)
    datos_vehiculo = data.model_dump(exclude={"valor", "medio"})
    vehicle = Vehiculo(**datos_vehiculo)
    session.add(vehicle)
    session.flush()
    auditar(session, accion="VEHICULO_CREADO", entidad="vehiculo", entidad_id=vehicle.id, placa=vehicle.placa,
            actor=actor, nuevo=datos_vehiculo)
    # El modelo ya calculó el vencimiento (fecha de pago + 30 días, sin corte anterior): el primer pago lo guarda.
    pago = Pago(vehiculo_id=vehicle.id, cliente_id=vehicle.cliente_id, fecha_pago=data.fecha_pago,
                valor=data.valor, medio=data.medio, vencimiento_anterior=None,
                vencimiento_nuevo=vehicle.fecha_vencimiento, operador_id=actor.id)
    session.add(pago)
    session.flush()
    auditar(session, accion="PAGO_REGISTRADO", entidad="pago", entidad_id=pago.id, placa=vehicle.placa,
            actor=actor,
            nuevo={"fecha_pago": data.fecha_pago, "valor": str(data.valor), "medio": data.medio,
                   "fecha_vencimiento": vehicle.fecha_vencimiento},
            detalle=f"Primer pago de {vehicle.placa} al registrar el vehículo; "
                    f"mensualidad hasta {vehicle.fecha_vencimiento.strftime('%d/%m/%Y')}.")
    session.commit()
    session.refresh(vehicle)
    return vehicle
''')

# ---------------------------------------------------------------- tests/test_vehiculos.py
f = "backend/tests/test_vehiculos.py"
if f in textos:
    viejo = '"linea": "NMax", "fecha_pago": "2026-10-05"}'
    n = textos[f].count(viejo)
    if n != 2:
        errores.append(f"{f}: se esperaban 2 coincidencias de datos de vehiculo y hubo {n}")
    else:
        textos[f] = textos[f].replace(
            viejo, '"linea": "NMax", "fecha_pago": "2026-10-05", "valor": "120000", "medio": "EFECTIVO"}')
        textos[f] = textos[f].rstrip("\n") + '''


# ---------- RF-04: el vehículo nuevo guarda su primer pago; la fecha de pago ya no se edita ----------

DATOS_VEHICULO = {"placa": "KDT482", "color": "Gris", "modelo": 2021, "marca": "Mazda", "tipo": "CARRO",
                  "cliente_id": 1, "linea": "3", "fecha_pago": "2026-10-05", "valor": "120000",
                  "medio": "EFECTIVO"}


@pytest.mark.parametrize("campo", ["fecha_pago", "valor", "medio"])
def test_creacion_exige_los_datos_del_primer_pago(campo):
    VehiculoCrear(**DATOS_VEHICULO)
    with pytest.raises(ValidationError):
        VehiculoCrear(**{k: v for k, v in DATOS_VEHICULO.items() if k != campo})


@pytest.mark.parametrize("cambio", [{"valor": "0"}, {"valor": "-5000"}, {"valor": "12.345"}, {"valor": None},
                                    {"medio": "TARJETA"}, {"medio": None}])
def test_creacion_rechaza_primer_pago_invalido(cambio):
    with pytest.raises(ValidationError):
        VehiculoCrear(**{**DATOS_VEHICULO, **cambio})


@pytest.mark.parametrize("campo, valor", [("fecha_pago", "2026-10-05"), ("fecha_vencimiento", "2026-12-01"),
                                          ("valor", "1000"), ("medio", "QR")])
def test_actualizar_no_edita_la_mensualidad_ni_el_pago(campo, valor):
    with pytest.raises(ValidationError):
        VehiculoActualizar(**{campo: valor})
'''

# ---------------------------------------------------------------- tests/test_vehiculos_postgres.py
f = "backend/tests/test_vehiculos_postgres.py"
editar(f, "from sqlalchemy import select, text\n", "from sqlalchemy import delete, select, text\n")
editar(f, "from app.models import Auditoria\n", "from app.models import Auditoria, Operador, Pago\n")
editar(f, '''            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                def override_session():
                    yield session
                app.dependency_overrides[get_session] = override_session
                try:
                    with como(ADMIN_PRUEBA), TestClient(app) as api:
                        api.session = session
                        yield api
''', '''            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                # RF-04: el primer pago guarda al usuario que lo registra; ese usuario debe existir en operador.
                operador = Operador(nombre="Prueba vehiculos", telefono=f"3{int(uuid4().hex[:8], 16) % 10**9:09d}",
                                    usuario=f"prueba{uuid4().hex[:10]}")
                session.add(operador)
                session.flush()
                actor = ADMIN_PRUEBA.__class__(**{**ADMIN_PRUEBA.__dict__, "id": operador.id})

                def override_session():
                    yield session
                app.dependency_overrides[get_session] = override_session
                try:
                    with como(actor), TestClient(app) as api:
                        api.session = session
                        api.operador_id = operador.id
                        yield api
''')
editar(f, '''               "marca": "Prueba", "tipo": "CARRO", "cliente_id": owner.json()["id"], "linea": "Linea",
               "fecha_pago": "2026-10-05"}''', '''               "marca": "Prueba", "tipo": "CARRO", "cliente_id": owner.json()["id"], "linea": "Linea",
               "fecha_pago": "2026-10-05", "valor": "120000", "medio": "EFECTIVO"}''')
editar(f, '    for missing in ("cliente_id", "linea", "fecha_pago"):',
       '    for missing in ("cliente_id", "linea", "fecha_pago", "valor", "medio"):')
editar(f, '''    assert vehicle["fecha_vencimiento"] == "2026-11-04"
''', '''    assert vehicle["fecha_vencimiento"] == "2026-11-04"
    # RF-04: el registro del vehículo guarda su primer pago, contado desde la fecha de pago.
    primer_pago = client.session.scalars(select(Pago).where(Pago.vehiculo_id == first_id)).one()
    assert primer_pago.vencimiento_anterior is None
    assert primer_pago.vencimiento_nuevo.isoformat() == "2026-11-04"
    assert int(primer_pago.valor) == 120000 and primer_pago.medio == "EFECTIVO"
    assert primer_pago.cliente_id == owner.json()["id"] and primer_pago.operador_id == client.operador_id
    for invalido in ({"valor": "0"}, {"valor": "-5"}, {"medio": "TARJETA"}, {"fecha_pago": "2999-01-01"}):
        assert client.post("/vehiculos", json={**payload, "placa": f"{letters}999", **invalido}).status_code == 422
''')
editar(f, '{"marca": "\\t"}):', '{"marca": "\\t"},\n                    {"fecha_pago": "2026-10-05"}, {"fecha_vencimiento": "2030-01-01"}):')
editar(f, '''    deleted = client.delete(f"/vehiculos/{first_id}")
''', '''    # Los pagos son historial inmutable: un vehículo con pagos no se elimina (conflicto, no error del servidor).
    assert client.delete(f"/vehiculos/{first_id}").status_code == 409
    client.session.execute(delete(Pago).where(Pago.vehiculo_id.in_([first_id, second_id])))
    deleted = client.delete(f"/vehiculos/{first_id}")
''')

# ---------------------------------------------------------------- tests/test_pagos_postgres.py
f = "backend/tests/test_pagos_postgres.py"
editar(f, "from app.models import Auditoria, Cliente, Operador, Pago, Vehiculo\n",
       "from app.models import Auditoria, Cliente, Estancia, Novedad, Operador, Pago, Vehiculo\n")
editar(f, '''        with Session(engine) as s, s.begin():
            s.execute(delete(Pago).where(Pago.vehiculo_id.in_(ids)))
''', '''        with Session(engine) as s, s.begin():
            # Los ingresos creados por las pruebas referencian vehículo y operador (RESTRICT): se borran primero.
            estancias = select(Estancia.id).where(Estancia.vehiculo_id.in_(ids))
            s.execute(delete(Novedad).where(Novedad.estancia_id.in_(estancias)))
            s.execute(delete(Estancia).where(Estancia.vehiculo_id.in_(ids)))
            s.execute(delete(Pago).where(Pago.vehiculo_id.in_(ids)))
''')
if "backend/tests/test_pagos_postgres.py" in textos:
    textos[f] = textos[f].rstrip("\n") + '''


# ---------- RF-04: el pago habilita el ingreso ----------

def test_vehiculo_vencido_entra_despues_de_pagar(datos):
    api, headers, placa_vencida = datos['api'], datos['headers'], datos['placa']['vencido']
    antes = api.post('/estancias/entrada', json={'placa': placa_vencida}, headers=headers)
    assert antes.status_code == 409
    assert 'Mensualidad vencida' in antes.json()['detail']

    pago = pagar(datos, 'vencido')
    assert pago.status_code == 201, pago.text
    assert pago.json()['mensualidad']['estado'] == 'VIGENTE'

    consulta = api.get(f'/estancias/vehiculo/{placa_vencida}', headers=headers).json()
    assert consulta['mensualidad']['estado'] == 'VIGENTE' and consulta['puede_ingresar']

    despues = api.post('/estancias/entrada', json={'placa': placa_vencida}, headers=headers)
    assert despues.status_code == 201, despues.text
    assert despues.json()['placa'] == placa_vencida and despues.json()['abierta']
'''

# ---------------------------------------------------------------- frontend/models/vehiculo.ts
f = "frontend/src/app/models/vehiculo.ts"
editar(f, "export const TIPOS_VEHICULO", "import type { MedioPago } from './pago';\n\nexport const TIPOS_VEHICULO")
editar(f, '''/** RF-02: todo vehículo pertenece a un cliente y trae la fecha de pago de su mensualidad. */
export interface VehiculoCrear {''', '''/** RF-02 y RF-04: todo vehículo pertenece a un cliente y trae su primer pago (fecha, valor y medio). */
export interface VehiculoCrear {''')
editar(f, '''  cliente_id: number;
  fecha_pago: string;
}
export type VehiculoActualizar = Partial<VehiculoCrear>;''', '''  cliente_id: number;
  fecha_pago: string;
  valor: string;
  medio: MedioPago;
}
/** RF-04: la fecha de pago y el pago no se editan en el vehículo; la mensualidad cambia solo con un pago. */
export type VehiculoActualizar = Partial<Omit<VehiculoCrear, 'fecha_pago' | 'valor' | 'medio'>>;''')

# ---------------------------------------------------------------- frontend/pagos/pagos.ts
f = "frontend/src/app/pagos/pagos.ts"
editar(f, "const valorValido: ValidatorFn = (c) => {", "export const valorValido: ValidatorFn = (c) => {")

# ---------------------------------------------------------------- frontend/clientes/clientes.ts
f = "frontend/src/app/clientes/clientes.ts"
editar(f, "import { Cliente, ClienteDetalle, TIPOS_DOCUMENTO, TipoDocumento } from '../models/cliente';\n",
       "import { Cliente, ClienteDetalle, TIPOS_DOCUMENTO, TipoDocumento } from '../models/cliente';\n"
       "import { MEDIOS_PAGO, MedioPago } from '../models/pago';\n")
editar(f, "import { ClientesService } from '../services/clientes.service';\n",
       "import { valorValido } from '../pagos/pagos';\nimport { ClientesService } from '../services/clientes.service';\n")
editar(f, "  readonly tiposVehiculo = TIPOS_VEHICULO;\n",
       "  readonly tiposVehiculo = TIPOS_VEHICULO;\n  readonly medios = MEDIOS_PAGO;\n  readonly hoy = hoyColombia();\n")
editar(f, "    fecha_pago: [hoyColombia(), Validators.required],\n",
       "    fecha_pago: [hoyColombia(), Validators.required],\n"
       "    // RF-04: el primer pago del vehículo lleva valor y medio, igual que cualquier pago.\n"
       "    valor: ['', [noVacio, valorValido]],\n"
       "    medio: this.fb.nonNullable.control<MedioPago | ''>('', Validators.required),\n")
editar(f, "      .create({ ...raw, placa, modelo: Number(raw.modelo), cliente_id: ficha.id })\n",
       "      .create({\n        ...raw,\n        placa,\n        modelo: Number(raw.modelo),\n"
       "        valor: raw.valor.trim(),\n        medio: raw.medio as MedioPago,\n        cliente_id: ficha.id,\n      })\n")
editar(f, "            `Vehículo ${v.placa} registrado. Mensualidad vence el ${fechaDia(v.fecha_vencimiento)}.`,",
       "            `Vehículo ${v.placa} registrado con su primer pago. Mensualidad vigente hasta el ${fechaDia(v.fecha_vencimiento)}.`,")

# ---------------------------------------------------------------- frontend/clientes/clientes.html
f = "frontend/src/app/clientes/clientes.html"
editar(f, '<input id="fecha_pago" type="date" formControlName="fecha_pago" />',
       '<input id="fecha_pago" type="date" formControlName="fecha_pago" [max]="hoy" />')
editar(f, "Vence 30 días después.", "Primer pago: vence 30 días después.")
if f in textos:
    patron = re.compile(r'Primer pago: vence 30 días después\.</span>\s*</div>')
    m = patron.search(textos[f])
    if not m:
        errores.append(f"{f}: no se encontro el campo de fecha de pago")
    else:
        bloque = '''
                <div class="field">
                  <label for="valor">Valor del primer pago (pesos)</label>
                  <input
                    id="valor"
                    formControlName="valor"
                    inputmode="decimal"
                    autocomplete="off"
                    placeholder="120000"
                    [attr.aria-invalid]="invalido('vehiculo', 'valor')"
                  />
                  <span class="field-error">
                    @if (invalido('vehiculo', 'valor')) {
                      Digita un valor mayor que cero, sin puntos (ejemplo: 120000).
                    }
                  </span>
                </div>
                <div class="field">
                  <label for="medio">Medio de pago</label>
                  <select
                    id="medio"
                    formControlName="medio"
                    [attr.aria-invalid]="invalido('vehiculo', 'medio')"
                  >
                    <option value="" disabled>Elige cómo pagó…</option>
                    @for (m of medios; track m.valor) {
                      <option [value]="m.valor">{{ m.nombre }}</option>
                    }
                  </select>
                  <span class="field-error">
                    @if (invalido('vehiculo', 'medio')) {
                      Elige cómo pagó el cliente.
                    }
                  </span>
                </div>'''
        textos[f] = textos[f][:m.end()] + bloque + textos[f][m.end():]

# ---------------------------------------------------------------- frontend/clientes/clientes.spec.ts
f = "frontend/src/app/clientes/clientes.spec.ts"
editar(f, '''      color: 'Gris',
      fecha_pago: '2026-10-05',
    });
''', '''      color: 'Gris',
      fecha_pago: '2026-10-05',
      valor: '120000',
      medio: 'EFECTIVO',
    });
''')
editar(f, '''      fecha_pago: '2026-10-05',
      cliente_id: 7,
''', '''      fecha_pago: '2026-10-05',
      valor: '120000',
      medio: 'EFECTIVO',
      cliente_id: 7,
''')
editar(f, '''    expect(c.creando()).toBe(true);
    http.verify();
  });
});
''', '''    expect(c.creando()).toBe(true);
    http.verify();
  });

  it('no registra el vehículo sin el valor y el medio del primer pago (RF-04)', () => {
    const { http, c } = crear();
    c.ficha.set(ficha as never);
    c.agregarVehiculo();
    c.vehiculo.patchValue({
      placa: 'KDT482',
      marca: 'Mazda',
      linea: 'Mazda 3',
      color: 'Gris',
      fecha_pago: '2026-10-05',
    });
    c.guardarVehiculo();
    http.expectNone('/vehiculos');
    expect(c.vehiculo.controls.valor.invalid).toBe(true);
    expect(c.vehiculo.controls.medio.invalid).toBe(true);
    http.verify();
  });
});
''')

# ---------------------------------------------------------------- escribir
if errores:
    print("NO SE ESCRIBIO NINGUN ARCHIVO. Problemas:")
    for e in errores:
        print(" -", e)
    sys.exit(1)

for ruta, texto in textos.items():
    salida = texto.replace("\n", "\r\n") if crlf[ruta] else texto
    Path(ruta).write_bytes(salida.encode("utf-8"))
    print("actualizado:", ruta)
print("\nListo. Ahora corre las pruebas.")