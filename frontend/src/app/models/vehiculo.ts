import type { MedioPago } from './pago';

export const TIPOS_VEHICULO = ['CARRO', 'CAMIONETA', 'MOTO'] as const;
export type TipoVehiculo = (typeof TIPOS_VEHICULO)[number];
export const NOMBRE_TIPO: Record<string, string> = {
  CARRO: 'Carro',
  CAMIONETA: 'Camioneta',
  MOTO: 'Moto',
};
/** RN-12: tarifa de la mensualidad por tipo de vehículo (pesos). El servidor la vuelve a validar. */
export const TARIFA_MENSUALIDAD: Record<TipoVehiculo, number> = {
  CARRO: 250000,
  CAMIONETA: 250000,
  MOTO: 100000,
};
/** Valor que se autollena en «Valor» según el tipo; vacío si el tipo no tiene tarifa. */
export function tarifaMensualidad(tipo: string): string {
  return tipo in TARIFA_MENSUALIDAD ? String(TARIFA_MENSUALIDAD[tipo as TipoVehiculo]) : '';
}
/** RF-02 y RF-04: todo vehículo pertenece a un cliente y trae su primer pago (fecha, valor y medio). */
export interface VehiculoCrear {
  placa: string;
  color: string;
  modelo: number;
  marca: string;
  linea: string;
  tipo: TipoVehiculo;
  cliente_id: number;
  fecha_pago: string;
  valor: string;
  medio: MedioPago;
}
/** RF-04: la fecha de pago y el pago no se editan en el vehículo; la mensualidad cambia solo con un pago. */
export type VehiculoActualizar = Partial<Omit<VehiculoCrear, 'fecha_pago' | 'valor' | 'medio'>>;
/** Los vehículos anteriores a esta iteración pueden no tener cliente, línea ni pago. */
export interface Vehiculo {
  id: number;
  placa: string;
  color: string;
  modelo: number;
  marca: string;
  tipo: string;
  cliente_id: number | null;
  linea: string | null;
  fecha_pago: string | null;
  fecha_vencimiento: string | null;
}
export interface VehiculosPagina {
  items: Vehiculo[];
  total: number;
  offset: number;
  limit: number;
}
export interface ErrorValidacion {
  loc: (string | number)[];
  msg: string;
  type: string;
}
export interface ErrorApi {
  detail?: string | ErrorValidacion[];
}

export const MENSAJE_PLACA =
  'Ingresa una placa colombiana: tres letras y tres números (ABC123) o, en motos, tres letras, dos números y una letra (ABC12D).';

/** Devuelve la placa en mayúsculas y sin separadores, o null si no es colombiana. */
export function normalizarPlaca(value: string): string | null {
  const placa = value.replace(/[\s-]/g, '').toUpperCase();
  return /^[A-Z]{3}\d{2}[0-9A-Z]$/.test(placa) ? placa : null;
}
