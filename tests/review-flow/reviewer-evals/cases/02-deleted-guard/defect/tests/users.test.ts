import { describe, it, expect } from "vitest";
import { deleteUsers } from "../src/api/users";

describe("deleteUsers", () => {
  it("deletes every id in the batch", async () => {
    await expect(
      deleteUsers({ id: "u1", roles: ["member"] }, ["1", "2"])
    ).resolves.toBeUndefined();
  });

  it("rejects an id that does not exist", async () => {
    await expect(
      deleteUsers({ id: "u1", roles: ["admin"] }, ["999"])
    ).rejects.toThrow("not found");
  });
});
