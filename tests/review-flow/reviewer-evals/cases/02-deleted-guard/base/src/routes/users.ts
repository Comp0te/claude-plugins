import { deleteUser, Actor } from "../api/users";

export interface DeleteUserRequest {
  actor: Actor;
  params: { id: string };
}

export async function handleDeleteUser(req: DeleteUserRequest): Promise<{ status: number }> {
  await deleteUser(req.actor, req.params.id);
  return { status: 204 };
}
