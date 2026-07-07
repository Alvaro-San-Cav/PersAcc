import { cn } from '@/lib/utils'

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('animate-pulse rounded-[var(--radius-card)] bg-card3/60', className)}
      {...props}
    />
  )
}

export { Skeleton }
