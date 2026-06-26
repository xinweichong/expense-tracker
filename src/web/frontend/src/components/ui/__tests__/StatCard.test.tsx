import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { StatCard } from '../StatCard';

describe('<StatCard>', () => {
  it('renders label and string value', () => {
    const { getByText } = render(<StatCard label="Total Spent" value="$1,247.00" />);
    expect(getByText('Total Spent')).toBeTruthy();
    expect(getByText('$1,247.00')).toBeTruthy();
  });

  it('renders delta badge when delta prop is provided', () => {
    const { container } = render(
      <StatCard label="Spent" value="$500" delta={{ value: 12.5 }} />
    );
    expect(container.textContent).toContain('12.5%');
  });

  it('applies teal color class when color="teal"', () => {
    const { container } = render(<StatCard label="Income" value="$2,000" color="teal" />);
    const valueEl = container.querySelector('[data-testid="stat-value"]');
    expect(valueEl?.className).toContain('text-teal');
  });

  it('renders sparkline svg when sparklineData provided', () => {
    const { container } = render(
      <StatCard label="Daily" value="$42" sparklineData={[10, 20, 15, 30, 25]} />
    );
    expect(container.querySelector('svg')).toBeTruthy();
  });

  it('applies hero-glow-warm class when hero=true and color="warm"', () => {
    const { container } = render(
      <StatCard label="Total" value="$1,247" hero color="warm" />
    );
    expect(container.querySelector('.hero-glow-warm')).toBeTruthy();
  });
});
