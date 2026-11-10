
const API_URL = 'http://127.0.0.1:8000'

export interface ChatRequest {
  conversation_id: string | null
  message: string
  provider: string
  model: string
  strategy: 'manual' | 'free_first' | 'best_available'
  web_search: boolean
}

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

export async function getConversations(): Promise<Conversation[]> {
  const response = await fetch(`${API_URL}/conversations`)

  if (!response.ok) {
    throw new Error('No fue posible cargar el historial.')
  }

  const data: ConversationsResponse = await response.json()
  return data.conversations
}

export async function getConversation(
  conversationId: string
): Promise<ConversationDetailResponse> {
  const response = await fetch(
    `${API_URL}/conversations/${encodeURIComponent(conversationId)}`
  )

  const data = await response.json()

  if (!response.ok) {
    throw new Error(data.detail || 'No fue posible recuperar la conversación.')
  }

  return data as ConversationDetailResponse
}
	
