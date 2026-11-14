import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, ValidatorFn } from '@angular/forms';
import { CeldasService } from '../services/celdas.service';
import { CeldaCrear, NOMBRE_CELDA, TIPOS_CELDA, TipoCelda } from '../models/celda';
import {
  AccionCelda,
  CeldaDetalle,
  EstadoCelda,
  FiltrosCeldas,
  NOMBRE_ESTADO,
  TotalTipo,
} from '../models/celda-gestion';
import { ErrorApi } from '../models/vehiculo';

const nonBlank: ValidatorFn = (control) =>
  typeof control.value === 'string' && control.value.trim() ? null : { required: true };
type Field = keyof CeldaCrear;
interface AccionPendiente {
  kind: AccionCelda;
  cell: CeldaDetalle;
}

const ESTADOS_FILTRO: EstadoCelda[] = ['DISPONIBLE', 'OCUPADA', 'INHABILITADA', 'ELIMINADA'];

@Component({
  selector: 'app-celdas',
  imports: [ReactiveFormsModule],
  templateUrl: './celdas.html',
  styleUrl: './celdas.css',
})
export class Celdas {
  private readonly api = inject(CeldasService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly fb = inject(FormBuilder);
  readonly tipos = TIPOS_CELDA;
  readonly nombreCelda = NOMBRE_CELDA;
  readonly nombreEstado = NOMBRE_ESTADO;
  readonly estadosFiltro = ESTADOS_FILTRO;
  readonly fields = [
    { key: 'codigo' as const, label: 'Código' },
    { key: 'tipo' as const, label: 'Tipo' },
  ];
  readonly form = this.fb.group({
    codigo: this.fb.nonNullable.control('', nonBlank),
    tipo: this.fb.nonNullable.control('', nonBlank),
  });
  readonly filtersForm = this.fb.nonNullable.group({ q: '', tipo: '', estado: '' });
  readonly motivo = this.fb.nonNullable.control('', nonBlank);
  readonly items = signal<CeldaDetalle[]>([]);
  readonly totales = signal<TotalTipo[]>([]);
  readonly appliedFilters = signal<FiltrosCeldas>({});
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly limit = 10;
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly busy = computed(() => this.loading() || this.saving());
  readonly showForm = signal(false);
  readonly editing = signal<number | null>(null);
  readonly pendingAction = signal<AccionPendiente | null>(null);
  readonly listError = signal('');
  readonly actionError = signal('');
  readonly success = signal('');
  readonly page = computed(() => Math.floor(this.offset() / this.limit) + 1);
  readonly pages = computed(() => Math.max(1, Math.ceil(this.total() / this.limit)));
  readonly filtering = computed(() => {
    const f = this.appliedFilters();
    return !!(f.q || f.tipo || f.estado);
  });

  constructor() {
    this.load();
  }

  load(offset = this.offset()): void {
    if (this.busy()) return;
    this.loading.set(true);
    this.listError.set('');
    this.api
      .list(offset, this.limit, this.appliedFilters())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data) => {
          this.loading.set(false);
          if (offset > 0 && offset >= data.total) {
            this.load(Math.max(0, Math.floor((data.total - 1) / this.limit) * this.limit));
            return;
          }
          this.items.set(data.items);
          this.total.set(data.total);
          this.totales.set(data.totales_por_tipo);
          this.offset.set(offset);
        },
        error: (error) => {
          this.loading.set(false);
          this.listError.set(this.errorMessage(error));
        },
      });
  }

  // ---------- RF-12: búsqueda y filtros ----------

  search(): void {
    if (this.busy()) return;
    const value = this.filtersForm.getRawValue();
    this.appliedFilters.set({
      q: value.q.trim(),
      tipo: value.tipo as TipoCelda | '',
      estado: value.estado as EstadoCelda | '',
    });
    this.load(0);
  }

  clearFilters(): void {
    if (this.busy()) return;
    this.filtersForm.reset();
    this.appliedFilters.set({});
    this.load(0);
  }

  // ---------- RF-11 y RF-13: crear y editar ----------

  /** RF-13: solo se edita una celda libre (disponible o inhabilitada); el servidor lo vuelve a comprobar. */
  canEdit(cell: CeldaDetalle): boolean {
    return cell.estado === 'DISPONIBLE' || cell.estado === 'INHABILITADA';
  }

  newCell(): void {
    if (this.busy()) return;
    this.form.reset();
    this.editing.set(null);
    this.showForm.set(true);
    this.pendingAction.set(null);
    this.actionError.set('');
    this.success.set('');
  }

  edit(cell: CeldaDetalle): void {
    if (this.busy()) return;
    this.loading.set(true);
    this.actionError.set('');
    this.success.set('');
    this.pendingAction.set(null);
    this.api
      .get(cell.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data) => {
          this.loading.set(false);
          if (!this.canEdit(data)) {
            this.actionError.set(
              `La celda ${data.codigo} está ${this.nombreEstado[data.estado].toLowerCase()}: solo se puede modificar cuando esté libre.`,
            );
            this.load();
            return;
          }
          this.editing.set(data.id);
          this.form.reset({ codigo: data.codigo, tipo: data.tipo });
          this.showForm.set(true);
        },
        error: (error) => {
          this.loading.set(false);
          this.actionError.set(this.errorMessage(error));
        },
      });
  }

  cancel(): void {
    if (this.busy()) return;
    this.showForm.set(false);
    this.pendingAction.set(null);
    this.actionError.set('');
  }

  fieldError(field: Field): string {
    const control = this.form.controls[field];
    if (!control.touched || !control.errors) return '';
    if (control.errors['server']) return String(control.errors['server']);
    if (control.errors['required']) return 'Este campo es obligatorio y no puede estar vacío.';
    return 'Revisa este campo.';
  }

  save(): void {
    if (this.busy()) return;
    this.form.markAllAsTouched();
    if (this.form.invalid) {
      this.actionError.set('Revisa los campos señalados antes de guardar la celda.');
      return;
    }
    const value = this.form.getRawValue();
    const payload: CeldaCrear = {
      codigo: value.codigo.trim().toUpperCase(),
      tipo: value.tipo.trim() as TipoCelda,
    };
    this.form.controls.codigo.setValue(payload.codigo);
    this.saving.set(true);
    this.actionError.set('');
    this.success.set('');
    const id = this.editing();
    const request = id === null ? this.api.create(payload) : this.api.update(id, payload);
    request.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (cell) => {
        this.saving.set(false);
        this.showForm.set(false);
        this.success.set(
          `Celda ${cell.codigo} ${id === null ? 'registrada' : 'actualizada'} correctamente.`,
        );
        this.load();
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.actionError.set(this.errorMessage(error));
        if (error.status === 409 && !this.serverDetail(error).includes('ocupada'))
          this.setFieldError('codigo', 'Ya existe una celda con ese código.');
        const body = error.error as ErrorApi | null;
        if (error.status === 422 && Array.isArray(body?.detail)) {
          for (const issue of body.detail) {
            const field = issue.loc.at(-1);
            if (typeof field === 'string' && Object.hasOwn(this.form.controls, field)) {
              this.setFieldError(
                field as Field,
                'El servicio rechazó este valor. Revisa el campo.',
              );
            }
          }
        }
      },
    });
  }

  private setFieldError(field: Field, message: string): void {
    this.form.controls[field].setErrors({ server: message });
    this.form.controls[field].markAsTouched();
  }

  // ---------- RF-14 y RF-15: inhabilitar, habilitar y eliminar (siempre con confirmación y motivo) ----------

  startAction(kind: AccionCelda, cell: CeldaDetalle): void {
    if (this.busy()) return;
    this.motivo.reset('');
    this.pendingAction.set({ kind, cell });
    this.showForm.set(false);
    this.actionError.set('');
    this.success.set('');
  }

  actionTitle(action: AccionPendiente): string {
    const verbo = { inhabilitar: 'Inhabilitar', habilitar: 'Habilitar', eliminar: 'Eliminar' };
    return `${verbo[action.kind]} celda ${action.cell.codigo}`;
  }

  actionDescription(action: AccionPendiente): string {
    const celda = `la celda ${action.cell.codigo}, de tipo ${this.nombreCelda[action.cell.tipo] ?? action.cell.tipo}`;
    switch (action.kind) {
      case 'inhabilitar':
        return `Vas a inhabilitar ${celda}. Dejará de asignarse a los vehículos y se verá inhabilitada en el mapa.`;
      case 'habilitar':
        return `Vas a habilitar ${celda}. Volverá a quedar disponible para la asignación automática.`;
      case 'eliminar':
        return `Vas a eliminar ${celda}. Saldrá del listado, del mapa y de la asignación, pero su historial se conserva.`;
    }
  }

  actionButton(action: AccionPendiente): string {
    const idle = { inhabilitar: 'Confirmar inhabilitación', habilitar: 'Confirmar habilitación', eliminar: 'Confirmar eliminación' };
    const busy = { inhabilitar: 'Inhabilitando…', habilitar: 'Habilitando…', eliminar: 'Eliminando…' };
    return this.saving() ? busy[action.kind] : idle[action.kind];
  }

  motivoError(): string {
    return this.motivo.touched && this.motivo.invalid ? 'Escribe el motivo para continuar.' : '';
  }

  confirmAction(): void {
    const action = this.pendingAction();
    if (!action || this.busy()) return;
    this.motivo.markAsTouched();
    if (this.motivo.invalid) {
      this.actionError.set('Escribe el motivo antes de confirmar.');
      return;
    }
    const motivo = this.motivo.value.trim();
    const { kind, cell } = action;
    const request =
      kind === 'inhabilitar'
        ? this.api.inhabilitar(cell.id, motivo)
        : kind === 'habilitar'
          ? this.api.habilitar(cell.id, motivo)
          : this.api.eliminar(cell.id, motivo);
    this.saving.set(true);
    this.actionError.set('');
    request.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        const hecho = { inhabilitar: 'inhabilitada', habilitar: 'habilitada', eliminar: 'eliminada' };
        this.saving.set(false);
        this.pendingAction.set(null);
        this.success.set(`Celda ${cell.codigo} ${hecho[kind]} correctamente.`);
        this.load();
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.actionError.set(this.errorMessage(error));
        if (error.status === 404 || error.status === 409) {
          // La celda cambió de estado (por ejemplo, la ocuparon): se actualiza el listado.
          this.pendingAction.set(null);
          this.load();
        }
      },
    });
  }

  private serverDetail(error: HttpErrorResponse): string {
    const detail: unknown = (error.error as { detail?: unknown } | null)?.detail;
    return typeof detail === 'string' ? detail : '';
  }

  private errorMessage(error: HttpErrorResponse): string {
    const detail = this.serverDetail(error);
    if (detail && (error.status === 409 || error.status === 404)) return detail;
    if (error.status === 404) return 'La celda ya no existe. Actualiza el listado.';
    if (error.status === 409) return 'Ya existe una celda con ese código.';
    if (error.status === 422)
      return 'Revisa los datos: hay campos que no cumplen las validaciones.';
    return 'No se pudo conectar con el servicio. Comprueba la conexión y actualiza el listado antes de reintentar.';
  }
}