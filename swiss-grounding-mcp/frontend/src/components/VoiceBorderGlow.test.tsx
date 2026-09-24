import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { VoiceBorderGlow } from "./VoiceBorderGlow";

describe("VoiceBorderGlow", () => {
  it("renders a non-interactive, viewport-fixed glow reflecting the current state and level", () => {
    const { container } = render(<VoiceBorderGlow state="listening" level={0.6} />);

    const glow = container.querySelector(".voice-border-glow");
    expect(glow).not.toBeNull();
    expect(glow).toHaveAttribute("data-state", "listening");
    expect(glow).toHaveAttribute("aria-hidden");
    expect((glow as HTMLElement).style.getPropertyValue("--level")).toBe("0.6");
  });
});
