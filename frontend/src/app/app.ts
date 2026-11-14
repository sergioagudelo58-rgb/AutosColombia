import { Component, computed, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from './auth/auth.service';
import { NOMBRE_ROL } from './models/auth';

interface Opcion {
  ruta: string;
  texto: string;
  soloAdmin: boolean;
}

/** RF-02: el menú muestra solo las opciones del perfil. */
const OPCIONES: Opcion[] = [
  { ruta: '/operacion/entrada', texto: 'Entrada', soloAdmin: false },
  { ruta: '/operacion/salida', texto: 'Salida', soloAdmin: false },
  { ruta: '/operacion/celdas', texto: 'Mapa', soloAdmin: false },
  { ruta: '/gestion/clientes', texto: 'Nuevo vehículo', soloAdmin: false },
  { ruta: '/gestion/usuarios', texto: 'Usuarios', soloAdmin: true },
  { ruta: '/gestion/celdas', texto: 'Celdas', soloAdmin: true },
  { ruta: '/gestion/reportes', texto: 'Reportes', soloAdmin: true },
  { ruta: '/gestion/auditoria', texto: 'Auditoría', soloAdmin: true },
];

@Component({
  selector: 'app-root',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  readonly auth = inject(AuthService);
  readonly nombreRol = NOMBRE_ROL;
  readonly menu = computed(() =>
    this.auth.activa() && !this.auth.debeCambiarClave()
      ? OPCIONES.filter((o) => !o.soloAdmin || this.auth.esAdmin())
      : [],
  );
}
