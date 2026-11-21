import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, FormGroup, ReactiveFormsModule, ValidatorFn, Validators } from '@angular/forms';
import { merge } from 'rxjs';
import { ConsultaPago, MEDIOS_PAGO, MedioPago, PagoRespuesta } from '../models/pago';
import { NOMBRE_TIPO, normalizarPlaca, tarifaMensualidad } from '../models/vehiculo';
import { PagosService } from '../services/pagos.service';
import {
  NOMBRE_MENSUALIDAD,
  claseMensualidad,
  fechaDia,
  fechaHora,
  hoyColombia,
  mensajeError,
  noVacio,
  placaColombiana,
} from '../shared/formato';

/** Cédula sin espacios, puntos ni guiones, como la guarda el servidor. */
export function normalizarCedula(valor: string): string {
  return valor.replace(/[\s.\-]/g, '').toUpperCase();
}

const cedulaValida: ValidatorFn = (c) =>
  typeof c.value !== 'string' || !c.value.trim() || /^[0-9A-Z]{3,20}$/.test(normalizarCedula(c.value))
    ? null
    : { cedula: true };

/** Valor en pesos mayor que cero, con máximo dos decimales. */
export const valorValido: ValidatorFn = (c) => {
  const texto = String(c.value ?? '').trim();
  if (!texto) return null;
  return /^\d{1,10}(\.\d{1,2})?$/.test(texto) && Number(texto) > 0 ? null : { valor: true };
};

/** La fecha de pago no puede ser posterior a hoy en Colombia. */
const noFutura: ValidatorFn = (c) =>
  typeof c.value === 'string' && c.value > hoyColombia() ? { futura: true } : null;

/** Iteración 3, RF-01 y RF-03: registrar el pago y mostrar hasta cuándo va la mensualidad. */
@Component({
  selector: 'app-pagos',
  imports: [ReactiveFormsModule],
  templateUrl: './pagos.html',
  styleUrl: './pagos.css',
})
export class Pagos {
  private readonly api = inject(PagosService);
  private readonly destroy = inject(DestroyRef);
  private readonly fb = inject(FormBuilder).nonNullable;
  readonly medios = MEDIOS_PAGO;
  readonly nombreMensualidad = NOMBRE_MENSUALIDAD;
  readonly claseMensualidad = claseMensualidad;
  readonly fechaDia = fechaDia;
  readonly fechaHora = fechaHora;
  readonly hoy = hoyColombia();

  readonly busqueda = this.fb.group({
    cedula: ['', [noVacio, cedulaValida]],
    placa: ['', [noVacio, placaColombiana]],
  });
  readonly pago = this.fb.group({
    fecha_pago: [this.hoy, [Validators.required, noFutura]],
    valor: ['', [noVacio, valorValido]],
    medio: this.fb.control<MedioPago | ''>('', Validators.required),
  });

  readonly consulta = signal<ConsultaPago | null>(null);
  readonly registrado = signal<PagoRespuesta | null>(null);
  readonly error = signal('');
  readonly buscando = signal(false);
  readonly guardando = signal(false);
  readonly ocupado = computed(() => this.buscando() || this.guardando());
  private version = 0;

  constructor() {
    // Si cambia la cédula o la placa, lo consultado ya no corresponde: hay que volver a buscar.
    merge(this.busqueda.controls.cedula.valueChanges, this.busqueda.controls.placa.valueChanges)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe(() => {
        if (this.buscando()) return;
        this.version++;
        this.consulta.set(null);
        this.error.set('');
      });
  }

  tipo(valor: string): string {
    return NOMBRE_TIPO[valor] ?? valor;
  }

  claseAviso(estado: string): string {
    const clase = claseMensualidad(estado);
    return clase === 'ok' ? 'success' : clase === 'warn' ? 'warning' : 'error';
  }

  buscar(): void {
    if (this.ocupado()) return;
    this.busqueda.markAllAsTouched();
    if (this.busqueda.invalid) return;
    const cedula = normalizarCedula(this.busqueda.controls.cedula.value);
    const placa = normalizarPlaca(this.busqueda.controls.placa.value)!;
    this.busqueda.setValue({ cedula, placa }, { emitEvent: false });
    const version = ++this.version;
    this.consulta.set(null);
    this.registrado.set(null);
    this.error.set('');
    this.buscando.set(true);
    this.api
      .consultar(cedula, placa)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (consulta) => {
          this.buscando.set(false);
          if (version !== this.version) return;
          this.consulta.set(consulta);
          // RN-12: el valor se llena solo con la tarifa del tipo de vehículo.
          this.pago.reset({
            fecha_pago: hoyColombia(),
            valor: tarifaMensualidad(consulta.vehiculo.tipo),
            medio: '',
          });
        },
        error: (error: HttpErrorResponse) => {
          this.buscando.set(false);
          // RF-01: «El cliente no está registrado», «El vehículo no está registrado» o
          // «El vehículo no pertenece a este cliente», tal como responde el servidor.
          if (version === this.version) this.error.set(mensajeError(error));
        },
      });
  }

  registrar(): void {
    const consulta = this.consulta();
    if (this.ocupado() || !consulta) return;
    this.pago.markAllAsTouched();
    if (this.pago.invalid) return;
    const { fecha_pago, valor, medio } = this.pago.getRawValue();
    this.guardando.set(true);
    this.error.set('');
    this.api
      .registrar({
        cedula: consulta.cliente.numero_documento,
        placa: consulta.vehiculo.placa,
        fecha_pago,
        valor: valor.trim(),
        medio: medio as MedioPago,
      })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (pago) => {
          this.guardando.set(false);
          this.registrado.set(pago);
          this.consulta.set(null);
          this.version++;
          this.busqueda.reset({ cedula: '', placa: '' }, { emitEvent: false });
          this.pago.reset({ fecha_pago: hoyColombia(), valor: '', medio: '' });
        },
        error: (error: HttpErrorResponse) => {
          this.guardando.set(false);
          this.error.set(mensajeError(error));
        },
      });
  }

  invalido(grupo: 'busqueda' | 'pago', campo: string): boolean {
    const formulario: FormGroup = grupo === 'busqueda' ? this.busqueda : this.pago;
    const control = formulario.get(campo);
    return !!control && control.touched && control.invalid;
  }

  valorEnPesos(valor: string): string {
    return new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP' }).format(Number(valor));
  }

  nombreMedio(valor: string): string {
    return MEDIOS_PAGO.find((m) => m.valor === valor)?.nombre ?? valor;
  }
}
