import { describe, it, expect } from "vitest";
import { safeNextPath } from "./safe-next";

describe("safeNextPath", () => {
  it("returns the fallback when next is null", () => {
    expect(safeNextPath(null)).toBe("/dashboard");
  });

  it("returns the fallback when next is empty", () => {
    expect(safeNextPath("")).toBe("/dashboard");
  });

  it("returns a plain same-origin absolute path unchanged", () => {
    expect(safeNextPath("/memories")).toBe("/memories");
  });

  it("preserves query and fragment on a relative path", () => {
    expect(safeNextPath("/memories?tab=new#top")).toBe("/memories?tab=new#top");
  });

  it("rejects an absolute http URL (open-redirect)", () => {
    expect(safeNextPath("http://evil.example/steal")).toBe("/dashboard");
  });

  it("rejects an absolute https URL (open-redirect)", () => {
    expect(safeNextPath("https://evil.example/steal")).toBe("/dashboard");
  });

  it("rejects a protocol-relative URL", () => {
    expect(safeNextPath("//evil.example/steal")).toBe("/dashboard");
  });

  it("rejects a backslash-prefixed URL that some browsers treat as protocol-relative", () => {
    expect(safeNextPath("/\\evil.example/steal")).toBe("/dashboard");
  });

  it("rejects a path that doesn't start with /", () => {
    expect(safeNextPath("dashboard")).toBe("/dashboard");
  });

  it("rejects a javascript: scheme", () => {
    expect(safeNextPath("javascript:alert(1)")).toBe("/dashboard");
  });

  it("accepts a caller-supplied fallback", () => {
    expect(safeNextPath(null, "/login")).toBe("/login");
  });
});
