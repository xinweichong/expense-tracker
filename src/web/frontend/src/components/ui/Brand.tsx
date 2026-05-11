import type { CSSProperties } from 'react';

const WARM_GRADIENT = 'linear-gradient(135deg, #D97706, #EA580C 50%, #DC2626)';

const dollarStyle: CSSProperties = {
  background: WARM_GRADIENT,
  WebkitBackgroundClip: 'text',
  backgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
  color: 'transparent',
  margin: '0 -0.02em',
};

const tealStyle: CSSProperties = {
  color: '#00D4AA',
};

interface CasheWordmarkProps {
  size?: number;
  className?: string;
}

export function CasheWordmark({ size = 22, className }: CasheWordmarkProps) {
  const rootStyle: CSSProperties = {
    fontFamily: "'Plus Jakarta Sans', sans-serif",
    fontWeight: 800,
    letterSpacing: '-0.045em',
    lineHeight: 0.9,
    fontSize: `${size}px`,
    display: 'inline-flex',
    alignItems: 'baseline',
  };

  return (
    <span style={rootStyle} className={className} aria-label="cashe">
      <span style={tealStyle}>ca</span>
      <span style={dollarStyle}>$</span>
      <span style={tealStyle}>he</span>
    </span>
  );
}

interface CasheIconProps {
  size?: number;
  className?: string;
}

export function CasheIcon({ size = 32, className }: CasheIconProps) {
  const wrapStyle: CSSProperties = {
    width: `${size}px`,
    height: `${size}px`,
    background: '#00D4AA',
    borderRadius: '22%',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
  };

  const glyphStyle: CSSProperties = {
    fontFamily: "'Plus Jakarta Sans', sans-serif",
    fontWeight: 800,
    fontSize: `${Math.round(size * 0.75)}px`,
    letterSpacing: '-0.02em',
    lineHeight: 1,
    background: WARM_GRADIENT,
    WebkitBackgroundClip: 'text',
    backgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    color: 'transparent',
    marginTop: '-0.05em',
  };

  return (
    <span style={wrapStyle} className={className} aria-label="cashe">
      <span style={glyphStyle}>$</span>
    </span>
  );
}
