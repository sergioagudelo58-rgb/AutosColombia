import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Observable, catchError, exhaustMap, of, timer } from 'rxjs';
import { AuthService } from '../auth/auth.service';
import { NOMBRE_ROL, Rol } from '../models/auth';
import { Usuario, UsuarioConTemporal } from '../models/usuario';
import { UsuariosService } from '../services/usuarios.service';
import { fechaDia, fechaHora, hoyColombia, mensajeError, noVacio } from '../shared/formato';

const ACTUALIZAR_MS = 5000;
type Accion = 'retirar' | 'restablecer' | 'cerrar';

/** RF-04 a RF-07: crear, consultar, modificar, retirar y reactivar usuarios; contraseñas temporales. */
@Component({
  selector: 'app-usuarios',
  imports: [ReactiveFormsModule],
  templateUrl: './usuarios.html',
  styleUrl: './usuarios.css',
})
export class Usuarios {
  private readonly api = inject(UsuariosService);
  private readonly fb = inject(FormBuilder);
  private readonly destroy = inject(DestroyRef);
  readonly auth = inject(AuthService);
  readonly nombreRol = NOMBRE_ROL;
  readonly fecha = fechaHora;
  readonly dia = fechaDia;
  readonly tiposDocumento = ['CC', 'CE', 'TI', 'PA', 'NIT'];

  readonly filtros = this.fb.nonNullable.group({ q: [''], estado: ['ACTIVO'], rol: [''] });
  readonly form = this.fb.nonNullable.group({
    tipo_documento: ['CC', Validators.required],
    numero_documento: ['', noVacio],
    nombres: ['', noVacio],
    apellidos: ['', noVacio],
    telefono: ['', noVacio],
    correo: [''],
    usuario: ['', [noVacio, Validators.pattern(/^\s*[a-zA-Z][a-zA-Z0-9._]{2,29}\s*$/)]],
    rol: ['OPERADOR' as Rol, Validators.required],
    fecha_ingreso: [hoyColombia(), Validators.required],
  });
  readonly retiro = this.fb.nonNullable.group({
    motivo: ['', noVacio],
    fecha_retiro: [hoyColombia(), Validators.required],
  });

  readonly items = signal<Usuario[]>([]);
  readonly enLinea = signal(0);
  readonly cargando = signal(true);
  readonly guardando = signal(false);
  readonly errorLista = signal('');
  readonly error = signal('');
  readonly exito = signal('');
  readonly formulario = signal<'nuevo' | Usuario | null>(null);
  readonly pendiente = signal<{ accion: Accion; usuario: Usuario } | null>(null);
  /** RN-06: la contraseña temporal se muestra una sola vez. */
  readonly temporal = signal<UsuarioConTemporal | null>(null);
  readonly editando = computed(() => {
    const f = this.formulario();
    return f !== null && f !== 'nuevo' ? f : null;
  });
  readonly activos = computed(() => this.items().filter((u) => u.estado === 'ACTIVO').length);

  constructor() {
    // RF-06: la lista se refresca sola para ver quién está en línea.
    timer(0, ACTUALIZAR_MS)
      .pipe(
        exhaustMap(() => this.consultar()),
        takeUntilDestroyed(this.destroy),
      )
      .subscribe();
  }

  private consultar(): Observable<unknown> {
    const f = this.filtros.getRawValue();
    return this.api.list(f).pipe(
      catchError((e: HttpErrorResponse) => {
        this.cargando.set(false);
        this.errorLista.set(mensajeError(e));
        return of(null);
      }),
      exhaustMap((pagina) => {
        if (pagina) {
          this.items.set(pagina.items);
          this.enLinea.set(pagina.en_linea);
          this.cargando.set(false);
          this.errorLista.set('');
        }
        return of(null);
      }),
    );
  }

  buscar(): void {
    this.cargando.set(true);
    this.consultar().pipe(takeUntilDestroyed(this.destroy)).subscribe();
  }

  nuevo(): void {
    this.limpiarMensajes();
    this.pendiente.set(null);
    this.form.reset();
    this.form.controls.usuario.enable();
    this.form.controls.tipo_documento.enable();
    this.form.controls.numero_documento.enable();
    this.form.controls.fecha_ingreso.enable();
    this.formulario.set('nuevo');
  }

