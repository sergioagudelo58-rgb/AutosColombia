import { Celda, TipoCelda } from './celda';

/** Estado que ve el usuario. DISPONIBLE y OCUPADA los calcula el servidor según la estancia abierta. */
export type EstadoCelda = 'DISPONIBLE' | 'OCUPADA' | 'INHABILITADA' | 'ELIMINADA';

export const NOMBRE_ESTADO: Record<EstadoCelda, string> = {
  DISPONIBLE: 'Disponible',
  OCUPADA: 'Ocupada',
  INHABILITADA: 'Inhabilitada',
  ELIMINADA: 'Eliminada',
};

export interface CeldaDetalle extends Celda {
  estado: EstadoCelda;
  motivo_estado: string | null;
  fecha_estado: string | null;
}

export interface TotalTipo {
  tipo: TipoCelda;
  total: number;
  disponibles: number;
  ocupadas: number;
  inhabilitadas: number;
}

export interface CeldasPaginaDetalle {
  items: CeldaDetalle[];
  total: number;
  offset: number;
  limit: number;
  totales_por_tipo: TotalTipo[];
}

export interface FiltrosCeldas {
  q?: string;
  tipo?: TipoCelda | '';
  estado?: EstadoCelda | '';
}

export type AccionCelda = 'inhabilitar' | 'habilitar' | 'eliminar';