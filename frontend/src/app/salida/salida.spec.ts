import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { TurnoService } from '../shared/turno.service';
import { Salida, busquedaSalida, normalizarRecibo } from './salida';

describe('Registrar salida', () => {
  let http: HttpTestingController;
  let c: Salida;
  const estancia = {
    id: 3,
    numero_recibo: 'E-000003',
    placa: 'ABC123',
    celda: { id: 12, codigo: '12', tipo: 'CARRO_CAMIONETA' },
    abierta: true,
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [Salida],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
    TestBed.inject(TurnoService).iniciar({
      operador: { id: 4, nombre: 'Laura' },
      puerta: { id: 2, nombre: 'Puerta 2' },
    });
    c = TestBed.createComponent(Salida).componentInstance;
  });
  afterEach(() => {
    TestBed.inject(TurnoService).cerrar();
    http.verify();
  });

  it('distingue placa y número de recibo', () => {
    expect(busquedaSalida('abc 123')).toEqual({ placa: 'ABC123' });
    expect(busquedaSalida('e231')).toEqual({ recibo: 'E-000231' });
    expect(busquedaSalida('E-000231')).toEqual({ recibo: 'E-000231' });
    expect(busquedaSalida('ZZ')).toBeNull();
    expect(normalizarRecibo('0')).toBeNull();
  });

  it('busca por placa y cierra con el operador y la puerta del turno', () => {
    c.form.controls.busqueda.setValue('abc 123');
    c.buscar();
    http.expectOne('/estancias/abierta?placa=ABC123').flush(estancia);
    c.confirmar();
    const req = http.expectOne('/estancias/salida');
    expect(req.request.body).toEqual({
      placa: 'ABC123',
      numero_recibo: 'E-000003',
      operador_id: 4,
      puerta_id: 2,
    });
    req.flush({ ...estancia, abierta: false, salida: '2026-10-18T20:00:00Z' });
    expect(c.salida()?.celda.codigo).toBe('12');
  });

  it('busca por número de recibo', () => {
    c.form.controls.busqueda.setValue('e3');
    c.buscar();
    http.expectOne('/estancias/abierta?recibo=E-000003').flush(estancia);
    expect(c.registro()?.placa).toBe('ABC123');
    expect(c.form.controls.busqueda.value).toBe('E-000003');
  });

  it('avisa cuando el vehículo no tiene ingreso abierto', () => {
    c.form.controls.busqueda.setValue('ABC123');
    c.buscar();
    http
      .expectOne('/estancias/abierta?placa=ABC123')
      .flush(
        { detail: 'Este vehículo no tiene un ingreso abierto.' },
        { status: 409, statusText: 'Conflict' },
      );
    expect(c.error()).toBe('Este vehículo no tiene un ingreso abierto.');
    c.confirmar();
    http.expectNone('/estancias/salida');
  });

  it('no consulta si el texto no es placa ni recibo', () => {
    c.form.controls.busqueda.setValue('hola');
    c.buscar();
    http.expectNone((r) => r.url.startsWith('/estancias'));
    expect(c.form.invalid).toBe(true);
  });
});
