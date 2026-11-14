import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { reglasContrasena } from '../models/auth';
import { authInterceptor } from './auth.interceptor';
import { AuthService } from './auth.service';
import { CambiarContrasena } from './cambiar-contrasena';
import { Login } from './login';

const sesion = {
  usuario_id: 7,
  usuario: 'drios',
  nombre: 'Diana Ríos',
  rol: 'OPERADOR' as const,
  puerta_id: 2,
  puerta: 'Puerta 2',
  contrasena_temporal: false,
  inactividad_segundos: 900,
};

describe('Sesión (RF-01, RF-05)', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        provideRouter([]),
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    TestBed.resetTestingModule();
    localStorage.clear();
  });

  it('ingresa con usuario, contraseña y puerta, y luego envía el token en cada solicitud', () => {
    const c = TestBed.createComponent(Login).componentInstance;
    http.expectOne('/puertas').flush([{ id: 2, nombre: 'Puerta 2' }]);
    c.form.setValue({ usuario: ' drios ', contrasena: 'Portero2026', puerta: 2 });
    c.ingresar();
    const req = http.expectOne('/auth/login');
    expect(req.request.body).toEqual({ usuario: 'drios', contrasena: 'Portero2026', puerta_id: 2 });
    expect(req.request.headers.has('Authorization')).toBe(false);
    req.flush({ ...sesion, token: 'abc' });
    const auth = TestBed.inject(AuthService);
    expect(auth.sesion()?.puerta).toBe('Puerta 2');
    TestBed.inject(HttpClient).get('/panel').subscribe();
    expect(http.expectOne('/panel').request.headers.get('Authorization')).toBe('Bearer abc');
  });

  it('muestra el mensaje genérico del servidor y no guarda la contraseña escrita', () => {
    const c = TestBed.createComponent(Login).componentInstance;
    http.expectOne('/puertas').flush([]);
    c.form.setValue({ usuario: 'drios', contrasena: 'mala', puerta: 2 });
    c.ingresar();
    http
      .expectOne('/auth/login')
      .flush({ detail: 'Usuario o contraseña incorrectos.' }, { status: 401, statusText: 'x' });
    expect(c.error()).toBe('Usuario o contraseña incorrectos.');
    expect(c.form.controls.contrasena.value).toBe('');
  });

  it('si el servidor cierra la sesión vuelve al ingreso con el motivo', () => {
    localStorage.setItem('autos-colombia.sesion', JSON.stringify({ token: 't', sesion }));
    const auth = TestBed.inject(AuthService);
    const navegar = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    TestBed.inject(HttpClient)
      .get('/panel')
      .subscribe({ error: () => undefined });
    http
      .expectOne('/panel')
      .flush(
        { detail: 'Usuario inactivo. Comuníquese con el administrador.' },
        { status: 401, statusText: 'x' },
      );
    expect(auth.activa()).toBe(false);
    expect(auth.aviso()).toBe('Usuario inactivo. Comuníquese con el administrador.');
    expect(navegar).toHaveBeenCalledWith(['/ingresar']);
  });

  it('la política de contraseña guía mientras se escribe (RNF-02)', () => {
    expect(
      reglasContrasena('corta', 'drios')
        .filter((r) => !r.cumple)
        .map((r) => r.texto),
    ).toEqual(['Mínimo 8 caracteres', 'Una letra mayúscula', 'Un número']);
    expect(reglasContrasena('Drios2026', 'drios').every((r) => r.cumple)).toBe(true);
    expect(reglasContrasena('Drios2026', 'drios2026').some((r) => !r.cumple)).toBe(true);
  });

  it('con contraseña temporal solo deja guardar una contraseña que cumpla la política', () => {
    localStorage.setItem(
      'autos-colombia.sesion',
      JSON.stringify({ token: 't', sesion: { ...sesion, contrasena_temporal: true } }),
    );
    const c = TestBed.createComponent(CambiarContrasena).componentInstance;
    expect(c.temporal()).toBe(true);
    c.form.setValue({ actual: 'Temporal99', nueva: 'debil', confirmacion: 'debil' });
    expect(c.valida()).toBe(false);
    c.form.setValue({ actual: 'Temporal99', nueva: 'Nueva2026x', confirmacion: 'Nueva2026x' });
    expect(c.valida()).toBe(true);
    vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    c.guardar();
    http.expectOne('/auth/cambiar-contrasena').flush({ ...sesion, contrasena_temporal: false });
    expect(TestBed.inject(AuthService).debeCambiarClave()).toBe(false);
  });
});
