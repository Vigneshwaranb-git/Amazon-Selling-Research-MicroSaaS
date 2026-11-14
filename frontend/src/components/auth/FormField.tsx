import type { InputHTMLAttributes } from 'react'
import { Input } from '@/components/ui/input'

interface FormFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  id: string
  label: string
  error?: string
}

export function FormField({ id, label, error, ...props }: FormFieldProps) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <Input id={id} aria-invalid={error ? true : undefined} aria-describedby={error ? `${id}-error` : undefined} {...props} />
      {error && (
        <p id={`${id}-error`} role="alert" className="text-xs text-red-500">
          {error}
        </p>
      )}
    </div>
  )
}

export function FormError({ message }: { message: string }) {
  return (
    <p role="alert" className="rounded-md bg-red-500/10 px-3 py-2 text-sm text-red-500">
      {message}
    </p>
  )
}
