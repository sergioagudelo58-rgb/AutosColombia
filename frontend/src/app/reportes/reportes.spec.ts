import { sesionDePrueba } from '../testing/auth';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { hoyColombia } from '../shared/formato';
import { Reportes, TAMANO_PAGINA } from './reportes';

const reporte = {
  generado_en: '2026-10-18T13:00:00Z',
  desde: '2026-10-18',
  hasta: '2026-10-18',
  clientes_registrados: 90,
  vehiculos_registrados: 112,
  vehiculos_por_tipo: { MOTO: 12, CARRO: 80, CAMIONETA: 20 },
  vehiculos_adentro: 53,
  cupos: [
    {
      tipo_celda: 'CARRO_CAMIONETA',
      nombre: 'carros y camionetas',
      total: 70,
      ocupadas: 47,
      disponibles: 23,
    },
    { tipo_celda: 'MOTO', nombre: 'motos', total: 10, ocupadas: 6, disponibles: 4 },
  ],
  celdas_total: 80,
  celdas_ocupadas: 53,
  celdas_disponibles: 27,
  porcentaje_ocupacion: 66.3,
  entradas: 40,
  salidas: 25,
  novedades: 2,
};

describe('Reportes', () => {
  let http: HttpTestingController;
  let c: Reportes;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [Reportes],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        sesionDePrueba('ADMINISTRADOR', null),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    c = TestBed.createComponent(Reportes).componentInstance;
  });
  afterEach(() => http.verify());

  it('genera el reporte del día actual al abrir (RF-10)', () => {
    const hoy = hoyColombia();
    const req = http.expectOne(`/reportes/ocupacion?desde=${hoy}&hasta=${hoy}`);
    req.flush(reporte);
    expect(c.reporte()?.porcentaje_ocupacion).toBe(66.3);
    expect(c.tiposVehiculo(c.reporte()!).length).toBe(3);
  });

  it('valida el rango antes de consultar', () => {
    http.expectOne((r) => r.url === '/reportes/ocupacion').flush(reporte);
    c.rango.setValue({ desde: '2026-10-19', hasta: '2026-10-18' });
    c.generar();
    expect(c.errorReporte()).toContain('posterior');
    http.expectNone((r) => r.url === '/reportes/ocupacion');
  });

  it('filtra el historial por placa, cliente y fechas y pagina (RF-11)', () => {
    http.expectOne((r) => r.url === '/reportes/ocupacion').flush(reporte);
    c.filtros.setValue({ placa: 'kdt 482', cliente: ' Laura ', desde: '2026-10-01', hasta: '' });
    c.buscar();
    const req = http.expectOne((r) => r.url === '/reportes/historial');
    expect(req.request.params.get('placa')).toBe('KDT482');
    expect(req.request.params.get('cliente')).toBe('Laura');
    expect(req.request.params.get('desde')).toBe('2026-10-01');
    expect(req.request.params.has('hasta')).toBe(false);
    expect(req.request.params.get('limit')).toBe(String(TAMANO_PAGINA));
    req.flush({ items: [], total: 45, offset: 0, limit: TAMANO_PAGINA });
    c.pagina(TAMANO_PAGINA);
    const siguiente = http.expectOne((r) => r.url === '/reportes/historial');
    expect(siguiente.request.params.get('offset')).toBe(String(TAMANO_PAGINA));
    expect(siguiente.request.params.get('placa')).toBe('KDT482');
    siguiente.flush({ items: [], total: 45, offset: TAMANO_PAGINA, limit: TAMANO_PAGINA });
  });

  it('exporta a Excel un CSV con fecha y usuario', async () => {
    http.expectOne((r) => r.url === '/reportes/ocupacion').flush(reporte);
    let blob: Blob | undefined;
    const crear = vi.spyOn(URL, 'createObjectURL').mockImplementation((b) => {
      blob = b as Blob;
      return 'blob:reporte';
    });
    const revocar = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    const clic = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    c.exportarExcel();
    const texto = await blob!.text();
    expect(texto).toContain('"Generado por";"Laura Gómez (lgomez)"');
    expect(texto).toContain('"Porcentaje de ocupación";"66.3 %"');
    expect(clic).toHaveBeenCalled();
    crear.mockRestore();
    revocar.mockRestore();
    clic.mockRestore();
  });
});
