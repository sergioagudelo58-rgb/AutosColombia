import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { Puerta } from '../models/estancia';
import { EstanciasService } from '../services/estancias.service';
import { AuthService } from './auth.service';

/** RF-01: ingreso con usuario y contraseña personales; el operador elige su puerta. */
@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule],
  template: `
    <section class="ui ingreso" aria-labelledby="login-title">
      <div class="panel tarjeta">
        <span class="eyebrow">AUTOS COLOMBIA</span>
        <h1 id="login-title">Iniciar sesión</h1>
        <p>
          Ingresa con tu usuario y contraseña personales. Todo lo que registres queda a tu nombre.
        </p>
        @if (auth.aviso()) {
          <p class="notice info" role="status">{{ auth.aviso() }}</p>
        }
        @if (error()) {
          <p class="notice error" role="alert">{{ error() }}</p>
        }
        <form [formGroup]="form" (ngSubmit)="ingresar()" novalidate>
          <fieldset [disabled]="enviando()">
            <div class="field">
              <label for="usuario">Usuario</label>
              <input
                id="usuario"
                formControlName="usuario"
                autocomplete="username"
                autocapitalize="none"
                spellcheck="false"
                [attr.aria-invalid]="invalido('usuario')"
              />
              <span class="field-error">{{
                invalido('usuario') ? 'Escribe tu usuario.' : ''
              }}</span>
            </div>
            <div class="field">
              <label for="contrasena">Contraseña</label>
              <div class="clave">
                <input
                  id="contrasena"
                  [type]="ver() ? 'text' : 'password'"
                  formControlName="contrasena"
                  autocomplete="current-password"
                  [attr.aria-invalid]="invalido('contrasena')"
                />
                <button type="button" (click)="ver.set(!ver())" [attr.aria-pressed]="ver()">
                  {{ ver() ? 'Ocultar' : 'Ver' }}
                </button>
              </div>
              <span class="field-error">{{
                invalido('contrasena') ? 'Escribe tu contraseña.' : ''
              }}</span>
            </div>
            <div class="field">
              <label for="puerta">Puerta en la que trabajas</label>
              <select id="puerta" formControlName="puerta">
                <option [ngValue]="null">Sin puerta (administrador)</option>
                @for (p of puertas(); track p.id) {
                  <option [ngValue]="p.id">{{ p.nombre }}</option>
                }
              </select>
              <span class="hint">Los operadores deben elegir la puerta.</span>
            </div>
            <button class="primary big" type="submit">
              {{ enviando() ? 'Ingresando…' : 'Ingresar' }}
            </button>
          </fieldset>
        </form>
      </div>
    </section>
  `,
  styles: `
    .ingreso {
      display: grid;
      place-items: center;
    }
    .tarjeta {
      width: min(440px, 100%);
    }
    form .field {
      margin-top: 14px;
    }
    .clave {
      display: flex;
      gap: 8px;
    }
    button.big {
      width: 100%;
      justify-content: center;
      margin-top: 18px;
    }
  `,
})
export class Login {
  readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly destroy = inject(DestroyRef);
  readonly form = inject(FormBuilder).nonNullable.group({
    usuario: ['', Validators.required],
    contrasena: ['', Validators.required],
    puerta: [null as number | null],
  });
  readonly puertas = signal<Puerta[]>([]);
  readonly enviando = signal(false);
  readonly error = signal('');
  readonly ver = signal(false);

  constructor() {
    inject(EstanciasService)
      .puertas()
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (p) => this.puertas.set(p),
        error: () => this.error.set('No se pudo conectar con el servidor. Revisa la conexión.'),
      });
  }

  invalido(campo: 'usuario' | 'contrasena'): boolean {
    const c = this.form.controls[campo];
    return c.touched && c.invalid;
  }

  ingresar(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.enviando()) return;
    const { usuario, contrasena, puerta } = this.form.getRawValue();
    this.enviando.set(true);
    this.error.set('');
    this.auth
      .login({ usuario: usuario.trim(), contrasena, puerta_id: puerta })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (s) => {
          this.enviando.set(false);
          void this.router.navigate([s.contrasena_temporal ? '/cambiar-contrasena' : '/']);
        },
        error: (e: HttpErrorResponse) => {
          this.enviando.set(false);
          this.form.controls.contrasena.reset('');
          this.error.set(
            typeof e.error?.detail === 'string'
              ? e.error.detail
              : e.status === 422
                ? 'Revisa los datos de ingreso.'
                : 'No se pudo conectar con el servidor. Intenta de nuevo.',
          );
        },
      });
  }
}
