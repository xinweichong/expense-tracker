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

describe('<HighlightCard>', () => {
  it('renders title and children', () => {
    const { getByText } = render(
      <HighlightCard title="On Track">76</HighlightCard>
    );
    expect(getByText('On Track')).toBeTruthy();
    expect(getByText('76')).toBeTruthy();
  });
});
