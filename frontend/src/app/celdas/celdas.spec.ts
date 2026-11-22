import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CeldaDetalle, CeldasPaginaDetalle } from '../models/celda-gestion';
import { Celdas } from './celdas';

const LISTA = '/celdas?offset=0&limit=10';

const cell: CeldaDetalle = {
  id: 1,
  codigo: 'A-01',
  tipo: 'MOTO',
  estado: 'DISPONIBLE',
  motivo_estado: null,
  fecha_estado: null,
};

function pagina(items: CeldaDetalle[]): CeldasPaginaDetalle {
  return {
    items,
    total: items.length,
    offset: 0,
    limit: 10,
    totales_por_tipo: [
      { tipo: 'CARRO_CAMIONETA', total: 0, disponibles: 0, ocupadas: 0, inhabilitadas: 0 },
      { tipo: 'MOTO', total: 1, disponibles: 1, ocupadas: 0, inhabilitadas: 0 },
    ],
  };
}

describe('Gestión de celdas', () => {
  let fixture: ComponentFixture<Celdas>;
  let http: HttpTestingController;
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Celdas],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Celdas);
    fixture.detectChanges();
    http.expectOne(LISTA).flush(pagina([cell]));
  });
  afterEach(() => http.verify());

  it('muestra los totales por tipo que envía el servidor (RF-12)', () => {
    const c = fixture.componentInstance;
    expect(c.items()).toEqual([cell]);
    expect(c.totales().find((t) => t.tipo === 'MOTO')?.disponibles).toBe(1);
  });

  it('crea desde el formulario HTML con código normalizado y tipo de la lista (RF-11)', () => {
    fixture.componentInstance.newCell();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    const codigo = root.querySelector<HTMLInputElement>('#codigo')!;
    codigo.value = ' a-02 ';
    codigo.dispatchEvent(new Event('input', { bubbles: true }));
    const tipo = root.querySelector<HTMLSelectElement>('#tipo')!;
    expect([...tipo.options].map((o) => o.value)).toEqual(['', 'CARRO_CAMIONETA', 'MOTO']);
    tipo.value = 'CARRO_CAMIONETA';
    tipo.dispatchEvent(new Event('change', { bubbles: true }));
    root
      .querySelector('form')!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    fixture.componentInstance.save();
    const request = http.expectOne({ method: 'POST', url: '/celdas' });
    expect(request.request.body).toEqual({ codigo: 'A-02', tipo: 'CARRO_CAMIONETA' });
    request.flush({ ...cell, codigo: 'A-02' });
    http.expectOne(LISTA).flush(pagina([cell]));
    expect(fixture.componentInstance.success()).toContain('registrada');
  });

  it('rechaza blancos y muestra duplicados junto al código', () => {
    const c = fixture.componentInstance;
    c.newCell();
    c.form.setValue({ codigo: ' ', tipo: ' ' });
    c.save();
    expect(c.form.invalid).toBe(true);
    c.form.setValue({ codigo: 'A-01', tipo: 'MOTO' });
    c.save();
    http
      .expectOne('/celdas')
      .flush(
        { detail: 'Ya existe una celda con ese código.' },
        { status: 409, statusText: 'Conflict' },
      );
    expect(c.fieldError('codigo')).toContain('Ya existe');
  });

  it('edita mediante PATCH y recarga la lista (RF-13)', () => {
    const c = fixture.componentInstance;
    c.edit(cell);
    http.expectOne('/celdas/1').flush(cell);
    c.form.controls.tipo.setValue('CARRO_CAMIONETA');
    c.save();
    const request = http.expectOne({ method: 'PATCH', url: '/celdas/1' });
    expect(request.request.body.id).toBeUndefined();
    request.flush({ ...cell, tipo: 'CARRO_CAMIONETA' });
    http.expectOne(LISTA).flush(pagina([cell]));
  });

  it('no permite editar una celda ocupada (RF-13)', () => {
    const c = fixture.componentInstance;
    c.edit(cell);
    http.expectOne('/celdas/1').flush({ ...cell, estado: 'OCUPADA' });
    expect(c.showForm()).toBe(false);
    expect(c.actionError()).toContain('ocupada');
    http.expectOne(LISTA).flush(pagina([cell]));
  });

  it('filtra por código, tipo y estado (RF-12)', () => {
    const c = fixture.componentInstance;
    c.filtersForm.setValue({ q: ' a-0 ', tipo: 'MOTO', estado: 'INHABILITADA' });
    c.search();
    const request = http.expectOne((r) => r.url === '/celdas');
    expect(request.request.params.get('q')).toBe('a-0');
    expect(request.request.params.get('tipo')).toBe('MOTO');
    expect(request.request.params.get('estado')).toBe('INHABILITADA');
    expect(request.request.params.get('offset')).toBe('0');
    request.flush(pagina([]));
    expect(c.filtering()).toBe(true);
  });

  it('inhabilitar pide confirmación y motivo, y se puede cancelar (RF-14)', () => {
    const c = fixture.componentInstance;
    c.startAction('inhabilitar', cell);
    fixture.detectChanges();
    const dialogo = (fixture.nativeElement as HTMLElement).querySelector('[role="alertdialog"]')!;
    expect(dialogo.textContent).toContain('A-01');
    c.confirmAction();
    expect(c.motivoError()).toContain('motivo');
    http.expectNone((r) => r.url.includes('/inhabilitar'));
    c.cancel();
    expect(c.pendingAction()).toBeNull();

    c.startAction('inhabilitar', cell);
    c.motivo.setValue('  Mantenimiento ');
    c.confirmAction();
    const request = http.expectOne({ method: 'POST', url: '/celdas/1/inhabilitar' });
    expect(request.request.body).toEqual({ motivo: 'Mantenimiento' });
    request.flush({ ...cell, estado: 'INHABILITADA', motivo_estado: 'Mantenimiento' });
    http.expectOne(LISTA).flush(pagina([]));
    expect(c.success()).toContain('inhabilitada');
  });

  it('elimina con borrado lógico y motivo, sin usar DELETE (RF-15)', () => {
    const c = fixture.componentInstance;
    c.startAction('eliminar', cell);
    c.motivo.setValue('Se demolió');
    c.confirmAction();
    http.expectNone((r) => r.method === 'DELETE');
    const request = http.expectOne({ method: 'POST', url: '/celdas/1/eliminar' });
    expect(request.request.body).toEqual({ motivo: 'Se demolió' });
    request.flush({ ...cell, estado: 'ELIMINADA', motivo_estado: 'Se demolió' });
    http.expectOne(LISTA).flush(pagina([]));
    expect(c.success()).toContain('eliminada');
  });

  it('si la celda cambió de estado al confirmar, muestra el motivo y recarga', () => {
    const c = fixture.componentInstance;
    c.startAction('eliminar', cell);
    c.motivo.setValue('Ya no se usa');
    c.confirmAction();
    http
      .expectOne('/celdas/1/eliminar')
      .flush(
        { detail: 'La celda A-01 está ocupada: no se puede eliminar mientras tenga un vehículo.' },
        { status: 409, statusText: 'Conflict' },
      );
    expect(c.actionError()).toContain('ocupada');
    expect(c.pendingAction()).toBeNull();
    http.expectOne(LISTA).flush(pagina([cell]));
  });
});
