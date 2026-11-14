import { Routes } from '@angular/router';
import { conSesion, conSesionTemporal, sinSesion, soloAdmin } from './auth/auth.guards';

// Las rutas de pantalla no coinciden con las de la API (/estancias, /clientes…) para no chocar con el proxy.
// RF-02: las pantallas de administración exigen el perfil Administrador; el servidor lo vuelve a validar.
export const routes: Routes = [
  {
    path: 'ingresar',
    title: 'Iniciar sesión | Autos Colombia',
    canActivate: [sinSesion],
    loadComponent: () => import('./auth/login').then((m) => m.Login),
  },
  {
    path: 'cambiar-contrasena',
    title: 'Cambiar contraseña | Autos Colombia',
    canActivate: [conSesionTemporal],
    loadComponent: () => import('./auth/cambiar-contrasena').then((m) => m.CambiarContrasena),
  },
  {
    path: '',
    canActivateChild: [conSesion],
    children: [
      {
        path: '',
        pathMatch: 'full',
        loadComponent: () => import('./home/home').then((m) => m.Home),
      },
      {
        path: 'sin-permiso',
        title: 'Sin permiso | Autos Colombia',
        loadComponent: () => import('./auth/sin-permiso').then((m) => m.SinPermiso),
      },
      {
        path: 'operacion/entrada',
        title: 'Registrar entrada | Autos Colombia',
        loadComponent: () => import('./entrada/entrada').then((m) => m.Entrada),
      },
      {
        path: 'operacion/salida',
        title: 'Registrar salida | Autos Colombia',
        loadComponent: () => import('./salida/salida').then((m) => m.Salida),
      },
      {
        path: 'operacion/celdas',
        title: 'Mapa de celdas | Autos Colombia',
        loadComponent: () => import('./mapa/mapa').then((m) => m.Mapa),
      },
      {
        path: 'gestion/clientes',
        title: 'Clientes y vehículos | Autos Colombia',
        loadComponent: () => import('./clientes/clientes').then((m) => m.Clientes),
      },
      {
        path: 'gestion',
        canActivateChild: [soloAdmin],
        children: [
          {
            path: 'usuarios',
            title: 'Usuarios | Autos Colombia',
            loadComponent: () => import('./usuarios/usuarios').then((m) => m.Usuarios),
          },
          {
            path: 'celdas',
            title: 'Celdas | Autos Colombia',
            loadComponent: () => import('./celdas/celdas').then((m) => m.Celdas),
          },
          {
            path: 'reportes',
            title: 'Reportes | Autos Colombia',
            loadComponent: () => import('./reportes/reportes').then((m) => m.Reportes),
          },
        ],
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
