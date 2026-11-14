import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { catchError, exhaustMap, of, timer } from 'rxjs';
import { NOMBRE_CELDA, TIPOS_CELDA, TipoCelda } from '../models/celda';
import { CeldaEstado, Panel } from '../models/reporte';
import { NOMBRE_TIPO } from '../models/vehiculo';
import { EstanciasService } from '../services/estancias.service';
import { ReportesService } from '../services/reportes.service';
import { fechaHora, hora, mensajeError, noVacio } from '../shared/formato';
import { TurnoComponent } from '../shared/turno';
import { TurnoService } from '../shared/turno.service';

/** RNF-02: los cambios de cualquier puerta se ven en máximo 2 segundos, sin recargar. */
export const INTERVALO_PANEL_MS = 2000;

const NOMBRE_ACTIVIDAD: Record<string, string> = {
  ENTRADA: 'Entrada',
  SALIDA: 'Salida',
  NOVEDAD: 'Cambio de celda',
};

/** RF-08: mapa de celdas en vivo. RF-09: cambio o intercambio de celda desde el detalle. */
@Component({
  selector: 'app-mapa',
  imports: [ReactiveFormsModule, TurnoComponent],
  templateUrl: './mapa.html',
  styleUrl: './mapa.css',
})
export class Mapa {
  readonly turnos = inject(TurnoService);
  private readonly reportes = inject(ReportesService);
  private readonly estancias = inject(EstanciasService);
  private readonly destroy = inject(DestroyRef);

  readonly panel = signal<Panel | null>(null);
  readonly sinConexion = signal(false);
  readonly seleccionId = signal<number | null>(null);
  readonly cambiando = signal(false);
  readonly guardando = signal(false);
  readonly error = signal('');
  readonly exito = signal('');
  readonly tipos = TIPOS_CELDA;
  readonly fecha = fechaHora;
  readonly hora = hora;

  readonly form = inject(FormBuilder).nonNullable.group({
    celdaId: [0, [Validators.min(1)]],
    motivo: ['', [noVacio, Validators.maxLength(300)]],
    intercambiar: [false],
  });
  private readonly destinoId = signal(0);

  readonly celdasPorTipo = computed(() => {
    const celdas = this.panel()?.celdas ?? [];
    return this.tipos.map((tipo) => ({
      tipo,
      nombre: NOMBRE_CELDA[tipo],
      celdas: celdas.filter((c) => c.tipo === tipo),
    }));
  });
  /** Se recalcula con cada actualización: el detalle refleja siempre el estado vigente. */
  readonly seleccion = computed(
    () => this.panel()?.celdas.find((c) => c.id === this.seleccionId()) ?? null,
  );
  readonly destinos = computed(() => {
    const actual = this.seleccion();
    if (!actual) return [];
    return (this.panel()?.celdas ?? []).filter((c) => c.tipo === actual.tipo && c.id !== actual.id && c.estado !== 'INHABILITADA');
  });
  readonly destino = computed(() => this.destinos().find((c) => c.id === this.destinoId()) ?? null);

  constructor() {
    this.form.controls.celdaId.valueChanges
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe((id) => {
        this.destinoId.set(Number(id));
        this.form.controls.intercambiar.setValue(false);
      });
    timer(0, INTERVALO_PANEL_MS)
      .pipe(
        // exhaustMap no apila solicitudes si una respuesta tarda más que el intervalo.
        exhaustMap(() => this.reportes.panel().pipe(catchError(() => of(null)))),
        takeUntilDestroyed(this.destroy),
      )
      .subscribe((panel) => {
        this.sinConexion.set(panel === null);
        if (panel) this.panel.set(panel);
      });
  }

  nombreTipoCelda(tipo: TipoCelda): string {
    return NOMBRE_CELDA[tipo];
  }
  nombreVehiculo(tipo: string): string {
    return NOMBRE_TIPO[tipo] ?? tipo;
  }
  nombreActividad(tipo: string): string {
    return NOMBRE_ACTIVIDAD[tipo] ?? tipo;
  }
  claseActividad(tipo: string): string {
    return tipo === 'ENTRADA' ? 'bad' : tipo === 'SALIDA' ? 'ok' : 'warn';
  }

  estadoCelda(c: CeldaEstado): string {
    if (c.estado === 'INHABILITADA') return 'Inhabilitada';
    if (c.estado === 'DISPONIBLE') return 'Disponible';
    return c.reciente ? 'Recién asignada' : 'Ocupada';
  }
  etiqueta(c: CeldaEstado): string {
    const ocupante = c.ocupacion ? ` por ${c.ocupacion.placa}` : '';
    return `Celda ${c.codigo}, ${this.estadoCelda(c).toLowerCase()}${ocupante}`;
  }
  opcionDestino(c: CeldaEstado): string {
    return c.ocupacion
      ? `${c.codigo} · ocupada por ${c.ocupacion.placa}`
      : `${c.codigo} · disponible`;
  }

  seleccionar(c: CeldaEstado): void {
    this.seleccionId.set(this.seleccionId() === c.id ? null : c.id);
    this.cerrarCambio();
    this.exito.set('');
  }

  abrirCambio(): void {
    this.cambiando.set(true);
    this.error.set('');
    this.exito.set('');
    this.form.reset({ celdaId: 0, motivo: '', intercambiar: false });
  }

  cerrarCambio(): void {
    this.cambiando.set(false);
    this.error.set('');
  }

  confirmarCambio(): void {
    const actual = this.seleccion();
    const turno = this.turnos.turno();
    const destino = this.destino();
    this.form.markAllAsTouched();
    if (this.guardando() || !actual?.ocupacion || !turno || !destino || this.form.invalid) return;
    const intercambiar = this.form.controls.intercambiar.value;
    if (destino.estado === 'OCUPADA' && !intercambiar) {
      this.error.set(
        `La celda ${destino.codigo} está ocupada. Marca «Intercambiar celdas» si ese vehículo está en realidad en la celda ${actual.codigo}.`,
      );
      return;
    }
    this.guardando.set(true);
    this.error.set('');
    this.estancias
      .cambiarCelda(actual.ocupacion.estancia_id, {
        celda_id: destino.id,
        motivo: this.form.controls.motivo.value.trim(),
        intercambiar: destino.estado === 'OCUPADA' && intercambiar,
      })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (respuesta) => {
          this.guardando.set(false);
          this.cambiando.set(false);
          const e = respuesta.estancia;
          const otro = respuesta.intercambio;
          this.exito.set(
            otro
              ? `Celdas intercambiadas: ${e.placa} → ${e.celda.codigo} y ${otro.placa} → ${otro.celda.codigo}.`
              : `${e.placa} pasó a la celda ${e.celda.codigo}; la celda ${actual.codigo} quedó disponible.`,
          );
          this.seleccionId.set(e.celda.id);
          this.reportes
            .panel()
            .pipe(takeUntilDestroyed(this.destroy))
            .subscribe({ next: (panel) => this.panel.set(panel), error: () => undefined });
        },
        error: (error: HttpErrorResponse) => {
          this.guardando.set(false);
          this.error.set(mensajeError(error));
        },
      });
  }
}
