import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

/** RF-02: pantalla que ve quien intenta abrir una función de otro perfil. */
@Component({
  selector: 'app-sin-permiso',
  imports: [RouterLink],
  template: `
    <section class="ui" aria-labelledby="permiso-title">
      <div class="panel">
        <span class="eyebrow">ACCESO RESTRINGIDO</span>
        <h1 id="permiso-title">No tiene permiso para esta acción.</h1>
        <p>
          Esta pantalla es solo para el administrador. El intento quedó registrado en la auditoría.
        </p>
        <a class="button primary" routerLink="/">Volver al inicio</a>
      </div>
    </section>
  `,
})
export class SinPermiso {}
