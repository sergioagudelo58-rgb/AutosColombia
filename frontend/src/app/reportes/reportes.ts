import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { NOMBRE_CELDA } from '../models/celda';
import { FiltrosHistorial, HistorialPagina, ReporteOcupacion } from '../models/reporte';
import { NOMBRE_TIPO } from '../models/vehiculo';
import { ReportesService } from '../services/reportes.service';
import { fechaDia, fechaHora, hoyColombia, mensajeError } from '../shared/formato';
import { AuthService } from '../auth/auth.service';

export const TAMANO_PAGINA = 20;

/** Celda CSV segura para Excel: comillas escapadas y sin fórmulas inyectadas. */
function celdaCsv(valor: string | number): string {
  let texto = String(valor);
  if (/^[=+\-@]/.test(texto)) texto = `'${texto}`;
  return `"${texto.replace(/"/g, '""')}"`;
}

/** RF-10 (reporte de ocupación) y RF-11 (historial de movimientos). */
@Component({
  selector: 'app-reportes',
  imports: [ReactiveFormsModule],
  templateUrl: './reportes.html',
  styleUrl: './reportes.css',
})
export class Reportes {
  private readonly api = inject(ReportesService);
  private readonly auth = inject(AuthService);
  private readonly destroy = inject(DestroyRef);
  private readonly fb = inject(FormBuilder).nonNullable;

  readonly pestana = signal<'ocupacion' | 'historial'>('ocupacion');
  readonly fecha = fechaHora;
  readonly dia = fechaDia;

  // ---------- RF-10 ----------
  readonly rango = this.fb.group({ desde: [hoyColombia()], hasta: [hoyColombia()] });
  readonly reporte = signal<ReporteOcupacion | null>(null);
  readonly generando = signal(false);
  readonly errorReporte = signal('');

  // ---------- RF-11 ----------
  readonly filtros = this.fb.group({ placa: [''], cliente: [''], desde: [''], hasta: [''] });
  readonly historial = signal<HistorialPagina | null>(null);
  readonly buscando = signal(false);
  readonly errorHistorial = signal('');
  private aplicados: FiltrosHistorial = {};

  constructor() {
    this.generar();
  }

  usuario(): string {
    const s = this.auth.sesion();
    return s ? `${s.nombre} (${s.usuario})` : 'Sin sesión';
  }
  nombreCelda(tipo: string): string {
    return NOMBRE_CELDA[tipo] ?? tipo;
  }
  nombreVehiculo(tipo: string): string {
    return NOMBRE_TIPO[tipo] ?? tipo;
  }
  tiposVehiculo(r: ReporteOcupacion): { tipo: string; total: number }[] {
    return Object.entries(r.vehiculos_por_tipo).map(([tipo, total]) => ({ tipo, total }));
  }

  generar(): void {
    const { desde, hasta } = this.rango.getRawValue();
    if (!desde || !hasta) {
      this.errorReporte.set('Selecciona la fecha inicial y la final.');
      return;
    }
    if (desde > hasta) {
      this.errorReporte.set('La fecha inicial no puede ser posterior a la fecha final.');
      return;
    }
    this.generando.set(true);
    this.errorReporte.set('');
    this.api
      .ocupacion(desde, hasta)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (reporte) => {
          this.generando.set(false);
          this.reporte.set(reporte);
        },
        error: (error: HttpErrorResponse) => {
          this.generando.set(false);
          this.errorReporte.set(mensajeError(error));
        },
      });
  }

  /** «Excel»: CSV con BOM y punto y coma, que Excel en español abre directamente. */
  exportarExcel(): void {
    const r = this.reporte();
    if (!r) return;
    const filas: (string | number)[][] = [
      ['Reporte de ocupación · Autos Colombia'],
      ['Generado', this.fecha(r.generado_en)],
      ['Generado por', this.usuario()],
      ['Rango', `${this.dia(r.desde)} – ${this.dia(r.hasta)}`],
      [],
      ['Indicador', 'Valor'],
      ['Clientes registrados', r.clientes_registrados],
      ['Vehículos registrados', r.vehiculos_registrados],
      ...this.tiposVehiculo(r).map((t) => [`Vehículos · ${this.nombreVehiculo(t.tipo)}`, t.total]),
      ['Vehículos adentro', r.vehiculos_adentro],
      ...r.cupos.flatMap((c) => [
        [`Celdas ocupadas · ${this.nombreCelda(c.tipo_celda)}`, c.ocupadas],
        [`Celdas disponibles · ${this.nombreCelda(c.tipo_celda)}`, c.disponibles],
      ]),
      ['Porcentaje de ocupación', `${r.porcentaje_ocupacion} %`],
      ['Entradas en el rango', r.entradas],
      ['Salidas en el rango', r.salidas],
      ['Cambios de celda en el rango', r.novedades],
    ];
    const csv = '﻿' + filas.map((f) => f.map(celdaCsv).join(';')).join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const enlace = document.createElement('a');
    enlace.href = url;
    enlace.download = `reporte-ocupacion-${r.desde}-a-${r.hasta}.csv`;
    enlace.click();
    URL.revokeObjectURL(url);
  }

  /** PDF: el diálogo de impresión del navegador permite «Guardar como PDF». */
  exportarPdf(): void {
    window.print();
  }

  buscar(): void {
    const { placa, cliente, desde, hasta } = this.filtros.getRawValue();
    if (desde && hasta && desde > hasta) {
      this.errorHistorial.set('La fecha inicial no puede ser posterior a la fecha final.');
      return;
    }
    this.aplicados = {
      placa: placa.replace(/[\s-]/g, '').toUpperCase(),
      cliente: cliente.trim(),
      desde,
      hasta,
    };
    this.pagina(0);
  }

  limpiar(): void {
    this.filtros.reset();
    this.historial.set(null);
    this.errorHistorial.set('');
  }

  pagina(offset: number): void {
    this.buscando.set(true);
    this.errorHistorial.set('');
    this.api
      .historial(this.aplicados, offset, TAMANO_PAGINA)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (pagina) => {
          this.buscando.set(false);
          this.historial.set(pagina);
        },
        error: (error: HttpErrorResponse) => {
          this.buscando.set(false);
          this.errorHistorial.set(mensajeError(error));
        },
      });
  }
}
