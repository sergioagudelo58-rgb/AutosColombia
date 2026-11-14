import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { reglasContrasena } from '../models/auth';
import { AuthService } from './auth.service';

/** RF-05: cambio obligatorio de la contraseña temporal y cambio voluntario después. */
@Component({
  selector: 'app-cambiar-contrasena',
  imports: [ReactiveFormsModule],
  template: `
    <section class="ui cambio" aria-labelledby="clave-title">
      <div class="panel tarjeta">
        <span class="eyebrow">SEGURIDAD</span>
        <h1 id="clave-title">
          {{ temporal() ? 'Crea tu contraseña' : 'Cambiar contraseña' }}
        </h1>
        @if (temporal()) {
          <p class="notice warning">
            Ingresaste con una contraseña temporal. Para continuar, crea una contraseña que solo tú
            conozcas.
          </p>
        }
        @if (exito()) {
          <p class="notice success" role="status">{{ exito() }}</p>
        }
        @if (error()) {
          <p class="notice error" role="alert">{{ error() }}</p>
        }
        <form [formGroup]="form" (ngSubmit)="guardar()" novalidate>
          <fieldset [disabled]="enviando()">
            <div class="field">
              <label for="actual">{{
                temporal() ? 'Contraseña temporal' : 'Contraseña actual'
              }}</label>
              <input
                id="actual"
                type="password"
                formControlName="actual"
                autocomplete="current-password"
              />
            </div>
            <div class="field">
              <label for="nueva">Nueva contraseña</label>
              <input
                id="nueva"
                type="password"
                formControlName="nueva"
                autocomplete="new-password"
                aria-describedby="reglas"
              />
            </div>
            <ul id="reglas" class="reglas" aria-label="Requisitos de la contraseña">
              @for (r of reglas(); track r.texto) {
                <li [class.ok]="r.cumple">
                  <span aria-hidden="true">{{ r.cumple ? '✓' : '○' }}</span> {{ r.texto }}
                  <span class="sr-only">{{ r.cumple ? 'cumple' : 'falta' }}</span>
                </li>
              }
            </ul>
            <div class="field">
              <label for="confirmacion">Confirmar nueva contraseña</label>
              <input
                id="confirmacion"
                type="password"
                formControlName="confirmacion"
                autocomplete="new-password"
                [attr.aria-invalid]="noCoincide()"
              />
              <span class="field-error">{{
                noCoincide() ? 'No coincide con la nueva contraseña.' : ''
              }}</span>
            </div>
            <div class="actions">
              <button class="primary" type="submit" [disabled]="!valida()">
                {{ enviando() ? 'Guardando…' : 'Guardar contraseña' }}
              </button>
              @if (temporal()) {
                <button type="button" (click)="auth.logout()">Cerrar sesión</button>
              }
            </div>
          </fieldset>
        </form>
      </div>
    </section>
  `,
  styles: `
    .cambio {
      display: grid;
      place-items: center;
    }
    .tarjeta {
      width: min(480px, 100%);
    }
    form .field {
      margin-top: 14px;
    }
    .reglas {
      list-style: none;
      padding: 0;
      margin: 10px 0 0;
      font-size: 13px;
      color: #8f3328;
      display: grid;
      gap: 4px;
    }
    .reglas li.ok {
      color: #1f5a3d;
    }
    .actions {
      margin-top: 18px;
    }
  `,
})
export class CambiarContrasena {
  readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly destroy = inject(DestroyRef);
  readonly form = inject(FormBuilder).nonNullable.group({
    actual: ['', Validators.required],
    nueva: [''],
    confirmacion: [''],
  });
  private readonly valores = toSignal(this.form.valueChanges, { initialValue: this.form.value });
  readonly temporal = computed(() => this.auth.debeCambiarClave());
  readonly reglas = computed(() =>
    reglasContrasena(this.valores().nueva ?? '', this.auth.sesion()?.usuario ?? ''),
  );
  readonly noCoincide = computed(
    () => !!this.valores().confirmacion && this.valores().confirmacion !== this.valores().nueva,
  );
  readonly valida = computed(
    () =>
      !!this.valores().actual &&
      this.reglas().every((r) => r.cumple) &&
      this.valores().confirmacion === this.valores().nueva,
  );
  readonly enviando = signal(false);
  readonly error = signal('');
  readonly exito = signal('');

  guardar(): void {
    if (!this.valida() || this.enviando()) return;
    const eraTemporal = this.temporal();
    this.enviando.set(true);
    this.error.set('');
    this.auth
      .cambiarContrasena(this.form.getRawValue())
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: () => {
          this.enviando.set(false);
          this.form.reset();
          if (eraTemporal) void this.router.navigate(['/']);
          else this.exito.set('Tu contraseña se cambió correctamente.');
        },
        error: (e: HttpErrorResponse) => {
          this.enviando.set(false);
          this.error.set(e.error?.detail ?? 'No se pudo cambiar la contraseña.');
        },
      });
  }
}
