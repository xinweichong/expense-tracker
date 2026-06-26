import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { HeroCard, HighlightCard } from '../cards';

describe('<HeroCard>', () => {
  it('renders title and children', () => {
    const { getByText } = render(
      <HeroCard title="This Month">$1,247</HeroCard>
    );
    expect(getByText('This Month')).toBeTruthy();
    expect(getByText('$1,247')).toBeTruthy();
  });
});

describe('<HeroCard> glowColor prop', () => {
  it('applies hero-glow-warm class by default', () => {
    const { container } = render(<HeroCard title="Spent">$500</HeroCard>);
    expect(container.querySelector('.hero-glow-warm')).toBeTruthy();
  });

  it('applies hero-glow-teal when glowColor="teal"', () => {
    const { container } = render(
      <HeroCard title="Income" glowColor="teal">$2,000</HeroCard>
    );
    expect(container.querySelector('.hero-glow-teal')).toBeTruthy();
    expect(container.querySelector('.hero-glow-warm')).toBeNull();
  });

  it('applies hero-glow-coral when glowColor="coral"', () => {
    const { container } = render(
      <HeroCard title="Over Budget" glowColor="coral">$1,100</HeroCard>
    );
    expect(container.querySelector('.hero-glow-coral')).toBeTruthy();
  });
});

describe('<HighlightCard>', () => {
  it('renders title and children', () => {
    const { getByText } = render(
      <HighlightCard title="On Track">76</HighlightCard>
    );
    expect(getByText('On Track')).toBeTruthy();
    expect(getByText('76')).toBeTruthy();
  });
});
