export interface LegacyRequestState<T> {
  loading: boolean;
  data: T | null;
  error: Error | null;
}

export function initialState<T>(): LegacyRequestState<T> {
  return { loading: false, data: null, error: null };
}
