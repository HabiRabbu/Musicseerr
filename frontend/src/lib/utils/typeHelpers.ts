export type Getter<T> = () => T;

export type MaybeGetter<T> = T | Getter<T>;
