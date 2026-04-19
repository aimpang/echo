import { describe, it, expect } from "vitest";
import {
  generateShareToken,
  isValidShareToken,
  SHARE_TOKEN_LENGTH,
} from "./token";

describe("generateShareToken", () => {
  it("returns a token of the documented length", () => {
    const token = generateShareToken();
    expect(token).toHaveLength(SHARE_TOKEN_LENGTH);
  });

  it("produces url-safe characters only", () => {
    for (let i = 0; i < 50; i++) {
      expect(generateShareToken()).toMatch(/^[A-Za-z0-9_-]+$/);
    }
  });

  it("is effectively unique across many calls", () => {
    const tokens = new Set<string>();
    for (let i = 0; i < 1000; i++) tokens.add(generateShareToken());
    expect(tokens.size).toBe(1000);
  });
});

describe("isValidShareToken", () => {
  it("accepts freshly generated tokens", () => {
    expect(isValidShareToken(generateShareToken())).toBe(true);
  });

  it("rejects tokens with the wrong length", () => {
    expect(isValidShareToken("abc")).toBe(false);
    expect(isValidShareToken("a".repeat(SHARE_TOKEN_LENGTH + 1))).toBe(false);
  });

  it("rejects tokens with disallowed characters", () => {
    const bad = "!".repeat(SHARE_TOKEN_LENGTH);
    expect(isValidShareToken(bad)).toBe(false);
  });

  it("rejects non-string input", () => {
    expect(isValidShareToken(undefined as unknown as string)).toBe(false);
    expect(isValidShareToken(null as unknown as string)).toBe(false);
    expect(isValidShareToken(123 as unknown as string)).toBe(false);
  });
});
