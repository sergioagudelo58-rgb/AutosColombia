import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import { CeldaActualizar, CeldaCrear } from '../models/celda';
import { CeldaDetalle, CeldasPaginaDetalle, FiltrosCeldas } from '../models/celda-gestion';

import { API_BASE_URL } from './api.service';

@Injectable({ providedIn: 'root' })
export class CeldasService {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);
  private readonly cells = `${this.base}/celdas`;

  list(offset: number, limit: number, filtros: FiltrosCeldas = {}) {
    let params = new HttpParams().set('offset', offset).set('limit', limit);
    if (filtros.q) params = params.set('q', filtros.q);
    if (filtros.tipo) params = params.set('tipo', filtros.tipo);
    if (filtros.estado) params = params.set('estado', filtros.estado);
    return this.http.get<CeldasPaginaDetalle>(this.cells, { params }).pipe(timeout(15000));
  }
  get(id: number) {
    return this.http.get<CeldaDetalle>(`${this.cells}/${id}`).pipe(timeout(15000));
  }
  create(data: CeldaCrear) {
    return this.http.post<CeldaDetalle>(this.cells, data).pipe(timeout(15000));
  }
  update(id: number, data: CeldaActualizar) {
    return this.http.patch<CeldaDetalle>(`${this.cells}/${id}`, data).pipe(timeout(15000));
  }
  inhabilitar(id: number, motivo: string) {
    return this.http
      .post<CeldaDetalle>(`${this.cells}/${id}/inhabilitar`, { motivo })
      .pipe(timeout(15000));
  }
  habilitar(id: number, motivo: string) {
    return this.http
      .post<CeldaDetalle>(`${this.cells}/${id}/habilitar`, { motivo })
      .pipe(timeout(15000));
  }
  /** Borrado lógico (RF-15): la celda queda «Eliminada» y conserva su historial. */
  eliminar(id: number, motivo: string) {
    return this.http
      .post<CeldaDetalle>(`${this.cells}/${id}/eliminar`, { motivo })
      .pipe(timeout(15000));
  }
}