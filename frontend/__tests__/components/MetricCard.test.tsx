import { render, screen } from "@testing-library/react"

import { MetricCard } from "@/components/ui/MetricCard"

describe("MetricCard", () => {
  test("renders label and value", () => {
    render(
      <MetricCard
        label="F1 Score"
        value="0.58"
      />,
    )

    expect(screen.getByText("F1 Score")).toBeInTheDocument()
    expect(screen.getByText("0.58")).toBeInTheDocument()
  })

  test("renders subValue when provided", () => {
    render(
      <MetricCard
        label="Test"
        value="1.0"
        subValue="± 0.02"
      />,
    )

    expect(screen.getByText("± 0.02")).toBeInTheDocument()
  })

  test("renders without subValue without crashing", () => {
    render(
      <MetricCard
        label="Test"
        value="42"
      />,
    )

    expect(screen.getByText("Test")).toBeInTheDocument()
    expect(screen.getByText("42")).toBeInTheDocument()
  })
})
