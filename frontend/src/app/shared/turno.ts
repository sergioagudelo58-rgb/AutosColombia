import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { AuthService } from '../auth/auth.service';
import { Puerta } from '../models/estancia';
import { EstanciasService } from '../services/estancias.service';
import { TurnoService } from './turno.service';

/**
 * Quién registra y por qué puerta (RF-01, RF-03). El operador no lo elige aquí: sale de su sesión.
 * El administrador que cubre un turno elige la puerta antes de registrar.
 */
@Component({
  selector: 'app-turno',
  imports: [ReactiveFormsModule],
  template: `
    @if (turnos.turno(); as t) {
      <div class="notice info turno-activo" role="status">
        <span
          >Registrando como <b>{{ t.operador.nombre }}</b> ({{ t.operador.usuario }}) ·
          <b>{{ t.puerta.nombre }}</b></span
        >
        @if (auth.esAdmin()) {
          <button type="button" (click)="soltar()" [disabled]="guardando()">Cambiar puerta</button>
        }
      </div>
    } @else if (auth.esAdmin()) {
      <section class="panel turno" aria-labelledby="turno-title">
        <h2 id="turno-title">¿En qué puerta cubres el turno?</h2>
        <p class="hint">Las entradas y salidas quedan a tu nombre con la puerta que elijas.</p>
        @if (error()) {
          <p class="notice error" role="alert">{{ error() }}</p>
        }
        <div class="actions">
          <label class="sr-only" for="turno-puerta">Puerta</label>
          <select id="turno-puerta" [formControl]="puerta">
            <option [ngValue]="null">Selecciona la puerta</option>
            @for (p of puertas(); track p.id) {
              <option [ngValue]="p.id">{{ p.nombre }}</option>
            }
          </select>
          <button
            class="primary"
            type="button"
            (click)="elegir()"
            [disabled]="puerta.invalid || guardando()"
          >
            Cubrir turno
          </button>
        </div>
      </section>
    }
  `,
  styles: `
    .turno-activo {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
      margin: 0 0 20px;
    }
    .turno select {
      max-width: 240px;
    }
  `,
})
export class TurnoComponent {
  readonly turnos = inject(TurnoService);
  readonly auth = inject(AuthService);
  private readonly api = inject(EstanciasService);
  private readonly destroy = inject(DestroyRef);
  readonly puerta = new FormControl<number | null>(null, Validators.required);
  readonly puertas = signal<Puerta[]>([]);
  readonly guardando = signal(false);
  readonly error = signal('');

  constructor() {
    if (this.auth.esAdmin()) {
      this.api
        .puertas()
        .pipe(takeUntilDestroyed(this.destroy))
        .subscribe({
          next: (p) => this.puertas.set(p),
          error: () => this.error.set('No se pudieron cargar las puertas.'),
        });
    }
  }

  elegir(): void {
    this.cambiar(this.puerta.value);
  }

  soltar(): void {
    this.cambiar(null);
  }

  private cambiar(puertaId: number | null): void {
    this.guardando.set(true);
    this.error.set('');
    this.auth
      .cambiarPuerta(puertaId)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: () => this.guardando.set(false),
        error: (e: HttpErrorResponse) => {
          this.guardando.set(false);
          this.error.set(e.error?.detail ?? 'No se pudo cambiar la puerta.');
        },
      });
  }
}
