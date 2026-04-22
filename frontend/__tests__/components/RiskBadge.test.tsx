import { render, screen } from "@testing-library/react"

import { RiskBadge } from "@/components/ui/RiskBadge"

describe("RiskBadge", () => {
  test("renders HIGH badge with correct text", () => {
    render(<RiskBadge level="HIGH" />)

    expect(screen.getByText("HIGH")).toBeInTheDocument()
  })

  test("renders MEDIUM badge", () => {
    render(<RiskBadge level="MEDIUM" />)

    expect(screen.getByText("MEDIUM")).toBeInTheDocument()
  })

  test("renders LOW badge", () => {
    render(<RiskBadge level="LOW" />)

    expect(screen.getByText("LOW")).toBeInTheDocument()
  })

  test("renders unknown level without crashing", () => {
    render(<RiskBadge level="UNKNOWN" />)

    expect(screen.getByText("UNKNOWN")).toBeInTheDocument()
  })
})
