import { Loader2 } from 'lucide-react'

export default function LoadingSpinner({ size = 'md', text = '' }) {
  const sizes = { sm: 'h-4 w-4', md: 'h-6 w-6', lg: 'h-8 w-8' }

  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12">
      <Loader2 className={`${sizes[size]} animate-spin text-blue-500`} />
      {text && <span className="text-sm text-gray-500">{text}</span>}
    </div>
  )
}
