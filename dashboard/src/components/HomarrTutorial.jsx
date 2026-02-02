import { useState } from 'react';

export const HomarrTutorial = ({ onClose }) => {
    const [step, setStep] = useState(0);

    const tutorialSteps = [
        {
            title: "Welcome to your Command Center",
            text: "You've installed your first apps! Now let's add them to your Homarr Dashboard for easy access.",
            image: "https://homarr.dev/img/screenshots/dashboard.webp" // Placeholder or actual screenshot
        },
        {
            title: "Step 1: Open Homarr",
            text: "Click the 'Open' button on the Homarr card in your App Library. It will open in your browser at http://localhost:7575.",
        },
        {
            title: "Step 2: Enter Edit Mode",
            text: "Once in Homarr, click the 'Edit' button in the top right corner. The grid will start to shimmer.",
        },
        {
            title: "Step 3: Add Widget",
            text: "Select 'Add Widget' -> 'Apps'. Choose the app you just installed (e.g., Mastodon or Jellyfin).",
        },
        {
            title: "Step 4: Live Status",
            text: "Integration with Proxion allows Homarr to show you live CPU/RAM and 'Up/Down' status for every app automatically.",
        }
    ];

    return (
        <div className="tutorial-overlay">
            <div className="tutorial-card">
                <button className="close-btn" onClick={onClose}>×</button>

                <div className="tutorial-content">
                    <h2>{tutorialSteps[step].title}</h2>
                    <p>{tutorialSteps[step].text}</p>

                    <div className="tutorial-dots">
                        {tutorialSteps.map((_, i) => (
                            <div key={i} className={`dot ${i === step ? 'active' : ''}`}></div>
                        ))}
                    </div>

                    <div className="tutorial-nav">
                        {step > 0 && <button className="btn-text" onClick={() => setStep(step - 1)}>Back</button>}
                        {step < tutorialSteps.length - 1 ? (
                            <button className="btn-primary" onClick={() => setStep(step + 1)}>Next</button>
                        ) : (
                            <button className="btn-primary" onClick={onClose}>Got it!</button>
                        )}
                    </div>
                </div>
            </div>

        </div>
    );
};
