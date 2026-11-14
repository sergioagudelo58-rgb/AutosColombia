import { TipoCelda } from './celda';
import { Cupo, Movimiento } from './estancia';

/** Detalle de solo lectura de una celda ocupada (RF-08). */
export interface OcupacionCelda {
  estancia_id: number;
  numero_recibo: string;
  placa: string;
  tipo_vehiculo: string;
  entrada: string;
  puerta: string;
  operador: string;
}
export type EstadoCelda = 'DISPONIBLE' | 'OCUPADA' | 'INHABILITADA';
export interface CeldaEstado {
  id: number;
  codigo: string;
  tipo: TipoCelda;
  estado: EstadoCelda;
  /** Asignada en los últimos 60 segundos. */
  reciente: boolean;
  ocupacion: OcupacionCelda | null;
}
export type TipoActividad = 'ENTRADA' | 'SALIDA' | 'NOVEDAD';
export interface Actividad {
  tipo: TipoActividad;
  fecha: string;
  placa: string;
  celda: string;
  puerta: string | null;
  operador: string;
  detalle: string;
}
export interface Panel {
  generado_en: string;
  cupos: Cupo[];
  celdas: CeldaEstado[];
  actividad: Actividad[];
}
/** RF-10: indicadores calculados en el momento de generar el reporte. */
export interface ReporteOcupacion {
  generado_en: string;
  desde: string;
  hasta: string;
  clientes_registrados: number;
  vehiculos_registrados: number;
  vehiculos_por_tipo: Record<string, number>;
  vehiculos_adentro: number;
  cupos: Cupo[];
  celdas_total: number;
  celdas_ocupadas: number;
  celdas_disponibles: number;
  porcentaje_ocupacion: number;
  entradas: number;
  salidas: number;
  novedades: number;
}
/** RF-11: filtros opcionales del historial. */
export interface FiltrosHistorial {
  placa?: string;
  cliente?: string;
  desde?: string;
  hasta?: string;
}
export interface HistorialPagina {
  items: Movimiento[];
  total: number;
  offset: number;
  limit: number;
}
