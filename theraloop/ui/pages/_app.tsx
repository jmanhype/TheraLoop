import type { AppProps } from "next/app";
import "../styles/globals.css";
import React from "react";

export default function App({ Component, pageProps }: AppProps) {
  React.useEffect(() => {
    console.log("App mounted");
  }, []);
  
  return <Component {...pageProps} />;
}