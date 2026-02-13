import React, { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { dark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { format } from 'date-fns';

const ChatInterface = ({ messages, isLoading }) => {
    const messagesEndRef = useRef(null);

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

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
        );
    };

    return (
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
                                            const match = /language-(\w+)/.exec(className || "");
                                            return !inline && match ? (
                                                <CodeBlock language={match[1]} value={String(children).replace(/\n$/, "")} {...props} />
                                            ) : (
                                                <code className={className} {...props}>
                                                    {children}
                                                </code>
                                            );
                                        },
                                    }}
                                >
                                    {message.content}
                                </ReactMarkdown>
                            </div>
                        )}
                    </div>
                    <div className="message-meta">
                        <span className="timestamp">{format(new Date(message.timestamp), "HH:mm:ss")}</span>
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
    );
};

export default ChatInterface;
