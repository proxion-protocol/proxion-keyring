import React from 'react';

export const ViewContainer = ({ title, description, children, headerActions, style }) => {
    return (
        <div className="view-container" style={{ display: 'flex', flexDirection: 'column', height: '100%', ...style }}>
            <header className="view-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <div>
                    <h1>{title}</h1>
                    <p>{description}</p>
                </div>
                {headerActions && (
                    <div className="header-actions" style={{ display: 'flex', gap: '10px' }}>
                        {headerActions}
                    </div>
                )}
            </header>
            <div className="view-content" style={{ flex: 1, overflowY: 'auto' }}>
                {children}
            </div>
        </div>
    );
};
