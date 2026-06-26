// src/web/frontend/src/lib/animations.ts
import { useEffect } from 'react'
import { animate, useMotionValue, useTransform, motion } from 'framer-motion'
import type { Variants } from 'framer-motion'
import { formatCurrency } from './utils'

// ─── Spring presets ──────────────────────────────────────────────────────────
export const springs = {
  gentle: { type: 'spring' as const, stiffness: 200, damping: 25 },
  snappy: { type: 'spring' as const, stiffness: 350, damping: 30 },
  bouncy: { type: 'spring' as const, stiffness: 400, damping: 20 },
  expo:   { type: 'tween'  as const, ease: [0.16, 1, 0.3, 1] as const, duration: 0.4 },
}

// ─── Page transition ─────────────────────────────────────────────────────────
export const pageVariants: Variants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: springs.gentle },
  exit:    { opacity: 0, y: -4, transition: { duration: 0.12, ease: 'easeIn' as const } },
}

// ─── Fade up (form expand, card entrance) ────────────────────────────────────
export const fadeUpVariants: Variants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: springs.gentle },
  exit:    { opacity: 0, y: 8,  transition: { duration: 0.12, ease: 'easeIn' as const } },
}

// ─── Slide in from right (detail panels) ─────────────────────────────────────
export const slideInRightVariants: Variants = {
  initial: { opacity: 0, x: 32 },
  animate: { opacity: 1, x: 0, transition: springs.snappy },
  exit:    { opacity: 0, x: 32, transition: { duration: 0.15, ease: 'easeIn' as const } },
}

// ─── Slide up from bottom (BottomTabs drawer) ────────────────────────────────
export const slideUpVariants: Variants = {
  initial: { y: '100%' },
  animate: { y: 0, transition: springs.snappy },
  exit:    { y: '100%', transition: { duration: 0.2, ease: 'easeIn' as const } },
}

// ─── Stagger container ────────────────────────────────────────────────────────
export const staggerContainerVariants: Variants = {
  initial: {},
  animate: { transition: { staggerChildren: 0.04, delayChildren: 0.05 } },
}

// ─── Stagger item (child of staggerContainer) ─────────────────────────────────
export const staggerItemVariants: Variants = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0, transition: springs.gentle },
  exit:    { opacity: 0, transition: { duration: 0.1 } },
}

// ─── Animated currency number ─────────────────────────────────────────────────
// Counts from 0 to `value` on mount and whenever `value` changes.
interface AnimatedCurrencyProps {
  value: number
  currency?: string
}

export function AnimatedCurrency({ value, currency = 'SGD' }: AnimatedCurrencyProps) {
  const motionValue = useMotionValue(0)
  const formatted = useTransform(motionValue, (v) => formatCurrency(v, currency))

  useEffect(() => {
    const controls = animate(motionValue, value, { duration: 0.7, ease: 'easeOut' })
    return controls.stop
  }, [value, motionValue])

  return <motion.span>{formatted}</motion.span>
}

// ─── Count-up hook ────────────────────────────────────────────────────────────
export function useCountUp(target: number, duration = 0.7) {
  const motionValue = useMotionValue(0)
  useEffect(() => {
    const controls = animate(motionValue, target, { duration, ease: 'easeOut' })
    return controls.stop
  }, [target, motionValue, duration])
  return motionValue
}

// ─── Delta badge ─────────────────────────────────────────────────────────────
// value = signed percentage vs prior period (positive = more spend = worse for expenses)
interface DeltaBadgeProps {
  value: number
  label?: string
  invert?: boolean  // set true when more = good (income, savings)
}

export function DeltaBadge({ value, label, invert = false }: DeltaBadgeProps) {
  const isUp = value >= 0
  const isBad = invert ? !isUp : isUp
  const color = isBad ? '#FF6B6B' : '#34D399'
  const arrow = isUp ? '▲' : '▼'
  return (
    <motion.span
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={springs.bouncy}
      className="inline-flex items-center gap-0.5 text-[10px] font-mono font-bold px-1.5 py-0.5 rounded-full"
      style={{ color, background: `${color}1A` }}
    >
      {arrow}{Math.abs(value).toFixed(1)}%{label ? ` ${label}` : ''}
    </motion.span>
  )
}

// ─── Sparkline ────────────────────────────────────────────────────────────────
interface SparklineProps {
  data: number[]
  color?: string
  width?: number
  height?: number
}

export function Sparkline({ data, color = '#00D4AA', width = 60, height = 24 }: SparklineProps) {
  if (!data || data.length < 2) return null
  const max = Math.max(...data)
  const min = Math.min(...data)
  const range = max - min || 1
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width
    const y = height - ((v - min) / range) * (height - 2)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden>
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
