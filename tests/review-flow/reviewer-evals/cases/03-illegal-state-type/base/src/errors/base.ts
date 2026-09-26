export class ApiFetchError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiFetchError";
  }
}

export class TimeoutError extends Error {
  constructor(message: string = "request timed out") {
    super(message);
    this.name = "TimeoutError";
  }
}
