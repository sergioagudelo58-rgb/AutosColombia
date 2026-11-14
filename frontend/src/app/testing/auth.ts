import { Provider, computed, signal } from '@angular/core';
import { AuthService } from '../auth/auth.service';
import { Rol, Sesion } from '../models/auth';

/** Sesión fija para las pruebas de componentes: sin token real ni consultas periódicas. */
export function sesionDePrueba(
  rol: Rol = 'OPERADOR',
  puerta: { id: number; nombre: string } | null = { id: 2, nombre: 'Puerta 2' },
): Provider {
  const sesion = signal<Sesion | null>({
    usuario_id: 4,
    usuario: 'lgomez',
    nombre: 'Laura Gómez',
    rol,
    puerta_id: puerta?.id ?? null,
    puerta: puerta?.nombre ?? null,
    contrasena_temporal: false,
    inactividad_segundos: 900,
  });
  const falso: Partial<AuthService> = {
    sesion: sesion.asReadonly(),
    activa: computed(() => sesion() !== null),
    esAdmin: computed(() => sesion()?.rol === 'ADMINISTRADOR'),
    debeCambiarClave: computed(() => false),
    aviso: signal(''),
    token: () => 'token-de-prueba',
    logout: () => sesion.set(null),
  };
  return { provide: AuthService, useValue: falso };
}
