import { useAuth } from "./AuthContext";
import React from "react";
import { getToken } from "../../api/client";

export default function RequireRole({
  role,
  children,
}: {
  role: "clinician" | "admin";
  children: React.ReactNode;
}) {
  const { user } = useAuth();
  
  // Client-side guard only; backend is authoritative
  if (typeof window !== "undefined" && !getToken()) {
    return <p className="p-6">Please log in.</p>;
  }
  
  // Check role if we have user info
  if (user && user.role !== role && user.role !== "admin") {
    return <p className="p-6">You need {role} role to access this page.</p>;
  }
  
  return <>{children}</>;
}