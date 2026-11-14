import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import { Movimiento } from '../models/estancia';
import { API_BASE_URL } from './api.service';

export interface CorreccionCrear {
  motivo: string;
  entrada?: string;
  salida?: string;
  anular_salida?: boolean;
}

/** RF-09: corregir o anular la salida de un registro (solo administrador, con motivo). */
@Injectable({ providedIn: 'root' })
export class CorreccionesService {
  private readonly http = inject(HttpClient);
  private readonly root = inject(API_BASE_URL);

  corregir(estanciaId: number, data: CorreccionCrear) {
    return this.http
      .post<Movimiento>(`${this.root}/estancias/${estanciaId}/corregir`, data)
      .pipe(timeout(15000));
  }
}
