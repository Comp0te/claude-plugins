import { deleteUsers, Actor } from "../api/users";

export interface DeleteUsersRequest {
  actor: Actor;
  params: { ids: string[] };
}

export async function handleDeleteUsers(req: DeleteUsersRequest): Promise<{ status: number }> {
  await deleteUsers(req.actor, req.params.ids);
  return { status: 204 };
}

export async function handleListUsers(): Promise<{ status: number }> {
  return { status: 200 };
}
