import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import { AuditoriaPagina, FiltrosAuditoria } from '../models/auditoria';
import { API_BASE_URL } from './api.service';

/** RF-10: consulta de la auditoría. Solo administrador; no hay operaciones de edición ni de borrado. */
@Injectable({ providedIn: 'root' })
export class AuditoriaService {
  private readonly http = inject(HttpClient);
  private readonly root = inject(API_BASE_URL);

  listar(filtros: FiltrosAuditoria, offset: number, limit: number) {
    const params: Record<string, string | number> = { offset, limit };
    for (const [clave, valor] of Object.entries(filtros)) if (valor) params[clave] = valor;
    return this.http
      .get<AuditoriaPagina>(`${this.root}/auditoria`, { params })
      .pipe(timeout(15000));
  }
}
