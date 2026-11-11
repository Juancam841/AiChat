
import { useEffect, useRef, useState, type FormEvent, type ChangeEvent } from 'react'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import {
  sendMessage,
  getProviders,
  getModels,
  getConversations,
  getConversation
} from './services/api'

import type {
  ChatResponse,
  ChatStrategy,
  AIModel,
  Conversation,
  Message
} from './services/api'

import './App.css'

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [webSearch, setWebSearch] = useState(false)

  // Referencia al contenedor de mensajes para controlar el autoscroll
  const chatMessagesRef = useRef<HTMLDivElement | null>(null)

  // Desplazar automáticamente hasta el último mensaje
  useEffect(() => {
    const container = chatMessagesRef.current

    if (container) {
      container.scrollTo({
        top: container.scrollHeight,
        behavior: 'smooth'
      })
    }
  }, [messages, loading])

  const [providers, setProviders] = useState<string[]>([])
  const [models, setModels] = useState<AIModel[]>([])
  const [provider, setProvider] = useState('')
  const [model, setModel] = useState('')
  const [strategy, setStrategy] = useState<ChatStrategy>('manual')
  const [catalogLoading, setCatalogLoading] = useState(true)

  const [conversations, setConversations] = useState<Conversation[]>([])
  const [conversationTotal, setConversationTotal] = useState(0)
  const [historyOffset, setHistoryOffset] = useState(0)
  const [historyLoading, setHistoryLoading] = useState(true)
  const historyPageSize = 25

  // Cargar proveedores y modelos
  useEffect(() => {
    async function loadCatalog() {
      try {
        const data = await getProviders()
        setProviders(data.available)

        if (data.available.length > 0) {
          const initialProvider = data.available[0]
          setProvider(initialProvider)

          const availableModels = await getModels(initialProvider)
          setModels(availableModels)

          if (availableModels.length > 0) {
            setModel(availableModels[0].id)
          }
        } else {
          setError('No hay proveedores configurados con modelos habilitados.')
        }
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'No fue posible cargar los modelos.'
        )
      } finally {
        setCatalogLoading(false)
      }
    }

    void loadCatalog()
  }, [])

  // Cargar historial de conversaciones
  async function loadHistory(offset = 0) {
    setHistoryLoading(true)
    try {
      const data = await getConversations(historyPageSize, offset)
      setConversations(data.conversations)
      setConversationTotal(data.total)
      setHistoryOffset(offset)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'No fue posible cargar el historial.'
      )
    } finally {
      setHistoryLoading(false)
    }
  }

  useEffect(() => {
    void loadHistory(0)
  }, [])

  // Cambiar proveedor
  async function handleProviderChange(
    event: ChangeEvent<HTMLSelectElement>
  ) {
    const selectedProvider = event.target.value

    setProvider(selectedProvider)
    setModel('')
    setModels([])
    setError('')

    try {
      const availableModels = await getModels(selectedProvider)
      setModels(availableModels)

      if (availableModels.length > 0) {
        setModel(availableModels[0].id)
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'No fue posible cargar los modelos.'
      )
    }
  }

  // Enviar mensaje
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const message = input.trim()

    if (!message || loading || !provider || !model) return

    setInput('')
    setError('')
    setLoading(true)

    setMessages(previous => [
      ...previous,
      { role: 'user', content: message }
    ])

    try {
      const result: ChatResponse = await sendMessage({
        conversation_id: conversationId,
        message,
        provider,
        model,
        strategy,
        web_search: webSearch
      })

      setConversationId(result.conversation_id)

      // Actualizar proveedor y modelo realmente utilizados
      if (result.provider !== provider) {
        try {
          const availableModels = await getModels(result.provider)
          setModels(availableModels)
        } catch (err) {
          console.error('No fue posible actualizar el catálogo:', err)
        }
      }

      setProvider(result.provider)
      setModel(result.model)

      setMessages(previous => [
        ...previous,
        { role: 'assistant', content: result.response, results: result.results }
      ])

      // Un fallo al refrescar el historial no invalida el mensaje ya guardado.
      try {
        const updatedHistory = await getConversations(historyPageSize, 0)
        setConversations(updatedHistory.conversations)
        setConversationTotal(updatedHistory.total)
        setHistoryOffset(0)
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'No fue posible actualizar el historial.'
        )
      }

    } catch (err) {
      // El mensaje optimista no se guardó en el servidor; retirarlo de la vista.
      setMessages(previous => previous.slice(0, -1))
      const errorMessage = err instanceof Error
        ? err.message
        : 'No fue posible comunicarse con el servidor.'

      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  // Abrir una conversación anterior
  async function openConversation(id: string) {
    if (loading) return

    setError('')

    try {
      const result = await getConversation(id)

      setConversationId(result.conversation.id)
      setMessages(result.messages)

      // Recuperar proveedor y modelo de la conversación
      const savedProvider = result.conversation.provider
      const savedModel = result.conversation.model

      setProvider(savedProvider)

      const availableModels = await getModels(savedProvider)
      setModels(availableModels)

      setModel(savedModel)
      setInput('')

    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'No fue posible abrir la conversación.'
      )
    }
  }

  // Crear conversación nueva
  function newConversation() {
    setMessages([])
    setConversationId(null)
    setInput('')
    setError('')
  }

  return (
    <div className="app-container">

      <aside className="sidebar">

        <div className="sidebar-header">
          <h2>Maris AI Chat</h2>
          <span>Multi-Model Platform</span>
        </div>

        <button
          className="new-chat-button"
          onClick={newConversation}
        >
          + Nueva conversación
        </button>

        <div className="history-section">

          <p className="section-title">HISTORIAL</p>

          {historyLoading ? (
            <p className="empty-history">
              Cargando conversaciones...
            </p>
          ) : conversations.length === 0 ? (
            <p className="empty-history">
              Todavía no tienes conversaciones.
            </p>
          ) : (
            <div className="history-list">
              {conversations.map(conversation => (
                <button
                  key={conversation.id}
                  className={`history-item ${
                    conversationId === conversation.id
                      ? 'active'
                      : ''
                  }`}
                  onClick={() => openConversation(conversation.id)}
                  disabled={loading}
                  title={conversation.title}
                >
                  <span className="history-item-title">
                    {conversation.title || 'Nueva conversación'}
                  </span>
                </button>
              ))}
            </div>
          )}

          {conversationTotal > historyPageSize && (
            <div className="history-pagination">
              <button
                onClick={() => void loadHistory(Math.max(0, historyOffset - historyPageSize))}
                disabled={historyLoading || historyOffset === 0}
                aria-label="Conversaciones anteriores"
              >
                Anterior
              </button>
              <span>
                {historyOffset + 1}–{Math.min(historyOffset + conversations.length, conversationTotal)} de {conversationTotal}
              </span>
              <button
                onClick={() => void loadHistory(historyOffset + historyPageSize)}
                disabled={historyLoading || historyOffset + historyPageSize >= conversationTotal}
                aria-label="Conversaciones siguientes"
              >
                Siguiente
              </button>
            </div>
          )}

        </div>

        <div className="sidebar-footer">
          <span>Configuración</span>
          <span>Perfil</span>
        </div>

      </aside>

      <main className="main-content">

        <header className="topbar">

          <h3>Mi espacio de trabajo</h3>

          <div className="model-selector">

            {/* Selector de estrategia */}
            <select
              value={strategy}
              onChange={event =>
                setStrategy(event.target.value as ChatStrategy)
              }
              disabled={loading}
            >
              <option value="manual">Manual</option>
              <option value="free_first">Gratis primero</option>
              <option value="best_available" title="Usa el orden de prioridad del catálogo de modelos">
                Mejor disponible
              </option>
            </select>

            {/* Selector de proveedor */}
            <select
              value={provider}
              onChange={handleProviderChange}
              disabled={
                strategy !== 'manual' ||
                catalogLoading ||
                providers.length === 0
              }
            >
              {providers.map(item => (
                <option key={item} value={item}>
                  {item.toUpperCase()}
                </option>
              ))}
            </select>

            {/* Selector de modelo */}
            <select
              value={model}
              onChange={event => setModel(event.target.value)}
              disabled={
                strategy !== 'manual' ||
                catalogLoading ||
                models.length === 0
              }
            >
              {models.map(item => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>

          </div>

        </header>

        <section className="chat-area">

          {messages.length === 0 ? (

            <div className="welcome-message">
              <h1>¿En qué puedo ayudarte?</h1>
              <p>
                Tu espacio de inteligencia artificial multimodelo.
                Elige un modelo y comienza una conversación.
              </p>
            </div>

          ) : (

            <div className="chat-messages" ref={chatMessagesRef}>

              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`message ${message.role}`}
                >
                  <strong>
                    {message.role === 'user' ? 'Tú' : 'AI'}
                  </strong>

                  {message.role === 'assistant' ? (
                    <>
                      <div className="markdown-content">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {message.content}
                        </ReactMarkdown>
                      </div>
                      {message.results && message.results.length > 0 && (
                        <div className="search-sources">
                          <strong>Fuentes</strong>
                          <ul>
                            {message.results.map((result, resultIndex) => (
                              <li key={`${result.url}-${resultIndex}`}>
                                {result.url ? (
                                  <a href={result.url} target="_blank" rel="noopener noreferrer">
                                    {result.title || result.url}
                                  </a>
                                ) : (result.title || 'Fuente')}
                                {result.published_date && <span> · {result.published_date}</span>}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </>
                  ) : (
                    <p>{message.content}</p>
                  )}
                </div>
              ))}

              {loading && (
                <div className="message assistant">
                  <strong>AI</strong>
                  <p>Generando respuesta...</p>
                </div>
              )}

              <div />

            </div>

          )}

        </section>

        <footer className="chat-input-area">

          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          <form
            className="chat-input-container"
            onSubmit={handleSubmit}
          >

            <textarea
              placeholder="Escribe tu mensaje..."
              rows={1}
              maxLength={24000}
              value={input}
              onChange={event => setInput(event.target.value)}
              disabled={loading}
            />

            <button
              className="send-button"
              type="submit"
              disabled={
                loading ||
                !input.trim() ||
                !provider ||
                !model
              }
            >
              ↑
            </button>

          </form>

          <label className="web-search-toggle">
            <input
              type="checkbox"
              checked={webSearch}
              onChange={event => setWebSearch(event.target.checked)}
              disabled={loading}
            />
            Buscar en la web
          </label>

          <p className="disclaimer">
            La inteligencia artificial puede cometer errores.
          </p>

        </footer>

      </main>

    </div>
  )
}

export default App

