import React, { useState, useRef, useEffect } from "react";
import {
  MessageSquare,
  X,
  Send,
  RotateCcw,
  Sparkles,
  Database,
  ChevronDown,
  ChevronUp,
  Terminal,
} from "lucide-react";
import { sendChatMessage } from "../lib/api";

export const PREFILLED_PROMPTS = [
  "Why was the top option chosen?",
  "Show me historical weather disruptions for this location.",
  "What evidence supports Option A?",
];

export const INITIAL_MESSAGE = {
  id: "init",
  sender: "ai",
  text: "Hello! I am the Continuity Council's reasoning interface. Ask me anything about why recovery options were ranked, the historical ClickHouse evidence used, or constraint gates applied.",
  sources: [],
  timestamp: new Date(),
};

export const CouncilChatbot = ({ productionId = "prod_001", caseId = null }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([INITIAL_MESSAGE]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [expandedSource, setExpandedSource] = useState(null);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    if (typeof messagesEndRef.current?.scrollIntoView === "function") {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
      inputRef.current?.focus();
    }
  }, [isOpen, messages, loading]);

  const handleSend = async (textToSend) => {
    const query = (textToSend || input).trim();
    if (!query || loading) return;

    const userMsg = {
      id: `user_${Date.now()}`,
      sender: "user",
      text: query,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await sendChatMessage({
        message: query,
        production_id: productionId,
        case_id: caseId,
      });

      const aiMsg = {
        id: `ai_${Date.now()}`,
        sender: "ai",
        text: res?.answer || "No response received from Council Reasoning.",
        sources: res?.sources || [],
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, aiMsg]);
    } catch (err) {
      const errorMsg = {
        id: `err_${Date.now()}`,
        sender: "ai",
        text:
          err?.response?.data?.detail ||
          err?.message ||
          "Sorry, an error occurred while querying council reasoning.",
        sources: [],
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClearChat = () => {
    setMessages([INITIAL_MESSAGE]);
    setExpandedSource(null);
  };

  // Helper to render simple markdown formatting
  const renderFormattedText = (text) => {
    if (!text) return null;
    const lines = text.split("\n");
    return lines.map((line, idx) => {
      // Bold rendering **text**
      const parts = line.split(/(\*\*.*?\*\*)/g);
      const formattedLine = parts.map((part, pIdx) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong key={pIdx} className="font-semibold text-[var(--cc-text-primary)]">
              {part.slice(2, -2)}
            </strong>
          );
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code
              key={pIdx}
              className="rounded bg-[var(--cc-surface-sunken)] border border-[var(--cc-border)] px-1 py-0.5 font-mono text-[11px] text-[var(--cc-text-secondary)]"
            >
              {part.slice(1, -1)}
            </code>
          );
        }
        return part;
      });

      if (line.startsWith("- ") || line.startsWith("* ")) {
        return (
          <li key={idx} className="ml-4 list-disc text-[12.5px] leading-relaxed">
            {formattedLine}
          </li>
        );
      }

      if (/^\d+\.\s/.test(line)) {
        return (
          <li key={idx} className="ml-4 list-decimal text-[12.5px] leading-relaxed">
            {formattedLine}
          </li>
        );
      }

      if (!line.trim()) {
        return <div key={idx} className="h-2" />;
      }

      return (
        <p key={idx} className="text-[12.5px] leading-relaxed">
          {formattedLine}
        </p>
      );
    });
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      {/* Slide-in Drawer Window */}
      {isOpen && (
        <div
          role="dialog"
          aria-label="Council Reasoning Chatbot"
          className="mb-3 flex h-[560px] max-h-[82vh] w-[400px] max-w-[calc(100vw-2rem)] flex-col rounded-[18px] border border-[var(--cc-border)] bg-[var(--cc-surface-elevated)] shadow-[var(--cc-shadow-lg)] backdrop-blur-xl transition-all duration-200"
          style={{ animation: "scaleUp 0.18s cubic-bezier(0.16, 1, 0.3, 1)" }}
        >
          {/* Drawer Header */}
          <div className="flex items-center justify-between border-b border-[var(--cc-border)] px-4 py-3 bg-[var(--cc-surface)]/80 rounded-t-[18px]">
            <div className="flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--cc-btn-primary-bg)] text-[var(--cc-btn-primary-text)]">
                <Sparkles size={14} />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-[13.5px] font-semibold text-[var(--cc-text-primary)]">
                    Council Reasoning
                  </h3>
                  <span className="inline-flex items-center gap-1 rounded-full bg-[var(--cc-green-bg)] px-2 py-0.5 text-[10.5px] font-medium text-[var(--cc-green-text)]">
                    <span className="h-1.5 w-1.5 rounded-full bg-[var(--cc-green-dot)] animate-pulse" />
                    MCP Live
                  </span>
                </div>
                <p className="text-[11px] text-[var(--cc-text-tertiary)]">
                  ClickHouse evidence & agent logic
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={handleClearChat}
                title="Clear Chat"
                className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--cc-text-tertiary)] hover:bg-[var(--cc-surface-hover)] hover:text-[var(--cc-text-primary)] transition-colors"
              >
                <RotateCcw size={13} />
              </button>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                title="Close Drawer"
                className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--cc-text-tertiary)] hover:bg-[var(--cc-surface-hover)] hover:text-[var(--cc-text-primary)] transition-colors"
              >
                <X size={15} />
              </button>
            </div>
          </div>

          {/* Messages Scroll Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3.5">
            {messages.map((msg, index) => (
              <div
                key={msg.id || index}
                className={`flex flex-col ${
                  msg.sender === "user" ? "items-end" : "items-start"
                }`}
              >
                <div
                  className={`relative rounded-[14px] px-3.5 py-2.5 ${
                    msg.sender === "user"
                      ? "bg-[var(--cc-btn-primary-bg)] text-[var(--cc-btn-primary-text)] max-w-[85%] rounded-tr-[4px]"
                      : "bg-[var(--cc-surface)] border border-[var(--cc-border)] text-[var(--cc-text-primary)] max-w-[92%] shadow-sm rounded-tl-[4px]"
                  }`}
                >
                  {renderFormattedText(msg.text)}

                  {/* Sources Footnotes */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-2.5 pt-2 border-t border-[var(--cc-border)] space-y-1.5">
                      <div className="flex items-center gap-1 text-[10.5px] font-medium text-[var(--cc-text-tertiary)]">
                        <Database size={11} />
                        <span>ClickHouse Evidence Sources:</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {msg.sources.map((src, sIdx) => {
                          const isExp = expandedSource === `${msg.id}_${sIdx}`;
                          return (
                            <button
                              key={sIdx}
                              type="button"
                              onClick={() =>
                                setExpandedSource(isExp ? null : `${msg.id}_${sIdx}`)
                              }
                              className="inline-flex items-center gap-1 rounded-md border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] px-2 py-1 text-[11px] text-[var(--cc-text-secondary)] hover:bg-[var(--cc-surface-hover)] transition-colors"
                            >
                              <span className="font-mono text-[10px]">[{sIdx + 1}]</span>
                              <span className="truncate max-w-[200px]">
                                {src.type === "mcp_query" ? "MCP Query" : "Source"}
                              </span>
                              {isExp ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                            </button>
                          );
                        })}
                      </div>

                      {/* Expanded Source Details */}
                      {msg.sources.map((src, sIdx) => {
                        const isExp = expandedSource === `${msg.id}_${sIdx}`;
                        if (!isExp) return null;
                        return (
                          <div
                            key={`detail_${sIdx}`}
                            className="mt-1.5 rounded-lg border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] p-2 text-[11px] text-[var(--cc-text-secondary)] animate-fadeIn"
                          >
                            <div className="mb-1 font-semibold text-[var(--cc-text-primary)]">
                              Result Summary:
                            </div>
                            <p className="mb-1.5 text-[11px] leading-snug">
                              {src.result_summary}
                            </p>
                            {src.query && (
                              <div className="mt-1">
                                <div className="flex items-center gap-1 text-[10px] font-mono text-[var(--cc-text-tertiary)] mb-0.5">
                                  <Terminal size={10} />
                                  <span>SQL Execution:</span>
                                </div>
                                <pre className="overflow-x-auto rounded bg-[var(--cc-surface)] p-1.5 font-mono text-[10px] text-[var(--cc-text-primary)] border border-[var(--cc-border)]">
                                  {src.query}
                                </pre>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                <span className="mt-1 px-1 text-[9.5px] text-[var(--cc-text-quaternary)]">
                  {new Date(msg.timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
            ))}

            {/* Typing Indicator */}
            {loading && (
              <div className="flex items-start">
                <div className="rounded-[14px] rounded-tl-[4px] bg-[var(--cc-surface)] border border-[var(--cc-border)] px-4 py-3 shadow-sm">
                  <div className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-[var(--cc-text-tertiary)] animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="h-2 w-2 rounded-full bg-[var(--cc-text-tertiary)] animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="h-2 w-2 rounded-full bg-[var(--cc-text-tertiary)] animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              </div>
            )}

            {/* Pre-filled Prompt Chips (Shown when only initial message exists) */}
            {messages.length === 1 && !loading && (
              <div className="pt-2 space-y-1.5">
                <div className="px-1 text-[11px] font-medium text-[var(--cc-text-tertiary)]">
                  Suggested questions:
                </div>
                <div className="flex flex-col gap-1.5">
                  {PREFILLED_PROMPTS.map((prompt, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => handleSend(prompt)}
                      className="text-left rounded-xl border border-[var(--cc-border)] bg-[var(--cc-surface)] px-3 py-2 text-[12px] text-[var(--cc-text-primary)] hover:border-[var(--cc-border-strong)] hover:bg-[var(--cc-surface-hover)] transition-all shadow-xs"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Chat Input Bar */}
          <div className="border-t border-[var(--cc-border)] p-3 bg-[var(--cc-surface)]/80 rounded-b-[18px]">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="flex items-center gap-2"
            >
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about option ranking or ClickHouse data..."
                disabled={loading}
                className="flex-1 rounded-full border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] px-3.5 py-2 text-[12.5px] text-[var(--cc-text-primary)] placeholder-[var(--cc-text-quaternary)] focus:border-[var(--cc-text-primary)] focus:outline-none transition-colors"
              />
              <button
                type="submit"
                disabled={!input.trim() || loading}
                className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--cc-btn-primary-bg)] text-[var(--cc-btn-primary-text)] hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm shrink-0"
              >
                <Send size={13} className="translate-x-[1px]" />
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Floating Action Button (FAB) */}
      <button
        type="button"
        id="council-chatbot-fab"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-label={isOpen ? "Close Council Chat" : "Open Council Chat"}
        className={`group relative flex h-12 w-12 items-center justify-center rounded-full border border-[var(--cc-border)] bg-[var(--cc-surface-elevated)] text-[var(--cc-text-primary)] shadow-[var(--cc-shadow-lg)] hover:scale-105 active:scale-95 transition-all duration-150 backdrop-blur-md ${
          isOpen ? "ring-2 ring-[var(--cc-text-primary)]" : ""
        }`}
      >
        {isOpen ? (
          <X size={20} className="transition-transform duration-150" />
        ) : (
          <div className="relative">
            <Sparkles size={20} className="transition-transform group-hover:rotate-12 duration-150" />
            <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--cc-green-dot)] opacity-75" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[var(--cc-green-dot)]" />
            </span>
          </div>
        )}
      </button>
    </div>
  );
};
export default CouncilChatbot;
