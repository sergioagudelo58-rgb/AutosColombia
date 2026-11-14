import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';
import { Rol } from './models/auth';
import { sesionDePrueba } from './testing/auth';

function menu(rol: Rol): (string | null | undefined)[][] {
  TestBed.configureTestingModule({
    imports: [App],
    providers: [provideRouter([]), sesionDePrueba(rol)],
  });
  const fixture = TestBed.createComponent(App);
  fixture.detectChanges();
  const nav = (fixture.nativeElement as HTMLElement).querySelector('nav')!;
  return [...nav.querySelectorAll('a')].map((a) => [a.getAttribute('href'), a.textContent?.trim()]);
}

describe('Menú por perfil (RF-02)', () => {
  it('el operador solo ve las opciones de entrada y salida de vehículos', () => {
    expect(menu('OPERADOR')).toEqual([
      ['/operacion/entrada', 'Entrada'],
      ['/operacion/salida', 'Salida'],
      ['/operacion/celdas', 'Mapa'],
      ['/gestion/clientes', 'Nuevo vehículo'],
    ]);
  });

  it('el administrador ve además la administración', () => {
    expect(menu('ADMINISTRADOR').map(([href]) => href)).toEqual([
      '/operacion/entrada',
      '/operacion/salida',
      '/operacion/celdas',
      '/gestion/clientes',
      '/gestion/usuarios',
      '/gestion/celdas',
      '/gestion/reportes',
    ]);
  });

  it('muestra quién está conectado, con su perfil y puerta', () => {
    TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([]), sesionDePrueba('OPERADOR')],
    });
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Laura Gómez · Operador · Puerta 2',
    );
  });
});
