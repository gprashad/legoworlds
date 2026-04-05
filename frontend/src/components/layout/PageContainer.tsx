export function PageContainer({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-bg">
      {children}
    </div>
  )
}
