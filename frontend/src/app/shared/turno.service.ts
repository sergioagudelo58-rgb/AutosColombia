import { Injectable, computed, inject } from '@angular/core';
import { AuthService } from '../auth/auth.service';
import { OperadorResumen, Puerta } from '../models/estancia';

export interface Turno {
  operador: OperadorResumen;
  puerta: Puerta;
}

/**
 * Usuario y puerta que registran los movimientos, tomados de la sesión (RF-01, RF-03).
 * El operador elige la puerta al ingresar; el administrador la elige cuando cubre un turno.
 */
@Injectable({ providedIn: 'root' })
export class TurnoService {
  private readonly auth = inject(AuthService);
  readonly turno = computed<Turno | null>(() => {
    const s = this.auth.sesion();
    if (!s || s.puerta_id === null || s.puerta === null) return null;
    return {
      operador: { id: s.usuario_id, nombre: s.nombre, usuario: s.usuario },
      puerta: { id: s.puerta_id, nombre: s.puerta },
    };
  });
  readonly activo = computed(() => this.turno() !== null);
}
