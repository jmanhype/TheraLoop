import type { AppProps } from "next/app";
import "../styles/globals.css";
import { AuthProvider } from "../components/auth/AuthContext";
import ErrorBoundary from "../components/ErrorBoundary";

export default function App({ Component, pageProps }: AppProps) {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <Component {...pageProps} />
      </AuthProvider>
    </ErrorBoundary>
  );
}