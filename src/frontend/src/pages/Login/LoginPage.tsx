import React from "react";
import { LoginForm } from "@/features/auth/components/LoginForm";

export const LoginPage: React.FC = () => {
  return (
    <div className="min-h-screen w-full flex items-center justify-center relative overflow-hidden bg-slate-50 p-4">
      {/* Decorative Radial Grid Pattern Background */}
      <div
        className="absolute inset-0 z-0 opacity-40 pointer-events-none"
        style={{
          backgroundImage: `radial-gradient(rgba(0, 209, 193, 0.2) 1px, transparent 1px)`,
          backgroundSize: "24px 24px",
        }}
      />

      {/* Decorative Blur Spots */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-[#00D1C1]/10 blur-[100px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-[#006a62]/10 blur-[100px] pointer-events-none" />

      {/* Centered Login Form Card */}
      <LoginForm />
    </div>
  );
};
