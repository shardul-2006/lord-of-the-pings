import { useState, useRef, useCallback } from 'react'
import { UploadIcon, FileIcon } from './icons'

interface Props {
  onFile: (file: File) => void
  accept?: string
  maxSizeMB?: number
  disabled?: boolean
}

const ACCEPT_TYPES = ['.pdf', '.md', '.markdown', '.html', '.htm']

export function DropZone({ onFile, accept, maxSizeMB = 200, disabled }: Props) {
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const validate = useCallback((file: File) => {
    setError('')
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    const allowed = accept ? accept.split(',') : ACCEPT_TYPES
    if (!allowed.includes(ext)) {
      setError(`Unsupported: ${ext}. Accepts ${allowed.join(', ')}.`)
      return false
    }
    if (file.size > maxSizeMB * 1024 * 1024) {
      setError(`Too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Max ${maxSizeMB} MB.`)
      return false
    }
    return true
  }, [maxSizeMB, accept])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    if (disabled) return
    const file = e.dataTransfer.files[0]
    if (file && validate(file)) {
      setSelectedFile(file)
      onFile(file)
    }
  }, [disabled, validate, onFile])

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file && validate(file)) {
      setSelectedFile(file)
      onFile(file)
    }
  }, [validate, onFile])

  return (
    <div
      className={`dropzone ${dragOver ? 'dropzone--active' : ''} ${disabled ? 'dropzone--disabled' : ''}`}
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
    >
      {/* SecOps HUD Brackets in 4 corners */}
      <span className="hud-corner hud-corner--tl" />
      <span className="hud-corner hud-corner--tr" />
      <span className="hud-corner hud-corner--bl" />
      <span className="hud-corner hud-corner--br" />

      <input
        ref={inputRef}
        type="file"
        accept={accept || ACCEPT_TYPES.join(',')}
        onChange={handleChange}
        hidden
      />
      {selectedFile ? (
        <div className="dropzone-selected fade-in">
          <div className="file-icon-glow">
            <FileIcon size={28} color="#3b82f6" />
          </div>
          <div>
            <div className="dropzone-filename">{selectedFile.name}</div>
            <div className="dropzone-filesize">
              {(selectedFile.size / 1024).toFixed(1)} KB &middot;{' '}
              <span className="file-chip-badge">{selectedFile.name.split('.').pop()?.toUpperCase()}</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="dropzone-empty">
          <div className="upload-icon-pulse">
            <UploadIcon size={32} color="#3b82f6" />
          </div>
          <div className="dropzone-text">Drop document here or click to browse</div>
          <div className="dropzone-hint">
            {accept ? accept.replace(/\./g, '').toUpperCase() : 'PDF, MD, HTML'} &middot; {maxSizeMB} MB max &middot; Fail-Closed Guard
          </div>
        </div>
      )}
      {error && <div className="dropzone-error fade-in">{error}</div>}
    </div>
  )
}
