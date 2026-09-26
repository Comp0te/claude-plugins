import { describe, it, expect } from "vitest";
import { deleteUser } from "../src/api/users";

describe("deleteUser", () => {
  it("rejects a non-admin actor", async () => {
    await expect(
      deleteUser({ id: "u2", roles: ["member"] }, "1")
    ).rejects.toThrow("lacks admin role");
  });

  it("deletes for an admin actor", async () => {
    await expect(
      deleteUser({ id: "u1", roles: ["admin"] }, "1")
    ).resolves.toBeUndefined();
  });

  it("rejects an id that does not exist", async () => {
    await expect(
      deleteUser({ id: "u1", roles: ["admin"] }, "999")
    ).rejects.toThrow("not found");
  });
});
