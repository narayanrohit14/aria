import Image from "next/image"

type DTCCLogoProps = {
  className?: string
}

export function DTCCLogo({ className }: DTCCLogoProps) {
  return (
    <Image
      src="/dtcc-logo.png"
      alt="DTCC"
      width={512}
      height={124}
      className={className}
      priority={false}
    />
  )
}
