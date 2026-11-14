import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { AuditoriaPagina, FiltrosAuditoria } from '../models/auditoria';
import { AuditoriaService } from '../services/auditoria.service';
import { fechaHora, mensajeError } from '../shared/formato';

export const TAMANO_PAGINA = 20;

const ACCIONES = [
  'INGRESO',
  'SALIDA',
  'CAMBIO_CELDA',
  'CORRECCION_REGISTRO',
  'CORRECCION_ANULA_SALIDA',
  'CLIENTE_CREADO',
  'CLIENTE_MODIFICADO',
  'VEHICULO_CREADO',
  'VEHICULO_MODIFICADO',
  'VEHICULO_ELIMINADO',
  'CELDA_CREADA',
  'CELDA_MODIFICADA',
  'CELDA_INHABILITADA',
  'CELDA_HABILITADA',
  'CELDA_ELIMINADA',
  'USUARIO_CREADO',
  'ACCESO_DENEGADO',
  'SESION_VENCIDA',
];

/** RF-10: consulta de la auditoría con filtros. Solo lectura (RNF-07). */
@Component({
  selector: 'app-auditoria',
  imports: [ReactiveFormsModule],
  templateUrl: './auditoria.html',
  styleUrl: './auditoria.css',
})
export class Auditoria {
  private readonly api = inject(AuditoriaService);
  private readonly destroy = inject(DestroyRef);

  readonly fecha = fechaHora;
  readonly acciones = ACCIONES;
  readonly filtros = inject(FormBuilder).nonNullable.group({
    usuario: [''],
    accion: [''],
    placa: [''],
    desde: [''],
    hasta: [''],
  });
  readonly pagina = signal<AuditoriaPagina | null>(null);
  readonly buscando = signal(false);
  readonly error = signal('');
  private aplicados: FiltrosAuditoria = {};

  constructor() {
    this.cargar(0);
  }

  nombreAccion(accion: string): string {
    const texto = accion.replace(/_/g, ' ').toLowerCase();
    return texto.charAt(0).toUpperCase() + texto.slice(1);
  }

  json(valor: Record<string, unknown> | null): string {
    return valor ? JSON.stringify(valor, null, 1) : '—';
  }

  buscar(): void {
    const { usuario, accion, placa, desde, hasta } = this.filtros.getRawValue();
    if (desde && hasta && desde > hasta) {
      this.error.set('La fecha inicial no puede ser posterior a la fecha final.');
      return;
    }
    this.aplicados = {
      usuario: usuario.trim(),
      accion: accion.trim().toUpperCase().replace(/\s+/g, '_'),
      placa: placa.replace(/[\s-]/g, '').toUpperCase(),
      desde,
      hasta,
    };
    this.cargar(0);
  }

  limpiar(): void {
    this.filtros.reset();
    this.aplicados = {};
    this.cargar(0);
  }

  cargar(offset: number): void {
    this.buscando.set(true);
    this.error.set('');
    this.api
      .listar(this.aplicados, offset, TAMANO_PAGINA)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (pagina) => {
          this.buscando.set(false);
          this.pagina.set(pagina);
        },
        error: (error: HttpErrorResponse) => {
          this.buscando.set(false);
          this.error.set(mensajeError(error));
        },
      });
  }
}
