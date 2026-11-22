import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { Clientes } from './clientes';

const ficha = {
  id: 7,
  tipo_documento: 'CC',
  numero_documento: '1036458221',
  nombres: 'Laura',
  apellidos: 'Gómez',
  telefono: '3001234567',
  correo: null,
  fecha_registro: '2026-10-18T10:00:00Z',
  vehiculos: [],
};

function crear(placa: string | null = null) {
  TestBed.configureTestingModule({
    imports: [Clientes],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([]),
      {
        provide: ActivatedRoute,
        useValue: { snapshot: { queryParamMap: convertToParamMap(placa ? { placa } : {}) } },
      },
    ],
  });
  const http = TestBed.inject(HttpTestingController);
  const c = TestBed.createComponent(Clientes).componentInstance;
  http
    .expectOne((r) => r.url === '/clientes' && r.method === 'GET')
    .flush({ items: [], total: 0, offset: 0, limit: 20 });
  return { http, c };
}

describe('Clientes y vehículos', () => {
  it('registra el cliente y luego su vehículo con la fecha de pago', () => {
    const { http, c } = crear();
    c.nuevoCliente();
    c.cliente.setValue({
      tipo_documento: 'CC',
      numero_documento: '1036458221',
      nombres: 'Laura',
      apellidos: 'Gómez',
      telefono: '3001234567',
      correo: '',
    });
    c.guardarCliente();
    const alta = http.expectOne((r) => r.url === '/clientes' && r.method === 'POST');
    expect(alta.request.body.correo).toBeNull();
    alta.flush(ficha);
    http
      .expectOne((r) => r.url === '/clientes' && r.method === 'GET')
      .flush({ items: [ficha], total: 1, offset: 0, limit: 20 });
    http.expectOne('/clientes/7').flush(ficha);
    expect(c.ficha()?.id).toBe(7);

    c.agregarVehiculo();
    c.vehiculo.setValue({
      placa: 'kdt-482',
      tipo: 'CARRO',
      marca: 'Mazda',
      linea: 'Mazda 3',
      modelo: 2021,
      color: 'Gris',
      fecha_pago: '2026-10-05',
      valor: '120000',
      medio: 'EFECTIVO',
    });
    c.guardarVehiculo();
    const vehiculo = http.expectOne('/vehiculos');
    expect(vehiculo.request.body).toEqual({
      placa: 'KDT482',
      tipo: 'CARRO',
      marca: 'Mazda',
      linea: 'Mazda 3',
      modelo: 2021,
      color: 'Gris',
      fecha_pago: '2026-10-05',
      valor: '120000',
      medio: 'EFECTIVO',
      cliente_id: 7,
    });
    vehiculo.flush({ id: 1, placa: 'KDT482', fecha_vencimiento: '2026-11-04' });
    http.expectOne('/clientes/7').flush(ficha);
    expect(c.exito()).toContain('04/11/2026');
    http.verify();
  });

  it('si el documento ya existe, abre la información del cliente', () => {
    const { http, c } = crear();
    c.nuevoCliente();
    c.cliente.patchValue({
      numero_documento: '1036458221',
      nombres: 'Laura',
      apellidos: 'Gómez',
      telefono: '3001234567',
    });
    c.guardarCliente();
    http
      .expectOne((r) => r.url === '/clientes' && r.method === 'POST')
      .flush(
        { detail: 'El cliente ya está registrado.', cliente_id: 7 },
        { status: 409, statusText: 'Conflict' },
      );
    http.expectOne('/clientes/7').flush(ficha);
    expect(c.ficha()?.id).toBe(7);
    expect(c.exito()).toBe('El cliente ya está registrado.');
    http.verify();
  });

  it('trae la placa no registrada desde la entrada para el nuevo vehículo', () => {
    const { http, c } = crear('abc123');
    expect(c.placaPendiente()).toBe('ABC123');
    expect(c.creando()).toBe(true);
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
    // RN-12: el valor llega con la tarifa del tipo; el operario debe elegir el medio de pago.
    expect(c.vehiculo.controls.valor.valid).toBe(true);
    c.guardarVehiculo();
    http.expectNone('/vehiculos');
    expect(c.vehiculo.controls.medio.invalid).toBe(true);
    // Si el operario borra el valor, tampoco se registra.
    c.vehiculo.patchValue({ valor: '', medio: 'EFECTIVO' });
    c.guardarVehiculo();
    http.expectNone('/vehiculos');
    expect(c.vehiculo.controls.valor.invalid).toBe(true);
    http.verify();
  });
});
