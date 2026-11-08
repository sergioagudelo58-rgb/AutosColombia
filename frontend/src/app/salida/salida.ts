import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
} from '@angular/forms';
import { Movimiento } from '../models/estancia';
import { NOMBRE_TIPO, normalizarPlaca } from '../models/vehiculo';
import { EstanciasService } from '../services/estancias.service';
import { fechaHora, mensajeError, noVacio } from '../shared/formato';
import { TurnoComponent } from '../shared/turno';
import { TurnoService } from '../shared/turno.service';

export const MENSAJE_BUSQUEDA_SALIDA =
  'Digita la placa (ABC123 o ABC12D) o el número del recibo (E-000245).';

/** Acepta E-000245, e245 o 245 y devuelve E-000245; null si no es un recibo. */
export function normalizarRecibo(valor: string): string | null {
  const match = /^(?:E-?)?0*([0-9]{1,18})$/.exec(valor.replace(/\s/g, '').toUpperCase());
  return match && Number(match[1]) > 0 ? `E-${match[1].padStart(6, '0')}` : null;
}

/** La búsqueda es por placa o, si no es una placa, por número de recibo. */
export function busquedaSalida(valor: string): { placa: string } | { recibo: string } | null {
  const placa = normalizarPlaca(valor);
  if (placa) return { placa };
  const recibo = normalizarRecibo(valor);
  return recibo ? { recibo } : null;
}

function placaORecibo(control: AbstractControl): ValidationErrors | null {
  const valor = control.value;
  return typeof valor !== 'string' || !valor.trim() || busquedaSalida(valor)
    ? null
    : { busqueda: true };
}

/** RF-07: salida por placa o recibo, con el operador y la puerta del turno. */
@Component({
  selector: 'app-salida',
  imports: [ReactiveFormsModule, TurnoComponent],
  templateUrl: './salida.html',
  styleUrl: './salida.css',
})
export class Salida {
  readonly mensajeBusqueda = MENSAJE_BUSQUEDA_SALIDA;
  readonly turnos = inject(TurnoService);
  private readonly api = inject(EstanciasService);
  private readonly destroy = inject(DestroyRef);
  readonly form = inject(FormBuilder).nonNullable.group({
    busqueda: ['', [noVacio, placaORecibo]],
  });
  readonly registro = signal<Movimiento | null>(null);
  readonly salida = signal<Movimiento | null>(null);
  readonly error = signal('');
  readonly buscando = signal(false);
  readonly guardando = signal(false);
  readonly ocupado = computed(() => this.buscando() || this.guardando());
  readonly fecha = fechaHora;
  private version = 0;

  constructor() {
    this.form.controls.busqueda.valueChanges
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe(() => {
        if (this.buscando()) return;
        this.version++;
        this.registro.set(null);
        this.error.set('');
      });
  }

  tipo(value: string): string {
    return NOMBRE_TIPO[value] ?? value;
  }

  buscar(): void {
    if (this.ocupado()) return;
    const control = this.form.controls.busqueda;
    control.markAsTouched();
    if (this.form.invalid) return;
    const busqueda = busquedaSalida(control.value)!;
    control.setValue('placa' in busqueda ? busqueda.placa : busqueda.recibo, { emitEvent: false });
    const version = ++this.version;
    this.salida.set(null);
    this.registro.set(null);
    this.error.set('');
    this.buscando.set(true);
    this.api
      .abierta(busqueda)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (registro) => {
          this.buscando.set(false);
          if (version === this.version) this.registro.set(registro);
        },
        error: (error: HttpErrorResponse) => {
          this.buscando.set(false);
          if (version === this.version) this.error.set(mensajeError(error));
        },
      });
  }

  confirmar(): void {
    const registro = this.registro();
    const turno = this.turnos.turno();
    if (this.ocupado() || !registro || !turno) return;
    this.guardando.set(true);
    this.error.set('');
    // Se envían placa y recibo para que el servidor confirme que corresponden al mismo ingreso.
    this.api
      .salida({
        placa: registro.placa,
        numero_recibo: registro.numero_recibo,
        operador_id: turno.operador.id,
        puerta_id: turno.puerta.id,
      })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (movimiento) => {
          this.guardando.set(false);
          this.registro.set(null);
          this.salida.set(movimiento);
          this.form.reset();
        },
        error: (error: HttpErrorResponse) => {
          this.guardando.set(false);
          this.error.set(mensajeError(error));
        },
      });
  }
}