  editar(u: Usuario): void {
    this.limpiarMensajes();
    this.pendiente.set(null);
    this.form.reset({
      tipo_documento: u.tipo_documento ?? 'CC',
      numero_documento: u.numero_documento ?? '',
      nombres: u.nombres ?? u.nombre,
      apellidos: u.apellidos ?? '',
      telefono: u.telefono,
      correo: u.correo ?? '',
      usuario: u.usuario,
      rol: u.rol,
      fecha_ingreso: u.fecha_ingreso ?? hoyColombia(),
    });
    // RF-06: el nombre de usuario, el documento y la fecha de ingreso no se modifican aquí.
    for (const c of ['usuario', 'tipo_documento', 'numero_documento', 'fecha_ingreso'] as const) {
      this.form.controls[c].disable();
    }
    this.formulario.set(u);
  }

  cancelar(): void {
    this.formulario.set(null);
    this.pendiente.set(null);
    this.error.set('');
  }

  invalido(campo: keyof typeof this.form.controls): boolean {
    const c = this.form.controls[campo];
    return c.touched && c.invalid;
  }

  guardar(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.guardando()) {
      this.error.set('Revisa los campos señalados.');
      return;
    }
    const v = this.form.getRawValue();
    const editando = this.editando();
    const correo = v.correo.trim() || null;
    const peticion: Observable<Usuario | UsuarioConTemporal> = editando
      ? this.api.update(editando.id, {
          nombres: v.nombres.trim(),
          apellidos: v.apellidos.trim(),
          telefono: v.telefono.trim(),
          correo,
          rol: v.rol,
        })
      : this.api.create({ ...v, usuario: v.usuario.trim().toLowerCase(), correo });
    this.ejecutar(peticion, (u) =>
      editando ? `Datos de ${u.usuario} actualizados.` : `Usuario ${u.usuario} creado.`,
    );
  }

  pedir(accion: Accion, usuario: Usuario): void {
    this.limpiarMensajes();
    this.formulario.set(null);
    this.retiro.reset({ motivo: '', fecha_retiro: hoyColombia() });
    this.pendiente.set({ accion, usuario });
  }

  confirmar(): void {
    const p = this.pendiente();
    if (!p || this.guardando()) return;
    if (p.accion === 'retirar') {
      this.retiro.markAllAsTouched();
      if (this.retiro.invalid) return;
      const r = this.retiro.getRawValue();
      this.ejecutar(
        this.api.retire(p.usuario.id, r.motivo.trim(), r.fecha_retiro),
        (u) => `${u.usuario} fue retirado. Ya no puede ingresar y su sesión se cerró.`,
      );
    } else if (p.accion === 'restablecer') {
      this.ejecutar(
        this.api.resetPassword(p.usuario.id),
        (u) => `Contraseña de ${u.usuario} restablecida. Su sesión abierta se cerró.`,
      );
    } else {
      this.ejecutar(
        this.api.closeSession(p.usuario.id),
        (u) => `Se cerró la sesión de ${u.usuario}.`,
      );
    }
  }

  reactivar(u: Usuario): void {
    this.limpiarMensajes();
    this.ejecutar(this.api.reactivate(u.id), (r) => `${r.usuario} fue reactivado.`);
  }

  desbloquear(u: Usuario): void {
    this.limpiarMensajes();
    this.ejecutar(this.api.unlock(u.id), (r) => `Cuenta de ${r.usuario} desbloqueada.`);
  }

  copiar(texto: string): void {
    void navigator.clipboard?.writeText(texto).catch(() => undefined);
  }

  private ejecutar(
    peticion: Observable<Usuario | UsuarioConTemporal>,
    mensaje: (u: Usuario) => string,
  ): void {
    this.guardando.set(true);
    this.error.set('');
    peticion.pipe(takeUntilDestroyed(this.destroy)).subscribe({
      next: (u) => {
        this.guardando.set(false);
        this.formulario.set(null);
        this.pendiente.set(null);
        this.exito.set(mensaje(u));
        this.temporal.set('contrasena_generada' in u ? u : null);
        this.buscar();
      },
      error: (e: HttpErrorResponse) => {
        this.guardando.set(false);
        this.error.set(mensajeError(e));
      },
    });
  }

  private limpiarMensajes(): void {
    this.error.set('');
    this.exito.set('');
    this.temporal.set(null);
  }
}
