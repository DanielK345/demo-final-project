export interface UserProfile {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  role: "CUSTOMER" | "OPERATOR" | "ADMIN" | "customer" | "driver" | "admin";
}

export interface AuthState {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}
