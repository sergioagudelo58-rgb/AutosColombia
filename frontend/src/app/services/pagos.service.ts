import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import { ConsultaPago, PagoCrear, PagoRespuesta } from '../models/pago';
import { API_BASE_URL } from './api.service';

/** Iteración 3: registro del pago de la mensualidad (RF-01) y su vigencia (RF-03). */
@Injectable({ providedIn: 'root' })
export class PagosService {
  private readonly http = inject(HttpClient);
  private readonly root = inject(API_BASE_URL);
  private readonly base = `${this.root}/pagos`;

  consultar(cedula: string, placa: string) {
    return this.http
      .get<ConsultaPago>(`${this.base}/consulta`, { params: { cedula, placa } })
      .pipe(timeout(15000));
  }
  registrar(data: PagoCrear) {
    return this.http.post<PagoRespuesta>(this.base, data).pipe(timeout(15000));
  }
}
