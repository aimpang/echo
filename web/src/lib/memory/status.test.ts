import { describe, it, expect } from "vitest";
import {
  MEMORY_STATUSES,
  TERMINAL_STATUSES,
  canTransition,
  transition,
  isTerminal,
  type MemoryStatus,
  type MemoryEvent,
} from "./status";

describe("MEMORY_STATUSES", () => {
  it("includes all documented states", () => {
    expect(MEMORY_STATUSES).toEqual(
      expect.arrayContaining([
        "uploading",
        "scanning",
        "processing",
        "ready",
        "upload_failed",
        "rejected",
        "processing_failed",
      ]),
    );
  });
});

describe("isTerminal", () => {
  it.each([
    ["ready", true],
    ["upload_failed", true],
    ["rejected", true],
    ["processing_failed", true],
    ["uploading", false],
    ["scanning", false],
    ["processing", false],
  ] as const)("%s -> %s", (status, expected) => {
    expect(isTerminal(status)).toBe(expected);
  });

  it("exports terminal set matching isTerminal", () => {
    for (const s of MEMORY_STATUSES) {
      expect(TERMINAL_STATUSES.includes(s)).toBe(isTerminal(s));
    }
  });
});

describe("canTransition", () => {
  it("allows the happy path", () => {
    expect(canTransition("uploading", "scanning")).toBe(true);
    expect(canTransition("scanning", "processing")).toBe(true);
    expect(canTransition("processing", "ready")).toBe(true);
  });

  it("allows documented failure branches", () => {
    expect(canTransition("uploading", "upload_failed")).toBe(true);
    expect(canTransition("scanning", "rejected")).toBe(true);
    expect(canTransition("scanning", "processing_failed")).toBe(true);
    expect(canTransition("processing", "processing_failed")).toBe(true);
  });

  it("forbids skipping states", () => {
    expect(canTransition("uploading", "ready")).toBe(false);
    expect(canTransition("uploading", "processing")).toBe(false);
  });

  it("forbids moving out of terminal states", () => {
    for (const terminal of TERMINAL_STATUSES) {
      for (const target of MEMORY_STATUSES) {
        if (target === terminal) continue;
        expect(canTransition(terminal, target)).toBe(false);
      }
    }
  });

  it("forbids backwards transitions", () => {
    expect(canTransition("processing", "scanning")).toBe(false);
    expect(canTransition("scanning", "uploading")).toBe(false);
  });
});

describe("transition", () => {
  it("advances through the happy path via events", () => {
    let s: MemoryStatus = "uploading";
    s = transition(s, "upload_completed");
    expect(s).toBe("scanning");
    s = transition(s, "scan_passed");
    expect(s).toBe("processing");
    s = transition(s, "processing_completed");
    expect(s).toBe("ready");
  });

  it("handles rejection branch", () => {
    expect(transition("scanning", "scan_rejected")).toBe("rejected");
  });

  it("throws on invalid event for current state", () => {
    expect(() =>
      transition("uploading", "processing_completed" satisfies MemoryEvent),
    ).toThrow();
  });

  it("throws when applying events to terminal states", () => {
    expect(() => transition("ready", "upload_completed")).toThrow();
  });
});
