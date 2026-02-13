"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import axios from "axios"
import io from "socket.io-client"

import Header from "./components/Header"
import ChatInterface from "./components/ChatInterface"
import InputArea from "./components/InputArea"
import TrainingModal from "./components/TrainingModal"

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

  // Modal State
  const [showTrainingModal, setShowTrainingModal] = useState(false)
  const [trainingStatus, setTrainingStatus] = useState(null)

  const socketRef = useRef(null)

  // Initialization
  useEffect(() => {
    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    setSessionId(newSessionId)

    loadModelInfo()
    loadChatHistory(newSessionId)

    if (settings.useWebSocket) {
      setupWebSocket(newSessionId)
    }

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect()
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Re-connect WS if settings change
  useEffect(() => {
    if (settings.useWebSocket && !isConnected && sessionId) {
      setupWebSocket(sessionId)
    } else if (!settings.useWebSocket && isConnected) {
      socketRef.current?.disconnect()
    }
  }, [settings.useWebSocket, sessionId])

  const loadModelInfo = async () => {
    try {
      const response = await axios.get(`${API_URL}/model/info`)
      setModelInfo(response.data)
    } catch (error) {
      console.error("Failed to load model info:", error)
    }
  }

  const loadChatHistory = async (sid) => {
    try {
      const response = await axios.get(`${API_URL}/chat/history/${sid}`)
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
          inferenceTime: item.inference_time,
        },
      ])
      setMessages(history)
    } catch (error) {
      console.error("Failed to load chat history:", error)
    }
  }

  const setupWebSocket = (sid) => {
    const socket = io(`${WS_URL}/ws/${sid}`, {
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
      socketRef.current.emit(
        "message",
        JSON.stringify({
          message: inputMessage,
          max_length: settings.maxLength,
          temperature: settings.temperature,
        }),
      )
    } else {
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

  const clearChat = () => {
    setMessages([])
  }

  // --- Training Modal Logic ---

  const loadTrainingStatus = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/model/training/status`)
      setTrainingStatus(response.data)
    } catch (error) {
      console.error("Failed to load training status:", error)
    }
  }, [])

  const startTraining = async () => {
    try {
      await axios.post(`${API_URL}/model/train`)
      loadTrainingStatus()

      const interval = setInterval(async () => {
        const response = await axios.get(`${API_URL}/model/training/status`)
        setTrainingStatus(response.data)
        if (response.data.status === 'completed' || response.data.status === 'failed') {
          clearInterval(interval)
          loadModelInfo()
        }
      }, 5000)
    } catch (error) {
      console.error("Failed to start training:", error)
      alert("Failed to start training. " + (error.response?.data?.detail || error.message))
    }
  }

  return (
    <div className="app">
      <Header
        isConnected={isConnected}
        modelInfo={modelInfo}
        onOpenTraining={() => setShowTrainingModal(true)}
      />

      <main className="chat-container">
        <ChatInterface
          messages={messages}
          isLoading={isLoading}
        />

        <InputArea
          inputMessage={inputMessage}
          setInputMessage={setInputMessage}
          sendMessage={sendMessage}
          isLoading={isLoading}
          settings={settings}
          setSettings={setSettings}
          clearChat={clearChat}
        />
      </main>

      <TrainingModal
        show={showTrainingModal}
        onClose={() => setShowTrainingModal(false)}
        modelInfo={modelInfo}
        trainingStatus={trainingStatus}
        loadTrainingStatus={loadTrainingStatus}
        startTraining={startTraining}
      />
    </div>
  )
}

export default App
