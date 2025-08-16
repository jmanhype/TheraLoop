import React from "react";

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
  errorInfo?: React.ErrorInfo;
}

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ComponentType<{error?: Error; resetError: () => void}>;
}

class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      error,
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
    
    // Log to external service in production
    this.logErrorToService(error, errorInfo);
    
    this.setState({
      error,
      errorInfo,
    });
  }

  logErrorToService = (error: Error, errorInfo: React.ErrorInfo) => {
    // In production, send to monitoring service
    const errorData = {
      message: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      timestamp: new Date().toISOString(),
      userAgent: typeof window !== "undefined" ? window.navigator.userAgent : "unknown",
      url: typeof window !== "undefined" ? window.location.href : "unknown",
    };
    
    // For now, just log to console
    console.error("TheraLoop Error:", errorData);
    
    // TODO: Send to monitoring service like Sentry, LogRocket, etc.
    // fetch('/api/errors', { method: 'POST', body: JSON.stringify(errorData) });
  };

  resetError = () => {
    this.setState({ hasError: false, error: undefined, errorInfo: undefined });
  };

  render() {
    if (this.state.hasError) {
      const FallbackComponent = this.props.fallback || DefaultErrorFallback;
      return <FallbackComponent error={this.state.error} resetError={this.resetError} />;
    }

    return this.props.children;
  }
}

// Default error fallback component
const DefaultErrorFallback: React.FC<{error?: Error; resetError: () => void}> = ({ 
  error, 
  resetError 
}) => {
  return (
    <div style={{
      maxWidth: 720,
      margin: "40px auto",
      padding: 24,
      border: "1px solid #fecaca",
      borderRadius: 12,
      background: "#fef2f2",
      fontFamily: "ui-sans-serif"
    }}>
      <h2 style={{ color: "#dc2626", marginTop: 0 }}>
        🚨 Something went wrong
      </h2>
      
      <p style={{ color: "#7f1d1d", marginBottom: 16 }}>
        We apologize for the technical difficulty. The error has been logged and our team will investigate.
      </p>
      
      {error && (
        <details style={{ 
          marginBottom: 16, 
          padding: 12, 
          background: "#ffffff", 
          borderRadius: 8,
          border: "1px solid #fca5a5"
        }}>
          <summary style={{ cursor: "pointer", fontWeight: "bold", color: "#dc2626" }}>
            Technical Details
          </summary>
          <pre style={{ 
            marginTop: 8, 
            fontSize: 12, 
            color: "#7f1d1d", 
            whiteSpace: "pre-wrap",
            wordBreak: "break-word"
          }}>
            {error.message}
            {(typeof window !== 'undefined' && 
              (window.location.hostname === 'localhost' || 
               window.location.hostname === '127.0.0.1' || 
               window.location.hostname.startsWith('192.168.') ||
               window.location.hostname.startsWith('10.'))) && (
              <>
                {"\n\n"}
                {error.stack}
              </>
            )}
          </pre>
        </details>
      )}
      
      <div style={{ display: "flex", gap: 12 }}>
        <button
          onClick={resetError}
          style={{
            padding: "10px 16px",
            background: "#dc2626",
            color: "white",
            border: "none",
            borderRadius: 8,
            cursor: "pointer",
            fontWeight: "bold"
          }}
        >
          Try Again
        </button>
        
        <button
          onClick={() => window.location.reload()}
          style={{
            padding: "10px 16px",
            background: "#6b7280",
            color: "white",
            border: "none",
            borderRadius: 8,
            cursor: "pointer"
          }}
        >
          Refresh Page
        </button>
      </div>
      
      <div style={{ 
        marginTop: 16, 
        padding: 12, 
        background: "#f0f9ff", 
        borderRadius: 8,
        border: "1px solid #7dd3fc"
      }}>
        <p style={{ margin: 0, fontSize: 14, color: "#0c4a6e" }}>
          <strong>Need immediate help?</strong><br />
          If you're experiencing a mental health crisis, please contact:
          <br />• 988 Suicide & Crisis Lifeline: 988
          <br />• Emergency Services: 911
          <br />• Crisis Text Line: Text HOME to 741741
        </p>
      </div>
    </div>
  );
};

export { ErrorBoundary, DefaultErrorFallback };
export default ErrorBoundary;