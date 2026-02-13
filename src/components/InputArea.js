import React from 'react';

const InputArea = ({
    inputMessage,
    setInputMessage,
    sendMessage,
    isLoading,
    settings,
    setSettings,
    clearChat
}) => {

    const handleKeyPress = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    return (
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
    );
};

export default InputArea;
