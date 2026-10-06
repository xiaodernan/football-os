'use client'

import { useState } from 'react'
import { useAuth } from '@/lib/auth'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Loader2, Send, Bot, User, Sparkles } from 'lucide-react'

interface Message {
  role: 'user' | 'assistant'
  content: string
  confidence?: number
  citations?: Array<{ source?: string; quote?: string }>
  from_cache?: boolean
}

const AGENT_TYPES = [
  { value: 'research', label: 'Research Agent', description: 'Football knowledge & RAG' },
  { value: 'coach', label: 'Coach Agent', description: 'Training plans & drills' },
  { value: 'tactical', label: 'Tactical Agent', description: 'Formations & tactics' },
  { value: 'scout', label: 'Scout Agent', description: 'Player search & analysis' },
  { value: 'simulation', label: 'Simulation Agent', description: 'Match engine explanations' },
  { value: 'video', label: 'Video Agent', description: 'Video pipeline guidance' },
]

export default function AgentsPage() {
  const { isAuthenticated } = useAuth()
  const [agentType, setAgentType] = useState('research')
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sendMessage = async () => {
    if (!query.trim() || !isAuthenticated) return

    const userMessage: Message = { role: 'user', content: query }
    setMessages(prev => [...prev, userMessage])
    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/v1/agents/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify({
          query: query,
          agent_type: agentType,
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      const assistantMessage: Message = {
        role: 'assistant',
        content: data.answer,
        confidence: data.confidence,
        citations: data.citations,
        from_cache: data.from_cache,
      }
      setMessages(prev => [...prev, assistantMessage])
      setQuery('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message')
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  if (!isAuthenticated) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-2xl">
        <Card>
          <CardHeader>
            <CardTitle>AI Football Agents</CardTitle>
            <CardDescription>Sign in to chat with specialized football AI agents</CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">AI Football Agents</h1>
        <p className="text-muted-foreground">
          Chat with specialized AI agents trained on football knowledge, tactics, coaching, and more.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-[300px_1fr]">
        {/* Sidebar - Agent Selection */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Select Agent</CardTitle>
            <CardDescription>Choose a specialized agent</CardDescription>
          </CardHeader>
          <CardContent>
            <Select value={agentType} onValueChange={setAgentType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {AGENT_TYPES.map(agent => (
                  <SelectItem key={agent.value} value={agent.value}>
                    <div>
                      <div className="font-medium">{agent.label}</div>
                      <div className="text-xs text-muted-foreground">{agent.description}</div>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        {/* Main Chat Area */}
        <Card className="flex flex-col h-[600px]">
          <CardHeader className="border-b">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Bot className="h-5 w-5" />
                  {AGENT_TYPES.find(a => a.value === agentType)?.label}
                </CardTitle>
                <CardDescription>
                  {AGENT_TYPES.find(a => a.value === agentType)?.description}
                </CardDescription>
              </div>
              {messages.length > 0 && (
                <Badge variant="outline">{messages.length} messages</Badge>
              )}
            </div>
          </CardHeader>

          <ScrollArea className="flex-1 p-4">
            <div className="space-y-4">
              {messages.length === 0 && (
                <div className="text-center text-muted-foreground py-12">
                  <Sparkles className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>Start a conversation with the {AGENT_TYPES.find(a => a.value === agentType)?.label.toLowerCase()}</p>
                  <p className="text-sm mt-2">Ask about football tactics, training, players, or match analysis</p>
                </div>
              )}

              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {msg.role === 'assistant' && (
                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                      <Bot className="h-4 w-4" />
                    </div>
                  )}

                  <div
                    className={`max-w-[80%] rounded-lg p-3 ${
                      msg.role === 'user'
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted'
                    }`}
                  >
                    <div className="whitespace-pre-wrap text-sm">{msg.content}</div>

                    {msg.role === 'assistant' && msg.confidence !== undefined && (
                      <div className="mt-2 text-xs opacity-70">
                        Confidence: {(msg.confidence * 100).toFixed(0)}%
                        {msg.from_cache && ' • Cached'}
                      </div>
                    )}

                    {msg.role === 'assistant' && msg.citations && msg.citations.length > 0 && (
                      <div className="mt-2 pt-2 border-t text-xs space-y-1">
                        <div className="font-semibold">Sources:</div>
                        {msg.citations.slice(0, 3).map((cit, i) => (
                          <div key={i} className="opacity-70">
                            {cit.source && `${cit.source}: `}
                            {cit.quote && `"${cit.quote.substring(0, 100)}..."`}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {msg.role === 'user' && (
                    <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
                      <User className="h-4 w-4 text-primary-foreground" />
                    </div>
                  )}
                </div>
              ))}

              {loading && (
                <div className="flex gap-3 justify-start">
                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                    <Loader2 className="h-4 w-4 animate-spin" />
                  </div>
                  <div className="bg-muted rounded-lg p-3">
                    <div className="text-sm text-muted-foreground">Thinking...</div>
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>

          {error && (
            <div className="px-4 py-2 text-sm text-destructive bg-destructive/10 border-t">
              {error}
            </div>
          )}

          <div className="border-t p-4">
            <div className="flex gap-2">
              <Textarea
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder={`Ask the ${AGENT_TYPES.find(a => a.value === agentType)?.label.toLowerCase()}...`}
                className="min-h-[60px] resize-none"
                disabled={loading}
              />
              <Button
                onClick={sendMessage}
                disabled={!query.trim() || loading}
                size="icon"
                className="self-end"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
