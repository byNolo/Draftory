// Reusable transport cache: no baseball rules, persistent storage or global state.
export class SessionCache {
  private values = new Map<string, Promise<unknown>>();
  has(key: string) {
    return this.values.has(key);
  }
  clear() {
    this.values = new Map();
  }
  get<T>(key: string, load: () => Promise<T>): Promise<T> {
    const values = this.values;
    let promise = values.get(key) as Promise<T> | undefined;
    if (!promise) {
      promise = Promise.resolve().then(load);
      values.set(key, promise);
      const current = promise;
      void promise.catch(() => {
        if (values.get(key) === current) values.delete(key);
      });
    }
    // Callers cannot mutate another request's cached snapshot.
    return promise.then((value) => structuredClone(value));
  }
}
