export interface ApiKey {
  id: number
  name: string
  prefix: string
  created_at: string
  last_used_at: string | null
}

export interface ApiKeyCreated extends ApiKey {
  key: string
}
