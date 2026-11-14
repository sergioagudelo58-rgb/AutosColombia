/** RF-10: registro de auditoría (solo lectura). */
export interface RegistroAuditoria {
  id: number;
  fecha: string;
  usuario: string | null;
  rol: string | null;
  puerta: string | null;
  equipo: string | null;
  accion: string;
  entidad: string | null;
  entidad_id: string | null;
  placa: string | null;
  detalle: string;
  valor_anterior: Record<string, unknown> | null;
  valor_nuevo: Record<string, unknown> | null;
  motivo: string | null;
}

export interface AuditoriaPagina {
  items: RegistroAuditoria[];
  total: number;
  offset: number;
  limit: number;
}

export interface FiltrosAuditoria {
  usuario?: string;
  accion?: string;
  placa?: string;
  desde?: string;
  hasta?: string;
}
