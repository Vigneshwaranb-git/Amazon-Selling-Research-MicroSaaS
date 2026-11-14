import { useId, useRef, useState, type DragEvent } from 'react'
import { CSV_ACCEPT } from '@/lib/files'
import { cn } from '@/lib/utils'

interface CsvDropzoneProps {
  label: string
  file: File | null
  disabled?: boolean
  onFile: (file: File) => void
}

/** Keyboard-accessible CSV picker (native file input) with optional drag-and-drop. */
export function CsvDropzone({ label, file, disabled = false, onFile }: CsvDropzoneProps) {
  const inputId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragging(false)
    if (disabled) return
    const dropped = e.dataTransfer.files[0]
    if (dropped) onFile(dropped)
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        if (!disabled) setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={cn(
        'rounded-md border border-dashed p-4 text-sm',
        dragging && 'border-primary bg-accent',
      )}
    >
      <label htmlFor={inputId} className="block font-medium">
        {label}
      </label>
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={CSV_ACCEPT}
        disabled={disabled}
        className="mt-2 block w-full text-sm"
        onChange={(e) => {
          const picked = e.target.files?.[0]
          if (picked) onFile(picked)
          e.target.value = ''
        }}
      />
      <p className="mt-2 text-xs text-muted-foreground">
        {file ? `Selected: ${file.name}` : 'Choose a CSV file or drop it here (max 1 MB, 1000 rows).'}
      </p>
    </div>
  )
}
