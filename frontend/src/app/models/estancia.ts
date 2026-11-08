import { Celda, TipoCelda } from './celda';
import { Cliente } from './cliente';
import { Vehiculo } from './vehiculo';

export interface Puerta {
  id: number;
  nombre: string;
}
export interface OperadorResumen {
  id: number;
  nombre: string;
}
export interface EntradaCrear {
  placa: string;
  operador_id: number;
  puerta_id: number;
}
/** RF-07: placa o número de recibo (o ambos, que el servidor verifica) y la puerta de salida. */
export interface SalidaCrear {
  placa?: string;
  numero_recibo?: string;
  operador_id: number;
  puerta_id: number;
}
/** RF-09: cambio de celda de un ingreso abierto; intercambiar solo si la celda nueva está ocupada. */
export interface CambioCeldaCrear {
  celda_id: number;
  motivo: string;
  operador_id: number;
  intercambiar: boolean;
}
export interface Novedad {
  id: number;
  celda_anterior: Celda;
  celda_nueva: Celda;
  motivo: string;
  operador: OperadorResumen;
  fecha: string;
}
/** Estancia con los datos del recibo de ingreso y sus novedades. */
export interface Movimiento {
  id: number;
  numero_recibo: string;
  vehiculo_id: number;
  placa: string;
  tipo_vehiculo: string;
  marca: string;
  linea: string | null;
  color: string;
  cliente: string | null;
  celda: Celda;
  entrada: string;
  salida: string | null;
  abierta: boolean;
  puerta_entrada: Puerta;
  puerta_salida: Puerta | null;
  operador_entrada: OperadorResumen;
  operador_salida: OperadorResumen | null;
  cliente_documento?: string | null;
  novedades?: Novedad[];
}
export interface CambioCeldaRespuesta {
  estancia: Movimiento;
  intercambio: Movimiento | null;
}
export type EstadoMensualidad = 'VIGENTE' | 'VENCE_HOY' | 'VENCIDA' | 'SIN_PAGO' | 'SIN_CLIENTE';
export interface Mensualidad {
  estado: EstadoMensualidad;
  fecha_pago: string | null;
  fecha_vencimiento: string | null;
  dias: number | null;
  permite_ingreso: boolean;
  mensaje: string;
}
export interface Cupo {
  tipo_celda: TipoCelda;
  nombre: string;
  total: number;
  ocupadas: number;
  disponibles: number;
}
export interface ConsultaVehiculo {
  vehiculo: Vehiculo;
  cliente: Cliente | null;
  mensualidad: Mensualidad;
  esta_dentro: boolean;
  estancia: Movimiento | null;
  cupo: Cupo;
  puede_ingresar: boolean;
  motivo: string | null;
}
