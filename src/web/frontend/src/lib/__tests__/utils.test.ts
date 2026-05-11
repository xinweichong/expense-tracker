import { describe, it, expect } from 'vitest';
import { nearestSpectrum, PALETTE } from '../utils';

describe('nearestSpectrum', () => {
  it('returns the input color if it is already in the palette', () => {
    expect(nearestSpectrum('#00D4AA')).toBe('#00D4AA');
    expect(nearestSpectrum('#FF6B6B')).toBe('#FF6B6B');
  });

  it('snaps a near-teal color to teal', () => {
    expect(nearestSpectrum('#00D2A8')).toBe('#00D4AA');
  });

  it('snaps a near-coral color to coral', () => {
    expect(nearestSpectrum('#FF6F70')).toBe('#FF6B6B');
  });

  it('snaps a generic red into the warm end of the palette', () => {
    const result = nearestSpectrum('#FF0000');
    expect(['#FB923C', '#FB7185', '#FF6B6B', '#F97316']).toContain(result);
  });

  it('falls back to the first palette color for invalid input', () => {
    expect(nearestSpectrum('not-a-hex')).toBe(PALETTE[0]);
  });
});
