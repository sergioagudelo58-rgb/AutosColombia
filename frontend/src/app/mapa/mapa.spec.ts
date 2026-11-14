import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Panel } from '../models/reporte';
import { sesionDePrueba } from '../testing/auth';
import { INTERVALO_PANEL_MS, Mapa } from './mapa';

const ocupacion = (estancia_id: number, placa: string) => ({
  estancia_id,
  numero_recibo: `E-${String(estancia_id).padStart(6, '0')}`,
  placa,
  tipo_vehiculo: 'CARRO',
  entrada: '2026-10-18T12:41:00Z',
  puerta: 'Puerta 2',
  operador: 'Laura',
});

function panel(): Panel {
  return {
    generado_en: '2026-10-18T12:41:30Z',
    cupos: [
      {
        tipo_celda: 'CARRO_CAMIONETA',
        nombre: 'carros y camionetas',
        total: 3,
        ocupadas: 2,
        disponibles: 1,
      },
      { tipo_celda: 'MOTO', nombre: 'motos', total: 1, ocupadas: 0, disponibles: 1 },
    ],
    celdas: [
      {
        id: 25,
        codigo: '25',
        tipo: 'CARRO_CAMIONETA',
        estado: 'OCUPADA',
        reciente: true,
        ocupacion: ocupacion(7, 'KDT482'),
      },
      {
        id: 26,
        codigo: '26',
        tipo: 'CARRO_CAMIONETA',
        estado: 'OCUPADA',
        reciente: false,
        ocupacion: ocupacion(8, 'JPX905'),
      },
      {
        id: 30,
        codigo: '30',
        tipo: 'CARRO_CAMIONETA',
        estado: 'DISPONIBLE',
        reciente: false,
        ocupacion: null,
      },
      {
        id: 71,
        codigo: '71',
        tipo: 'MOTO',
        estado: 'DISPONIBLE',
        reciente: false,
        ocupacion: null,
      },
    ],
    actividad: [
      {
        tipo: 'ENTRADA',
        fecha: '2026-10-18T12:41:00Z',
        placa: 'KDT482',
        celda: '25',
        puerta: 'Puerta 2',
        operador: 'Laura',
        detalle: 'Ingresó a la celda 25 · E-000007',
      },
    ],
  };
}

describe('Mapa de celdas', () => {
  let http: HttpTestingController;
  let c: Mapa;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({
      imports: [Mapa],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        sesionDePrueba('OPERADOR', { id: 1, nombre: 'Puerta 1' }),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    c = TestBed.createComponent(Mapa).componentInstance;
    vi.advanceTimersByTime(0);
    http.expectOne('/panel').flush(panel());
  });
  afterEach(() => {
    http.verify();
    vi.useRealTimers();
  });

  it('se actualiza solo cada 2 segundos sin recargar (RNF-02)', () => {
    expect(c.celdasPorTipo()[0].celdas.length).toBe(3);
    const siguiente = panel();
    siguiente.celdas[2] = {
      ...siguiente.celdas[2],
      estado: 'OCUPADA',
      reciente: true,
      ocupacion: ocupacion(9, 'AAA111'),
    };
    vi.advanceTimersByTime(INTERVALO_PANEL_MS);
    http.expectOne('/panel').flush(siguiente);
    expect(c.panel()?.celdas[2].ocupacion?.placa).toBe('AAA111');
  });

  it('conserva el último estado y avisa si se pierde la conexión', () => {
    vi.advanceTimersByTime(INTERVALO_PANEL_MS);
    http.expectOne('/panel').flush(null, { status: 503, statusText: 'Unavailable' });
    expect(c.sinConexion()).toBe(true);
    expect(c.panel()?.celdas.length).toBe(4);
  });

  it('muestra el detalle de una celda ocupada y describe su estado con texto', () => {
    const celda = c.panel()!.celdas[0];
    c.seleccionar(celda);
    expect(c.seleccion()?.ocupacion?.placa).toBe('KDT482');
    expect(c.etiqueta(celda)).toBe('Celda 25, recién asignada por KDT482');
    // Solo se ofrecen celdas del mismo tipo como destino.
    expect(c.destinos().map((d) => d.id)).toEqual([26, 30]);
  });

  it('cambia a una celda libre con motivo y el operador del turno', () => {
    c.seleccionar(c.panel()!.celdas[0]);
    c.abrirCambio();
    c.form.setValue({
      celdaId: 30,
      motivo: '  El conductor parqueó en la 30 ',
      intercambiar: false,
    });
    c.confirmarCambio();
    const req = http.expectOne('/estancias/7/celda');
    expect(req.request.body).toEqual({
      celda_id: 30,
      motivo: 'El conductor parqueó en la 30',
      intercambiar: false,
    });
    req.flush({
      estancia: { placa: 'KDT482', celda: { id: 30, codigo: '30', tipo: 'CARRO_CAMIONETA' } },
      intercambio: null,
    });
    http.expectOne('/panel').flush(panel());
    expect(c.exito()).toContain('KDT482 pasó a la celda 30');
  });

  it('exige el motivo y pide confirmar el intercambio si la celda está ocupada', () => {
    c.seleccionar(c.panel()!.celdas[0]);
    c.abrirCambio();
    c.form.setValue({ celdaId: 26, motivo: '', intercambiar: false });
    c.confirmarCambio();
    http.expectNone('/estancias/7/celda');
    c.form.controls.motivo.setValue('Celda asignada ocupada');
    c.confirmarCambio();
    expect(c.error()).toContain('Intercambiar celdas');
    http.expectNone('/estancias/7/celda');
    c.form.controls.intercambiar.setValue(true);
    c.confirmarCambio();
    const req = http.expectOne('/estancias/7/celda');
    expect(req.request.body.intercambiar).toBe(true);
    req.flush({
      estancia: { placa: 'KDT482', celda: { id: 26, codigo: '26' } },
      intercambio: { placa: 'JPX905', celda: { id: 25, codigo: '25' } },
    });
    http.expectOne('/panel').flush(panel());
    expect(c.exito()).toBe('Celdas intercambiadas: KDT482 → 26 y JPX905 → 25.');
  });
});
