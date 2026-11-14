import { Rol } from './auth';

export interface UsuarioCrear {
  tipo_documento: string;
  numero_documento: string;
  nombres: string;
  apellidos: string;
  telefono: string;
  correo: string | null;
  usuario: string;
  rol: Rol;
  fecha_ingreso: string;
}
export type UsuarioActualizar = Partial<
  Pick<UsuarioCrear, 'nombres' | 'apellidos' | 'telefono' | 'correo' | 'rol'>
>;
export interface Usuario {
  id: number;
  usuario: string;
  nombre: string;
  nombres: string | null;
  apellidos: string | null;
  tipo_documento: string | null;
  numero_documento: string | null;
  telefono: string;
  correo: string | null;
  rol: Rol;
  estado: 'ACTIVO' | 'RETIRADO';
  fecha_ingreso: string | null;
  fecha_retiro: string | null;
  motivo_retiro: string | null;
  ultima_conexion: string | null;
  en_linea: boolean;
  puerta: string | null;
  bloqueado: boolean;
  contrasena_temporal: boolean;
  sin_contrasena: boolean;
}
/** La contraseña temporal llega una sola vez (RN-06). */
export interface UsuarioConTemporal extends Usuario {
  contrasena_generada: string;
}
export interface UsuariosPagina {
  items: Usuario[];
  total: number;
  en_linea: number;
}
