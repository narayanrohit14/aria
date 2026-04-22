import type { Metadata } from "next"
import { Rajdhani, Share_Tech_Mono } from "next/font/google"

import { Navbar } from "@/components/layout/Navbar"
import "./globals.css"

const rajdhani = Rajdhani({
  subsets: ["latin"],
  variable: "--font-rajdhani",
  weight: ["300", "400", "600"],
})

const shareTechMono = Share_Tech_Mono({
  subsets: ["latin"],
  variable: "--font-share-tech-mono",
  weight: "400",
})

export const metadata: Metadata = {
  title: "ARIA | Audit Risk & Insights Agent",
  description: "AI-powered Internal Audit Intelligence Platform",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body
        className={`${rajdhani.variable} ${shareTechMono.variable} min-h-screen bg-[#0a0f0a] text-white antialiased`}
      >
        <Navbar />
        <main>{children}</main>
      </body>
    </html>
  )
}
