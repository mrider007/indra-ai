"use client"

import { useState, useEffect, useRef } from "react"
import axios from "axios"
import io from "socket.io-client"
import ReactMarkdown from "react-markdown"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { dark } from "react-syntax-highlighter/dist/esm/styles/prism"
import { format } from "date-fns"
import "./App.css"

const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000"
const WS_URL = process.env.REACT_APP_WS_URL || "ws://localhost:8000"

function App() {
  const [messages, setMessages] = useState([])
  const [inputMessage, setInputMessage] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isConnected, setIsConnected] = useState(false)
  const [sessionId, setSessionId] = useState("")
  const [modelInfo, setModelInfo] = useState(null)
  const [settings, setSettings] = useState({
    maxLength: 150,
    temperature: 0.7,
    useWebSocket: true,
  })

  const messagesEndRef = useRef(null)
  const socketRef = useRef(null)

  useEffect(() => {
    // Generate session ID
    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    setSessionId(newSessionId)

    // Load model info
    loadModelInfo()

    // Load chat history
    loadChatHistory(newSessionId)

    // Setup WebSocket connection
    if (settings.useWebSocket) {
      setupWebSocket(newSessionId)
    }

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect()
      }
    }
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  const loadModelInfo = async () => {
    try {
      const response = await axios.get(`${API_URL}/model/info`)
      setModelInfo(response.data)
    } catch (error) {
      console.error("Failed to load model info:", error)
    }
  }

  const loadChatHistory = async (sessionId) => {
    try {
      const response = await axios.get(`${API_URL}/chat/history/${sessionId}`)
      const history = response.data.flatMap((item) => [
        {
          type: "user",
          content: item.user_message,
          timestamp: new Date(item.timestamp),
        },
        {
          type: "bot",
          content: item.bot_response,
          timestamp: new Date(item.timestamp),
        },
      ])

      setMessages(history)
    } catch (error) {
      console.error("Failed to load chat history:", error)
    }
  }

  const setupWebSocket = (sessionId) => {
    const socket = io(`${WS_URL}/ws/${sessionId}`, {
      transports: ["websocket"],
    })

    socket.on("connect", () => {
      setIsConnected(true)
      console.log("WebSocket connected")
    })

    socket.on("disconnect", () => {
      setIsConnected(false)
      console.log("WebSocket disconnected")
    })

    socket.on("message", (data) => {
      const response = JSON.parse(data)
      setMessages((prev) => [
        ...prev,
        {
          type: "bot",
          content: response.response,
          timestamp: new Date(response.timestamp),
          inferenceTime: response.inference_time,
        },
      ])
      setIsLoading(false)
    })

    socketRef.current = socket
  }

  const sendMessage = async () => {
    if (!inputMessage.trim()) return

    const userMessage = {
      type: "user",
      content: inputMessage,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)

    if (settings.useWebSocket && socketRef.current && isConnected) {
      // Send via WebSocket
      socketRef.current.emit(
        "message",
        JSON.stringify({
          message: inputMessage,
          max_length: settings.maxLength,
          temperature: settings.temperature,
        }),
      )
    } else {
      // Send via HTTP API
      try {
        const response = await axios.post(`${API_URL}/chat`, {
          message: inputMessage,
          session_id: sessionId,
          max_length: settings.maxLength,
          temperature: settings.temperature,
        })

        const botMessage = {
          type: "bot",
          content: response.data.response,
          timestamp: new Date(response.data.timestamp),
          inferenceTime: response.data.inference_time,
        }

        setMessages((prev) => [...prev, botMessage])
      } catch (error) {
        console.error("Failed to send message:", error)
        setMessages((prev) => [
          ...prev,
          {
            type: "error",
            content: "Failed to get response. Please try again.",
            timestamp: new Date(),
          },
        ])
      } finally {
        setIsLoading(false)
      }
    }

    setInputMessage("")
  }

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const clearChat = () => {
    setMessages([])
  }

  const CodeBlock = ({ language, value }) => {
    return (
      <SyntaxHighlighter
        language={language}
        style={dark}
        customStyle={{
          margin: "1rem 0",
          borderRadius: "8px",
        }}
      >
        {value}
      </SyntaxHighlighter>
    )
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <h1>🧠 Indra LLM</h1>
          <div className="status-indicators">
            <div className={`status-indicator ${isConnected ? "connected" : "disconnected"}`}>
              {isConnected ? "🟢 Connected" : "🔴 Disconnected"}
            </div>
            {modelInfo && (
              <div className="model-info">
                📊 {modelInfo.model_name} ({(modelInfo.parameters / 1000000).toFixed(1)}M params)
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="chat-container">
        <div className="messages-container">
          {messages.map((message, index) => (
            <div key={index} className={`message ${message.type}`}>
              <div className="message-content">
                {message.type === "user" ? (
                  <div className="user-message">{message.content}</div>
                ) : message.type === "error" ? (
                  <div className="error-message">{message.content}</div>
                ) : (
                  <div className="bot-message">
                    <ReactMarkdown
                      components={{
                        code({ node, inline, className, children, ...props }) {
                          const match = /language-(\w+)/.exec(className || "")
                          return !inline && match ? (
                            <CodeBlock language={match[1]} value={String(children).replace(/\n$/, "")} {...props} />
                          ) : (
                            <code className={className} {...props}>
                              {children}
                            </code>
                          )
                        },
                      }}
                    >
                      {message.content}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
              <div className="message-meta">
                <span className="timestamp">{format(message.timestamp, "HH:mm:ss")}</span>
                {message.inferenceTime && (
                  <span className="inference-time">⚡ {message.inferenceTime.toFixed(2)}s</span>
                )}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="message bot">
              <div className="message-content">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-container">
          <div className="settings-bar">
            <label>
              Max Length:
              <input
                type="range"
                min="50"
                max="500"
                value={settings.maxLength}
                onChange={(e) => setSettings((prev) => ({ ...prev, maxLength: Number.parseInt(e.target.value) }))}
              />
              <span>{settings.maxLength}</span>
            </label>
            <label>
              Temperature:
              <input
                type="range"
                min="0.1"
                max="2.0"
                step="0.1"
                value={settings.temperature}
                onChange={(e) => setSettings((prev) => ({ ...prev, temperature: Number.parseFloat(e.target.value) }))}
              />
              <span>{settings.temperature}</span>
            </label>
            <label>
              <input
                type="checkbox"
                checked={settings.useWebSocket}
                onChange={(e) => setSettings((prev) => ({ ...prev, useWebSocket: e.target.checked }))}
              />
              WebSocket
            </label>
            <button onClick={clearChat} className="clear-button">
              🗑️ Clear
            </button>
          </div>

          <div className="message-input-container">
            <textarea
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your message here... (Press Enter to send, Shift+Enter for new line)"
              className="message-input"
              rows="3"
              disabled={isLoading}
            />
            <button onClick={sendMessage} disabled={isLoading || !inputMessage.trim()} className="send-button">
              {isLoading ? "⏳" : "🚀"}
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
