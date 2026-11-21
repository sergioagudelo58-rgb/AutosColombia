import { TARIFA_MENSUALIDAD, tarifaMensualidad } from './vehiculo';

describe('tarifas de la mensualidad (RN-12)', () => {
  it('carro y camioneta valen 250000', () => {
    expect(tarifaMensualidad('CARRO')).toBe('250000');
    expect(tarifaMensualidad('CAMIONETA')).toBe('250000');
  });

  it('moto vale 100000', () => {
    expect(tarifaMensualidad('MOTO')).toBe('100000');
  });

  it('un tipo desconocido no tiene tarifa', () => {
    expect(tarifaMensualidad('BUS')).toBe('');
  });

  it('las tarifas están definidas', () => {
    expect(TARIFA_MENSUALIDAD).toEqual({ CARRO: 250000, CAMIONETA: 250000, MOTO: 100000 });
  });
});
