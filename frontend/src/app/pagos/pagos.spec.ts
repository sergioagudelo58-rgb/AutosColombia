import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { sesionDePrueba } from '../testing/auth';
import { Pagos, normalizarCedula } from './pagos';

describe('Registrar pago (RF-01, RF-03)', () => {
  let http: HttpTestingController;
  let c: Pagos;
  let el: HTMLElement;
  let fixture: ComponentFixture<Pagos>;
  const mensualidad = (estado: string, vence: string | null, mensaje: string) => ({
    estado,
    fecha_pago: null,
    fecha_vencimiento: vence,
    dias: null,
    permite_ingreso: estado === 'VIGENTE',
    mensaje,
  });
  const consulta = {
    cliente: { id: 7, tipo_documento: 'CC', numero_documento: '1036458221', nombres: 'Laura', apellidos: 'Gómez' },
    vehiculo: { id: 9, placa: 'KDT482', tipo: 'CARRO', marca: 'Mazda', linea: '3', cliente_id: 7 },
    mensualidad: mensualidad('VENCIDA', '2026-11-01', 'Mensualidad vencida hace 4 días (venció el 01/11/2026).'),
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [Pagos],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        sesionDePrueba('OPERADOR'),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Pagos);
    c = fixture.componentInstance;
    el = fixture.nativeElement;
    fixture.detectChanges();
  });
  afterEach(() => {
    http.verify();
  });

  function buscar() {
    c.busqueda.setValue({ cedula: '1.036.458.221', placa: 'kdt 482' });
    c.buscar();
    return http.expectOne((r) => r.url === '/pagos/consulta');
  }

  it('normaliza la cédula como el servidor', () => {
    expect(normalizarCedula(' 1.036.458-221 ')).toBe('1036458221');
  });

  it('busca por cédula y placa y muestra hasta cuándo va la mensualidad', () => {
    const req = buscar();
    expect(req.request.params.get('cedula')).toBe('1036458221');
    expect(req.request.params.get('placa')).toBe('KDT482');
    req.flush(consulta);
    fixture.detectChanges();
    expect(c.consulta()?.vehiculo.placa).toBe('KDT482');
    expect(el.textContent).toContain('Mensualidad vencida hace 4 días');
    expect(el.textContent).toContain('01/11/2026');
  });

  for (const detalle of [
    'El cliente no está registrado.',
    'El vehículo no está registrado.',
    'El vehículo no pertenece a este cliente.',
  ]) {
    it(`muestra la notificación «${detalle}»`, () => {
      buscar().flush({ detail: detalle }, { status: detalle.includes('pertenece') ? 409 : 404, statusText: 'x' });
      expect(c.error()).toBe(detalle);
      expect(c.consulta()).toBeNull();
      fixture.detectChanges();
      expect(el.querySelector('[role="alert"]')?.textContent).toContain(detalle);
    });
  }

  it('no registra sin fecha, valor y medio', () => {
    buscar().flush(consulta);
    c.pago.patchValue({ fecha_pago: '', valor: '0', medio: '' });
    c.registrar();
    http.expectNone('/pagos');
    expect(c.pago.invalid).toBe(true);
  });

  it('no acepta una fecha de pago futura', () => {
    buscar().flush(consulta);
    c.pago.patchValue({ fecha_pago: '2999-01-01', valor: '120000', medio: 'EFECTIVO' });
    c.registrar();
    http.expectNone('/pagos');
  });

  it('registra el pago y muestra «Mensualidad vigente hasta…»', () => {
    buscar().flush(consulta);
    c.pago.patchValue({ fecha_pago: '2026-11-05', valor: ' 120000 ', medio: 'QR' });
    c.registrar();
    const req = http.expectOne('/pagos');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      cedula: '1036458221',
      placa: 'KDT482',
      fecha_pago: '2026-11-05',
      valor: '120000',
      medio: 'QR',
    });
    req.flush({
      id: 1,
      cedula: '1036458221',
      cliente: 'Laura Gómez',
      placa: 'KDT482',
      fecha_pago: '2026-11-05',
      valor: '120000.00',
      medio: 'QR',
      vencimiento_anterior: '2026-11-01',
      vencimiento_nuevo: '2026-12-01',
      registrado_por: 'drios',
      registrado_en: '2026-11-05T15:00:00Z',
      mensualidad: mensualidad('VIGENTE', '2026-12-01', 'Mensualidad vigente hasta 01/12/2026.'),
    });
    expect(c.registrado()?.vencimiento_nuevo).toBe('2026-12-01');
    fixture.detectChanges();
    expect(el.querySelector('[role="status"]')?.textContent).toContain(
      'Mensualidad vigente hasta 01/12/2026.',
    );
    expect(c.consulta()).toBeNull();
  });

  it('si cambia la placa después de buscar, hay que volver a buscar', () => {
    buscar().flush(consulta);
    c.busqueda.controls.placa.setValue('ABC123');
    expect(c.consulta()).toBeNull();
  });
});
