import React, { useEffect } from 'react';

const TrainingModal = ({
    show,
    onClose,
    modelInfo,
    trainingStatus,
    loadTrainingStatus,
    startTraining
}) => {

    useEffect(() => {
        if (show) {
            loadTrainingStatus();
        }
    }, [show, loadTrainingStatus]);

    if (!show) return null;

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h2>🧠 Model Training</h2>
                    <button className="close-button" onClick={onClose}>&times;</button>
                </div>

                <div className="modal-body">
                    <div className="status-item">
                        <span className="status-label">Current Model:</span>
                        <span className="status-value">{modelInfo?.model_name || "Unknown"}</span>
                    </div>

                    <div className="status-item">
                        <span className="status-label">Training Status:</span>
                        <span className={`status-value ${trainingStatus?.status || ''}`}>
                            {trainingStatus?.status || "Idle"}
                        </span>
                    </div>

                    {trainingStatus?.created_at && (
                        <div className="status-item">
                            <span className="status-label">Last Run:</span>
                            <span className="status-value">{new Date(trainingStatus.created_at).toLocaleString()}</span>
                        </div>
                    )}

                    {trainingStatus?.status === 'training' && (
                        <div style={{ textAlign: 'center', marginTop: '1rem', color: '#667eea' }}>
                            Running auto-training... This may take a while.
                        </div>
                    )}
                </div>

                <div className="modal-footer">
                    <button className="refresh-button" onClick={loadTrainingStatus}>
                        🔄 Refresh
                    </button>
                    <button
                        className="train-button"
                        onClick={startTraining}
                        disabled={trainingStatus?.status === 'training'}
                    >
                        {trainingStatus?.status === 'training' ? "Training..." : "🚀 Start Training"}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default TrainingModal;
