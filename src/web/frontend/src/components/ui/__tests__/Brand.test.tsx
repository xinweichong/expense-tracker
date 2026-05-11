import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { CasheWordmark, CasheIcon } from '../Brand';

describe('<CasheWordmark>', () => {
  it('renders the lowercase "ca$he" with three segments', () => {
    const { container } = render(<CasheWordmark size={36} />);
    expect(container.textContent).toBe('ca$he');
    expect(container.querySelectorAll('span').length).toBeGreaterThanOrEqual(3);
  });

  it('applies the requested font-size', () => {
    const { container } = render(<CasheWordmark size={48} />);
    const root = container.firstChild as HTMLElement;
    expect(root.style.fontSize).toBe('48px');
  });
});

describe('<CasheIcon>', () => {
  it('renders a $ glyph inside a container with the requested size', () => {
    const { container } = render(<CasheIcon size={32} />);
    const root = container.firstChild as HTMLElement;
    expect(root.style.width).toBe('32px');
    expect(root.style.height).toBe('32px');
    expect(container.textContent).toContain('$');
  });
});
