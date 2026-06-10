import { describe, expect, it } from "vitest";
import { emptyExpertForm, parseList, slugify, validateExpert } from "./lib";

describe("slugify", () => {
  it("lowercases and dashes", () => {
    expect(slugify("Code Reviewer")).toBe("code-reviewer");
  });
  it("strips invalid chars and trims dashes", () => {
    expect(slugify("  My Expert!! v2 ")).toBe("my-expert-v2");
  });
});

describe("parseList", () => {
  it("splits on commas and newlines", () => {
    expect(parseList("Read, Grep\nGlob")).toEqual(["Read", "Grep", "Glob"]);
  });
  it("drops empties", () => {
    expect(parseList(" , ,")).toEqual([]);
  });
});

describe("validateExpert", () => {
  const base = { slug: "ok-slug", name: "Ok", autonomy: "off", interaction_mode: "auto" };

  it("accepts a valid expert", () => {
    expect(validateExpert(base)).toEqual([]);
  });
  it("rejects a bad slug", () => {
    expect(validateExpert({ ...base, slug: "Bad Slug" })).toContain(
      "slug must be lowercase alphanumeric with dashes",
    );
  });
  it("requires a name", () => {
    expect(validateExpert({ ...base, name: "  " })).toContain("name is required");
  });
  it("rejects invalid autonomy and mode", () => {
    const errs = validateExpert({ ...base, autonomy: "ultra", interaction_mode: "nope" });
    expect(errs).toContain("invalid autonomy");
    expect(errs).toContain("invalid interaction mode");
  });
});

describe("emptyExpertForm", () => {
  it("has safe defaults", () => {
    const f = emptyExpertForm();
    expect(f.autonomy).toBe("off");
    expect(f.interaction_mode).toBe("auto");
    expect(f.run_in_worktree).toBe(false);
    expect(f.skills).toEqual([]);
  });
});
