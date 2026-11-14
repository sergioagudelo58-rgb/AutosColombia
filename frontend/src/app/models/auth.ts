export type Rol = 'ADMINISTRADOR' | 'OPERADOR';
export const NOMBRE_ROL: Record<string, string> = {
  ADMINISTRADOR: 'Administrador',
  OPERADOR: 'Operador',
};

/** Sesión abierta (RF-01): usuario, perfil y puerta del turno. */
export interface Sesion {
  usuario_id: number;
  usuario: string;
  nombre: string;
  rol: Rol;
  puerta_id: number | null;
  puerta: string | null;
  contrasena_temporal: boolean;
  inactividad_segundos: number;
}
export interface LoginRespuesta extends Sesion {
  token: string;
}
export interface LoginCrear {
  usuario: string;
  contrasena: string;
  puerta_id: number | null;
}
export interface CambioContrasena {
  actual: string;
  nueva: string;
  confirmacion: string;
}

/** RNF-02: lo mismo que valida el servidor, para guiar al usuario mientras escribe. */
export function reglasContrasena(
  clave: string,
  usuario = '',
): { texto: string; cumple: boolean }[] {
  return [
    { texto: 'Mínimo 8 caracteres', cumple: clave.length >= 8 && clave.length <= 64 },
    { texto: 'Una letra mayúscula', cumple: /\p{Lu}/u.test(clave) },
    { texto: 'Una letra minúscula', cumple: /\p{Ll}/u.test(clave) },
    { texto: 'Un número', cumple: /\d/.test(clave) },
    {
      texto: 'Distinta del nombre de usuario',
      cumple: !!clave && clave.trim().toLowerCase() !== usuario.toLowerCase(),
    },
  ];
}
