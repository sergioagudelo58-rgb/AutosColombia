import { Cliente } from './cliente';
import { Mensualidad } from './estancia';
import { Vehiculo } from './vehiculo';

/** Iteración 3, RN-03: el cliente pagó en un banco, en efectivo o por QR. */
export const MEDIOS_PAGO = [
  { valor: 'BANCO', nombre: 'Banco (recibo del banco)' },
  { valor: 'EFECTIVO', nombre: 'Efectivo' },
  { valor: 'QR', nombre: 'QR (comprobante del pago con QR)' },
] as const;
export type MedioPago = (typeof MEDIOS_PAGO)[number]['valor'];

/** RF-01: lo que digita el operario. El usuario que registra sale de la sesión. */
export interface PagoCrear {
  cedula: string;
  placa: string;
  fecha_pago: string;
  valor: string;
  medio: MedioPago;
}

/** RF-01 y RF-03: cliente, vehículo y hasta cuándo va la mensualidad, antes de pagar. */
export interface ConsultaPago {
  cliente: Cliente;
  vehiculo: Vehiculo;
  mensualidad: Mensualidad;
}

/** RF-03: el pago guardado y la fecha hasta la que va la mensualidad. */
export interface PagoRespuesta {
  id: number;
  cedula: string;
  cliente: string;
  placa: string;
  fecha_pago: string;
  valor: string;
  medio: MedioPago;
  vencimiento_anterior: string | null;
  vencimiento_nuevo: string;
  registrado_por: string;
  registrado_en: string;
  mensualidad: Mensualidad;
}
