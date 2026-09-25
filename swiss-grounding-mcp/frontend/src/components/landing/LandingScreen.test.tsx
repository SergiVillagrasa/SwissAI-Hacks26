import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { LandingScreen } from "./LandingScreen";

function renderLanding(overrides: Partial<Parameters<typeof LandingScreen>[0]> = {}) {
  const props = {
    disabled: false,
    onSubmit: vi.fn(),
    voiceState: "idle" as const,
    voiceActive: false,
    onMicClick: vi.fn(),
    onVoiceCancel: vi.fn(),
    voiceError: null,
    ...overrides,
  };
  render(<LandingScreen {...props} />);
  return props;
}

describe("LandingScreen", () => {
  it("renders the brand marks and the frosted search pill", () => {
    renderLanding();
    expect(screen.getByText(/swiss travel/i)).toBeInTheDocument();
    expect(screen.getByText(/by swisscom/i)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /swisscom/i })).toBeInTheDocument();
    expect(
      screen.getByRole("textbox", { name: /search your journey/i })
    ).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Buscar tus resultados...")).toBeInTheDocument();
  });

  it("opens the curtain canyon sweep while the search is focused", () => {
    renderLanding();
    const scene = screen.getByTestId("landing-screen");
    const input = screen.getByPlaceholderText("Buscar tus resultados...");

    expect(scene).toHaveAttribute("data-open", "false");
    fireEvent.focus(input);
    expect(scene).toHaveAttribute("data-open", "true");
    fireEvent.blur(input);
    expect(scene).toHaveAttribute("data-open", "false");
  });

  it("keeps the center clean when open — no cards or widgets render", () => {
    renderLanding();
    const input = screen.getByPlaceholderText("Buscar tus resultados...");
    fireEvent.focus(input);
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
    expect(screen.getByRole("search")).toBeInTheDocument();
  });

  it("submits the typed query", () => {
    const { onSubmit } = renderLanding();
    const input = screen.getByPlaceholderText("Buscar tus resultados...");
    fireEvent.change(input, { target: { value: "Bern to Zürich" } });
    fireEvent.submit(input.closest("form")!);
    expect(onSubmit).toHaveBeenCalledWith("Bern to Zürich");
  });

  it("opens while voice mode is active", () => {
    renderLanding({ voiceActive: true, voiceState: "listening" });
    expect(screen.getByTestId("landing-screen")).toHaveAttribute("data-open", "true");
    expect(screen.getByRole("button", { name: /stop and send/i })).toBeInTheDocument();
  });
});
