import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';

/** Pantallas con sesión abierta y contraseña definitiva. */
export const conSesion: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (!auth.activa()) return router.parseUrl('/ingresar');
  if (auth.debeCambiarClave()) return router.parseUrl('/cambiar-contrasena');
  return true;
};

/** RF-02: el menú no muestra estas opciones al operador y la ruta tampoco se abre escribiéndola. */
export const soloAdmin: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (!auth.esAdmin()) {
    auth.accesoDenegado(state.url);
    return router.parseUrl('/sin-permiso');
  }
  return true;
};

export const sinSesion: CanActivateFn = () => {
  const auth = inject(AuthService);
  return auth.activa() && !auth.debeCambiarClave() ? inject(Router).parseUrl('/') : true;
};

export const conSesionTemporal: CanActivateFn = () =>
  inject(AuthService).activa() ? true : inject(Router).parseUrl('/ingresar');
