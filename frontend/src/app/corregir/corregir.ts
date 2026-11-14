import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, OnInit, inject, input, output, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Movimiento } from '../models/estancia';
import { CorreccionCrear, CorreccionesService } from '../services/correcciones.service';
import { mensajeError, noVacio } from '../shared/formato';

/** Colombia no tiene horario de verano: siempre UTC-5. */
const DESFASE_MS = 5 * 3600 * 1000;

function aLocal(iso: string): string {
  return new Date(new Date(iso).getTime() - DESFASE_MS).toISOString().slice(0, 16);
}
function aIso(local: string): string {
  return new Date(`${local}:00-05:00`).toISOString();
}

/** RF-09: corregir una fecha o anular la salida. El servidor exige perfil Administrador y guarda el motivo. */
@Component({
  selector: 'app-corregir',
  imports: [ReactiveFormsModule],
  templateUrl: './corregir.html',
  styleUrl: './corregir.css',
})
export class CorregirRegistro implements OnInit {
  readonly movimiento = input.required<Movimiento>();
  readonly listo = output<void>();
  readonly cancelar = output<void>();

  private readonly api = inject(CorreccionesService);
  private readonly destroy = inject(DestroyRef);

  readonly guardando = signal(false);
  readonly error = signal('');
  readonly form = inject(FormBuilder).nonNullable.group({
    entrada: [''],
    salida: [''],
    anular: [false],
    motivo: ['', [noVacio, Validators.maxLength(300)]],
  });
  private original = { entrada: '', salida: '' };

  ngOnInit(): void {
    const m = this.movimiento();
    this.original = { entrada: aLocal(m.entrada), salida: m.salida ? aLocal(m.salida) : '' };
    this.form.patchValue(this.original);
  }

  invalido(campo: 'motivo'): boolean {
    const c = this.form.controls[campo];
    return c.touched && c.invalid;
  }

  guardar(): void {
    this.form.markAllAsTouched();
    if (this.guardando() || this.form.invalid) return;
    const m = this.movimiento();
    const v = this.form.getRawValue();
    const cuerpo: CorreccionCrear = { motivo: v.motivo.trim() };
    if (v.entrada && v.entrada !== this.original.entrada) cuerpo.entrada = aIso(v.entrada);
    if (!m.abierta) {
      if (v.anular) cuerpo.anular_salida = true;
      else if (v.salida && v.salida !== this.original.salida) cuerpo.salida = aIso(v.salida);
    }
    if (!cuerpo.entrada && !cuerpo.salida && !cuerpo.anular_salida) {
      this.error.set('No cambiaste ningún dato.');
      return;
    }
    this.guardando.set(true);
    this.error.set('');
    this.api
      .corregir(m.id, cuerpo)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: () => {
          this.guardando.set(false);
          this.listo.emit();
        },
        error: (error: HttpErrorResponse) => {
          this.guardando.set(false);
          this.error.set(mensajeError(error));
        },
      });
  }
}
