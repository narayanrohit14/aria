export default function SessionLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return <div className="min-h-screen bg-[#030a04] p-0">{children}</div>
}
