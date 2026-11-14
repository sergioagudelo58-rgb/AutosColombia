import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { sesionDePrueba } from '../testing/auth';
import { Usuarios } from './usuarios';

const usuario = {
  id: 9,
  usuario: 'drios',
  nombre: 'Diana Ríos',
  nombres: 'Diana',
  apellidos: 'Ríos',
  tipo_documento: 'CC',
  numero_documento: '1036458221',
  telefono: '3001234567',
  correo: null,
  rol: 'OPERADOR',
  estado: 'ACTIVO',
  fecha_ingreso: '2026-11-01',
  fecha_retiro: null,
  motivo_retiro: null,
  ultima_conexion: null,
  en_linea: true,
  puerta: 'Puerta 2',
  bloqueado: false,
  contrasena_temporal: true,
  sin_contrasena: false,
};

describe('Usuarios (RF-04 a RF-07)', () => {
  let http: HttpTestingController;
  let c: Usuarios;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({
      imports: [Usuarios],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        sesionDePrueba('ADMINISTRADOR', null),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    c = TestBed.createComponent(Usuarios).componentInstance;
    vi.advanceTimersByTime(0);
    http.expectOne('/usuarios?estado=ACTIVO').flush({ items: [usuario], total: 1, en_linea: 1 });
  });
  afterEach(() => {
    http.verify();
    vi.useRealTimers();
  });

  it('lista con «en línea» y se actualiza sola', () => {
    expect(c.enLinea()).toBe(1);
    vi.advanceTimersByTime(5000);
    http.expectOne('/usuarios?estado=ACTIVO').flush({ items: [], total: 0, en_linea: 0 });
    expect(c.items()).toEqual([]);
  });

  it('crea el usuario y muestra la contraseña temporal una sola vez', () => {
    c.nuevo();
    c.form.setValue({
      tipo_documento: 'CC',
      numero_documento: '1036458221',
      nombres: 'Diana',
      apellidos: 'Ríos',
      telefono: '3001234567',
      correo: '',
      usuario: ' DRios ',
      rol: 'OPERADOR',
      fecha_ingreso: '2026-11-01',
    });
    c.guardar();
    const req = http.expectOne('/usuarios');
    expect(req.request.body.usuario).toBe('drios');
    expect(req.request.body.correo).toBeNull();
    req.flush({ ...usuario, contrasena_generada: 'Ab3kP9xQ2m' });
    http.expectOne('/usuarios?estado=ACTIVO').flush({ items: [usuario], total: 1, en_linea: 1 });
    expect(c.temporal()?.contrasena_generada).toBe('Ab3kP9xQ2m');
    c.editar(c.items()[0]);
    expect(c.temporal()).toBeNull();
    expect(c.form.controls.usuario.disabled).toBe(true);
  });

  it('retirar exige motivo', () => {
    c.pedir('retirar', c.items()[0]);
    c.confirmar();
    http.expectNone('/usuarios/9/retirar');
    c.retiro.setValue({ motivo: 'Terminó su contrato', fecha_retiro: '2026-11-30' });
    c.confirmar();
    expect(http.expectOne('/usuarios/9/retirar').request.body).toEqual({
      motivo: 'Terminó su contrato',
      fecha_retiro: '2026-11-30',
    });
  });
});
