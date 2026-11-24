import { Loader } from './icons'

interface Props {
  filename: string
  stage?: string
}

export function ScanProgress({ filename, stage }: Props) {
  return (
    <div className="scan-progress slide-up">
      <div className="scan-progress-bar">
        <div className="scan-progress-fill" />
      </div>
      <div className="scan-progress-info">
        <Loader size={16} />
        <span>Screening <strong>{filename}</strong>{stage ? ` \u2014 ${stage}` : '...'}</span>
      </div>
    </div>
  )
}
