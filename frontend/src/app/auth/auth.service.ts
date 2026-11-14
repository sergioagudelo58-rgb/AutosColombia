import { HttpClient } from '@angular/common/http';
import { DestroyRef, Injectable, NgZone, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, tap, timeout } from 'rxjs';
import { CambioContrasena, LoginCrear, LoginRespuesta, Sesion } from '../models/auth';
import { API_BASE_URL } from '../services/api.service';

const CLAVE = 'autos-colombia.sesion';
const CONSULTA_MS = 5000;

interface Guardado {
  token: string;
  sesion: Sesion;
}

/**
 * Sesión del usuario (RF-01 a RF-03). El token se guarda en el navegador; en la base solo queda su hash.
 * Cada 5 s se consulta el estado de la sesión (sin contar como actividad) para cerrar la pantalla si el
 * administrador retiró al usuario o cerró su sesión (RNF-04), y tras 15 minutos sin actividad se cierra.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly zone = inject(NgZone);
  private readonly base = `${inject(API_BASE_URL)}/auth`;
  private readonly estado = signal<Guardado | null>(this.leer());
  private consulta?: ReturnType<typeof setInterval>;
  private inactividad?: ReturnType<typeof setTimeout>;

  readonly sesion = computed(() => this.estado()?.sesion ?? null);
  readonly activa = computed(() => this.estado() !== null);
  readonly esAdmin = computed(() => this.sesion()?.rol === 'ADMINISTRADOR');
  readonly debeCambiarClave = computed(() => !!this.sesion()?.contrasena_temporal);
  /** Mensaje que la pantalla de ingreso muestra al volver (sesión vencida, retirado…). */
  readonly aviso = signal('');

  constructor() {
    const reiniciar = () => this.reiniciarInactividad();
    for (const evento of ['click', 'keydown', 'pointerdown', 'touchstart']) {
      window.addEventListener(evento, reiniciar, { passive: true });
    }
    inject(DestroyRef).onDestroy(() => {
      for (const evento of ['click', 'keydown', 'pointerdown', 'touchstart']) {
        window.removeEventListener(evento, reiniciar);
      }
      this.detener();
    });
    if (this.estado()) this.vigilar();
  }

  token(): string | null {
    return this.estado()?.token ?? null;
  }

  login(datos: LoginCrear): Observable<LoginRespuesta> {
    return this.http.post<LoginRespuesta>(`${this.base}/login`, datos).pipe(
      timeout(15000),
      tap(({ token, ...sesion }) => {
        this.guardar({ token, sesion });
        this.aviso.set('');
        this.vigilar();
      }),
    );
  }

  logout(): void {
    if (this.token()) {
      this.http.post(`${this.base}/logout`, {}).subscribe({ error: () => undefined });
    }
    this.terminar('Cerraste la sesión.');
  }

  cambiarContrasena(datos: CambioContrasena): Observable<Sesion> {
    return this.http.post<Sesion>(`${this.base}/cambiar-contrasena`, datos).pipe(
      timeout(15000),
      tap((sesion) => this.actualizar(sesion)),
    );
  }

  /** El administrador elige la puerta del turno que cubre. */
  cambiarPuerta(puertaId: number | null): Observable<Sesion> {
    return this.http.patch<Sesion>(`${this.base}/sesion`, { puerta_id: puertaId }).pipe(
      timeout(15000),
      tap((sesion) => this.actualizar(sesion)),
    );
  }

  /** RF-02: el intento de abrir una pantalla sin permiso queda en la auditoría. */
  accesoDenegado(ruta: string): void {
    this.http.post(`${this.base}/acceso-denegado`, { ruta }).subscribe({ error: () => undefined });
  }

  /** La sesión ya no es válida en el servidor: se limpia y se vuelve al ingreso con el motivo. */
  terminar(mensaje: string): void {
    const habia = this.estado() !== null;
    this.detener();
    this.guardar(null);
    this.aviso.set(mensaje);
    if (habia || !this.router.url.startsWith('/ingresar')) void this.router.navigate(['/ingresar']);
  }

  private actualizar(sesion: Sesion): void {
    const actual = this.estado();
    if (actual) this.guardar({ ...actual, sesion });
  }

  private vigilar(): void {
    this.detener();
    this.reiniciarInactividad();
    this.zone.runOutsideAngular(() => {
      this.consulta = setInterval(
        () =>
          this.zone.run(() =>
            this.http
              .get<Sesion>(`${this.base}/sesion`)
              .subscribe({ next: (s) => this.actualizar(s), error: () => undefined }),
          ),
        CONSULTA_MS,
      );
    });
  }

  private reiniciarInactividad(): void {
    const sesion = this.sesion();
    clearTimeout(this.inactividad);
    if (!sesion) return;
    this.zone.runOutsideAngular(() => {
      this.inactividad = setTimeout(
        () =>
          this.zone.run(() => {
            this.http.post(`${this.base}/logout`, {}).subscribe({ error: () => undefined });
            this.terminar('Tu sesión se cerró tras 15 minutos sin actividad. Ingresa de nuevo.');
          }),
        sesion.inactividad_segundos * 1000,
      );
    });
  }

  private detener(): void {
    clearInterval(this.consulta);
    clearTimeout(this.inactividad);
  }

  private guardar(valor: Guardado | null): void {
    this.estado.set(valor);
    try {
      if (valor) localStorage.setItem(CLAVE, JSON.stringify(valor));
      else localStorage.removeItem(CLAVE);
    } catch {
      // Sin almacenamiento, la sesión dura mientras la pestaña esté abierta.
    }
  }

  private leer(): Guardado | null {
    try {
      const valor = JSON.parse(localStorage.getItem(CLAVE) ?? 'null');
      if (typeof valor?.token === 'string' && typeof valor?.sesion?.usuario === 'string')
        return valor;
    } catch {
      // Valor ausente o dañado: se pide ingresar de nuevo.
    }
    return null;
  }
}
