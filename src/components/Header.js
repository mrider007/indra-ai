import React from 'react';

const Header = ({ isConnected, modelInfo, onOpenTraining }) => {
    return (
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
                    <button className="settings-button" onClick={onOpenTraining}>
                        ⚙️ Training
                    </button>
                </div>
            </div>
        </header>
    );
};

export default Header;
