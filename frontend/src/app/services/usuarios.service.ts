import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { timeout } from 'rxjs';
import {
  Usuario,
  UsuarioActualizar,
  UsuarioConTemporal,
  UsuarioCrear,
  UsuariosPagina,
} from '../models/usuario';
import { API_BASE_URL } from './api.service';

/** Usuarios del sistema (RF-04 a RF-07), solo para el administrador. */
@Injectable({ providedIn: 'root' })
export class UsuariosService {
  private readonly http = inject(HttpClient);
  private readonly base = `${inject(API_BASE_URL)}/usuarios`;

  list(filtros: { estado?: string; rol?: string; q?: string }) {
    const params: Record<string, string> = {};
    for (const [clave, valor] of Object.entries(filtros)) if (valor) params[clave] = valor;
    return this.http.get<UsuariosPagina>(this.base, { params }).pipe(timeout(15000));
  }
  create(data: UsuarioCrear) {
    return this.http.post<UsuarioConTemporal>(this.base, data).pipe(timeout(15000));
  }
  update(id: number, data: UsuarioActualizar) {
    return this.http.patch<Usuario>(`${this.base}/${id}`, data).pipe(timeout(15000));
  }
  retire(id: number, motivo: string, fecha_retiro: string | null) {
    return this.http
      .post<Usuario>(`${this.base}/${id}/retirar`, { motivo, fecha_retiro })
      .pipe(timeout(15000));
  }
  reactivate(id: number) {
    return this.http
      .post<UsuarioConTemporal>(`${this.base}/${id}/reactivar`, {})
      .pipe(timeout(15000));
  }
  resetPassword(id: number) {
    return this.http
      .post<UsuarioConTemporal>(`${this.base}/${id}/restablecer-contrasena`, {})
      .pipe(timeout(15000));
  }
  unlock(id: number) {
    return this.http.post<Usuario>(`${this.base}/${id}/desbloquear`, {}).pipe(timeout(15000));
  }
  closeSession(id: number) {
    return this.http.post<Usuario>(`${this.base}/${id}/cerrar-sesion`, {}).pipe(timeout(15000));
  }
}
