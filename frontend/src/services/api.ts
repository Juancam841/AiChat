
const API_URL = (
  import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
).replace(/\/+$/, '')

export interface ChatRequest {
  conversation_id: string | null
  message: string
  provider: string
  model: string
  strategy: ChatStrategy
  web_search: boolean
}

export type ChatStrategy = 'manual' | 'free_first' | 'best_available'

export interface SearchResult {
  title: string | null
  url: string | null
  content: string | null
  published_date?: string | null
}

export interface ChatResponse {
  conversation_id: string
  response: string
  model: string
  provider: string
  results: SearchResult[]
}

export interface ProvidersResponse {
  configured: string[]
  supported: string[]
  available: string[]
}

export interface AIModel {
  id: string
  name: string
  type: string
}

export interface ModelsResponse {
  models: AIModel[]
}

export interface Message {
  id?: number
  role: 'user' | 'assistant'
  content: string
  results?: SearchResult[]
}

export interface Conversation {
  id: string
  title: string
  provider: string
  model: string
  created_at: string
  updated_at: string
}

export interface ConversationsResponse {
  total: number
  conversations: Conversation[]
}

export interface ConversationDetailResponse {
  conversation: Conversation
  messages: Message[]
  has_more: boolean
}

export async function getProviders(): Promise<ProvidersResponse> {
  const response = await fetch(`${API_URL}/providers`)

  if (!response.ok) {
    throw new Error('No fue posible consultar los proveedores.')
  }

  return response.json()
}

export async function getModels(provider: string): Promise<AIModel[]> {
  const response = await fetch(
    `${API_URL}/models?provider=${encodeURIComponent(provider)}`
  )

  if (!response.ok) {
    throw new Error('No fue posible consultar los modelos.')
  }

  const data: ModelsResponse = await response.json()
  return data.models
}

export async function sendMessage(
  request: ChatRequest
): Promise<ChatResponse> {
  const response = await fetch(`${API_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  })

  const data = await response.json()

  if (!response.ok) {
    throw new Error(data.detail || 'Error al comunicarse con el servidor')
  }

  return data as ChatResponse
}

export async function getConversations(
  limit = 25,
  offset = 0
): Promise<ConversationsResponse> {
  const response = await fetch(
    `${API_URL}/conversations?limit=${limit}&offset=${offset}`
  )

  if (!response.ok) {
    throw new Error('No fue posible cargar el historial.')
  }

  return response.json()
}

export async function getConversation(
  conversationId: string,
  limit = 50,
  beforeId?: number
): Promise<ConversationDetailResponse> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (beforeId !== undefined) params.set('before_id', String(beforeId))
  const response = await fetch(
    `${API_URL}/conversations/${encodeURIComponent(conversationId)}?${params}`
  )

  const data = await response.json()

  if (!response.ok) {
    throw new Error(data.detail || 'No fue posible recuperar la conversación.')
  }

  return data as ConversationDetailResponse
}
	
