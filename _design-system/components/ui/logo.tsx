import { cn } from '../../lib/utils'

type LogoVariant = 'full' | 'compact' | 'tagline'
type LogoSize = 'sm' | 'md' | 'lg'

export interface LogoProps {
  variant?: LogoVariant
  size?: LogoSize
  className?: string
}

const sizeStyles: Record<LogoSize, { text: string; slash: string; tagline: string }> = {
  sm: { text: 'text-xl', slash: 'text-xl', tagline: 'text-[10px]' },
  md: { text: 'text-3xl', slash: 'text-3xl', tagline: 'text-xs' },
  lg: { text: 'text-5xl', slash: 'text-5xl', tagline: 'text-sm' },
}

/**
 * Logo JulIA
 *
 * - full:    Jul/IA
 * - compact: J/
 * - tagline: Jul/IA + subtitulo
 *
 * A barra "/" e angular e usa a cor accent.
 * "Jul" em peso regular, "IA" em bold.
 */
function Logo({ variant = 'full', size = 'md', className }: LogoProps) {
  const s = sizeStyles[size]

  if (variant === 'compact') {
    return (
      <span
        className={cn(
          'inline-flex items-baseline font-brand leading-none select-none',
          s.text,
          className
        )}
      >
        <span className="font-semibold text-text-primary tracking-tight">J</span>
        <span
          className="font-bold text-accent -mx-[0.05em]"
          style={{ transform: 'skewX(-8deg)', display: 'inline-block' }}
          aria-hidden="true"
        >
          /
        </span>
      </span>
    )
  }

  return (
    <span
      className={cn(
        'inline-flex flex-col items-start select-none',
        className
      )}
    >
      <span
        className={cn(
          'inline-flex items-baseline font-brand leading-none',
          s.text
        )}
      >
        <span className="font-regular text-text-primary tracking-tight">Jul</span>
        <span
          className="font-bold text-accent -mx-[0.05em]"
          style={{ transform: 'skewX(-8deg)', display: 'inline-block' }}
          aria-hidden="true"
        >
          /
        </span>
        <span className="font-bold text-text-primary tracking-tight">IA</span>
      </span>

      {variant === 'tagline' && (
        <span
          className={cn(
            'font-heading font-medium text-text-tertiary uppercase tracking-widest mt-1',
            s.tagline
          )}
        >
          Engineering Intelligence
        </span>
      )}
    </span>
  )
}

Logo.displayName = 'Logo'
export { Logo }
