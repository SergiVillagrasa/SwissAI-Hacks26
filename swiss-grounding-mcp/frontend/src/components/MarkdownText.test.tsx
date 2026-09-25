import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MarkdownText } from "./MarkdownText";

describe("MarkdownText", () => {
  it("renders plain text unchanged", () => {
    render(<MarkdownText>Hello world</MarkdownText>);
    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  it("renders bold text with a strong element", () => {
    render(<MarkdownText>Hello **world**</MarkdownText>);
    const strong = screen.getByText("world");
    expect(strong.tagName).toBe("STRONG");
  });

  it("renders italic text with an em element", () => {
    render(<MarkdownText>Hello *world*</MarkdownText>);
    const em = screen.getByText("world");
    expect(em.tagName).toBe("EM");
  });

  it("renders a markdown link", () => {
    render(<MarkdownText>[link](https://example.com)</MarkdownText>);
    const link = screen.getByRole("link", { name: "link" });
    expect(link).toHaveAttribute("href", "https://example.com");
  });
});
