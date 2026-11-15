import { useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'

export interface ComboboxOption {
  value: string
  label: string
}

/** Select buscable (Popover + Command) para listas largas de opciones. */
export function Combobox({
  options,
  value,
  onValueChange,
  placeholder = 'Selecciona…',
  searchPlaceholder = 'Buscar…',
  emptyText = 'Sin resultados.',
  className,
}: {
  options: ComboboxOption[]
  value: string
  onValueChange: (value: string) => void
  placeholder?: string
  searchPlaceholder?: string
  emptyText?: string
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const selected = options.find((o) => o.value === value)

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          role="combobox"
          aria-expanded={open}
          className={cn(
            'flex h-9 w-full items-center justify-between gap-2 rounded-[var(--radius-card)] border border-border-strong bg-bg2 px-3 py-1 text-sm text-txt focus:outline-none focus:ring-2 focus:ring-accent/50 disabled:opacity-50',
            className,
          )}
        >
          <span className={cn('truncate', !selected && 'text-txt3')}>
            {selected ? selected.label : placeholder}
          </span>
          <ChevronDown className="size-4 shrink-0 text-txt3" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="p-0">
        <Command
          filter={(itemValue, search) => {
            const opt = options.find((o) => o.value === itemValue)
            return opt?.label.toLowerCase().includes(search.toLowerCase()) ? 1 : 0
          }}
        >
          <CommandInput placeholder={searchPlaceholder} />
          <CommandList>
            <CommandEmpty>{emptyText}</CommandEmpty>
            <CommandGroup>
              {options.map((o) => (
                <CommandItem
                  key={o.value}
                  value={o.value}
                  onSelect={(v) => {
                    onValueChange(v)
                    setOpen(false)
                  }}
                >
                  <Check className={cn('size-4 shrink-0', o.value === value ? 'opacity-100 text-accent2' : 'opacity-0')} />
                  {o.label}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
