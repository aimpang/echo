import { describe, it, expect } from "vitest";
import { formatTimecode } from "./timecode";

describe("formatTimecode", () => {
  it("formats whole seconds with one decimal", () => {
    expect(formatTimecode(0)).toBe("0:00.0");
    expect(formatTimecode(5)).toBe("0:05.0");
  });

  it("formats sub-second values with one decimal", () => {
    expect(formatTimecode(1.25)).toBe("0:01.2");
    expect(formatTimecode(0.95)).toBe("0:00.9");
  });

  it("rolls minutes at 60 seconds", () => {
    expect(formatTimecode(60)).toBe("1:00.0");
    expect(formatTimecode(75.5)).toBe("1:15.5");
  });

  it("zero-pads the seconds component", () => {
    expect(formatTimecode(61)).toBe("1:01.0");
    expect(formatTimecode(119.9)).toBe("1:59.9");
  });

  it("clamps negatives to zero", () => {
    expect(formatTimecode(-5)).toBe("0:00.0");
  });

  it("handles NaN/Infinity gracefully", () => {
    expect(formatTimecode(NaN)).toBe("0:00.0");
    expect(formatTimecode(Infinity)).toBe("0:00.0");
  });
});
