import { describe, expect, it } from "vitest";
import {
  TriggerForm,
  emptyExpertForm,
  emptyTriggerForm,
  eventVarsForSource,
  parseCondition,
  parseList,
  slugify,
  validateExpert,
  validateTrigger,
} from "./lib";

describe("eventVarsForSource", () => {
  it("returns github event variables", () => {
    expect(eventVarsForSource("github")).toContain("external_ref");
    expect(eventVarsForSource("github")).toContain("number");
  });
  it("returns linear event variables", () => {
    expect(eventVarsForSource("linear")).toContain("identifier");
  });
  it("returns empty for unknown sources", () => {
    expect(eventVarsForSource("nope")).toEqual([]);
  });
});

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
    expect(f.autonomy).toBe("high");
    expect(f.interaction_mode).toBe("auto");
    expect(f.run_in_worktree).toBe(false);
    expect(f.skills).toEqual([]);
  });
});

describe("parseCondition", () => {
  it("accepts an empty condition", () => {
    expect(parseCondition("  ")).toEqual({ ok: true, value: {} });
  });
  it("parses a JSON object", () => {
    expect(parseCondition('{"action":"opened"}')).toEqual({
      ok: true,
      value: { action: "opened" },
    });
  });
  it("rejects invalid JSON", () => {
    expect(parseCondition("{nope}").ok).toBe(false);
  });
  it("rejects non-objects", () => {
    expect(parseCondition("[1,2]").ok).toBe(false);
  });
});

describe("validateTrigger", () => {
  const base: TriggerForm = { ...emptyTriggerForm(), expert_slug: "code-reviewer" };

  it("accepts a valid trigger", () => {
    expect(validateTrigger(base, ["code-reviewer"])).toEqual([]);
  });
  it("requires a known expert", () => {
    expect(validateTrigger(base, ["other"])).toContain("select a valid expert");
  });
  it("rejects an invalid source", () => {
    expect(validateTrigger({ ...base, source: "gitlab" }, ["code-reviewer"])).toContain(
      "invalid source",
    );
  });
  it("flags bad condition JSON", () => {
    expect(
      validateTrigger({ ...base, conditionText: "{bad}" }, ["code-reviewer"]),
    ).toContain("condition must be valid JSON");
  });
});
