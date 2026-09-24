import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Composer } from "./Composer";

describe("Composer", () => {
  it("calls onMicClick when the microphone button is clicked", () => {
    const onMicClick = vi.fn();
    render(
      <Composer disabled={false} onSubmit={vi.fn()} voiceState="idle" onMicClick={onMicClick} />
    );

    fireEvent.click(screen.getByRole("button", { name: /speak instead of typing/i }));

    expect(onMicClick).toHaveBeenCalledTimes(1);
  });

  it("disables the microphone button while a reply is pending", () => {
    render(<Composer disabled onSubmit={vi.fn()} voiceState="idle" onMicClick={vi.fn()} />);

    expect(screen.getByRole("button", { name: /speak instead of typing/i })).toBeDisabled();
  });

  it("keeps the microphone button enabled while listening, even mid-recording", () => {
    render(
      <Composer disabled={false} onSubmit={vi.fn()} voiceState="listening" onMicClick={vi.fn()} />
    );

    expect(screen.getByRole("button", { name: /stop and send/i })).toBeEnabled();
  });

  it("disables the microphone button while transcribing or speaking", () => {
    const { rerender } = render(
      <Composer disabled={false} onSubmit={vi.fn()} voiceState="processing" onMicClick={vi.fn()} />
    );
    expect(screen.getByRole("button", { name: /transcribing your voice/i })).toBeDisabled();

    rerender(
      <Composer disabled={false} onSubmit={vi.fn()} voiceState="speaking" onMicClick={vi.fn()} />
    );
    expect(screen.getByRole("button", { name: /assistant is speaking/i })).toBeDisabled();
  });

  it("does not draw the browser's default focus outline on the text field", () => {
    render(<Composer disabled={false} onSubmit={vi.fn()} voiceState="idle" onMicClick={vi.fn()} />);

    expect(screen.getByPlaceholderText(/ask about your journey/i)).toHaveClass(
      "quiet-focus-plain"
    );
  });
});
