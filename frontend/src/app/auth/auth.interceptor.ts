import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from './auth.service';

/** Envía el token en cada solicitud y reacciona cuando el servidor cierra o limita la sesión. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const token = auth.token();
  const peticion = token ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;
  return next(peticion).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse && !req.url.endsWith('/auth/login')) {
        if (error.status === 401 && token) {
          const detalle = typeof error.error?.detail === 'string' ? error.error.detail : '';
          auth.terminar(detalle || 'Tu sesión terminó. Ingresa de nuevo.');
        } else if (
          error.status === 403 &&
          error.headers.get('X-Motivo-Sesion') === 'CONTRASENA_TEMPORAL'
        ) {
          void router.navigate(['/cambiar-contrasena']);
        }
      }
      return throwError(() => error);
    }),
  );
};
