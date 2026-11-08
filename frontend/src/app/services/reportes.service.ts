import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import { FiltrosHistorial, HistorialPagina, Panel, ReporteOcupacion } from '../models/reporte';
import { API_BASE_URL } from './api.service';

/** Panel en vivo (RF-08), reporte de ocupación (RF-10) e historial (RF-11). */
@Injectable({ providedIn: 'root' })
export class ReportesService {
  private readonly http = inject(HttpClient);
  private readonly root = inject(API_BASE_URL);

  panel() {
    return this.http.get<Panel>(`${this.root}/panel`).pipe(timeout(5000));
  }
  ocupacion(desde: string, hasta: string) {
    return this.http
      .get<ReporteOcupacion>(`${this.root}/reportes/ocupacion`, { params: { desde, hasta } })
      .pipe(timeout(15000));
  }
  historial(filtros: FiltrosHistorial, offset: number, limit: number) {
    const params: Record<string, string | number> = { offset, limit };
    for (const [clave, valor] of Object.entries(filtros)) if (valor) params[clave] = valor;
    return this.http
      .get<HistorialPagina>(`${this.root}/reportes/historial`, { params })
      .pipe(timeout(15000));
  }
}
