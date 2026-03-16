declare module 'undici' {
  export class Agent {
    constructor(options?: {
      bodyTimeout?: number
      headersTimeout?: number
      connectTimeout?: number
    })
  }
}
