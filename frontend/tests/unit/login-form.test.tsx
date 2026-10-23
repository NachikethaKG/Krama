import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LoginForm } from "@/components/auth/LoginForm";
import { ApiRequestError, MockApiClient } from "@/lib/api";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    refresh: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams({ from: "/dashboard" }),
}));

describe("LoginForm Component Suite", () => {
  it("renders email, password inputs, submit button, and seeded credentials helper", () => {
    render(<LoginForm client={new MockApiClient()} />);

    expect(screen.getByRole("heading", { name: /Sign in to Krama/i })).toBeInTheDocument();
    expect(screen.getByTestId("login-email")).toBeInTheDocument();
    expect(screen.getByTestId("login-password")).toBeInTheDocument();
    expect(screen.getByTestId("login-submit")).toBeInTheDocument();
    expect(screen.getByTestId("use-demo-creds-btn")).toBeInTheDocument();
    expect(screen.getByText(/demo@krama.dev/)).toBeInTheDocument();
  });

  it("pre-fills demo credentials when clicking 'Fill credentials'", () => {
    render(<LoginForm client={new MockApiClient()} />);

    const fillBtn = screen.getByTestId("use-demo-creds-btn");
    fireEvent.click(fillBtn);

    expect(screen.getByTestId("login-email")).toHaveValue("demo@krama.dev");
    expect(screen.getByTestId("login-password")).toHaveValue("krama-demo-pass");
  });

  it("validates empty submission and prevents API call", () => {
    const client = new MockApiClient();
    const loginSpy = vi.spyOn(client, "login");

    render(<LoginForm client={client} />);

    const submitBtn = screen.getByTestId("login-submit");
    fireEvent.click(submitBtn);

    expect(screen.getByRole("alert")).toHaveTextContent(/Please enter both email and password/i);
    expect(loginSpy).not.toHaveBeenCalled();
  });

  it("submits valid credentials and calls onSuccess callback", async () => {
    const client = new MockApiClient();
    const loginSpy = vi.spyOn(client, "login");
    const onSuccess = vi.fn();

    render(<LoginForm client={client} onSuccess={onSuccess} />);

    fireEvent.change(screen.getByTestId("login-email"), { target: { value: "demo@krama.dev" } });
    fireEvent.change(screen.getByTestId("login-password"), { target: { value: "krama-demo-pass" } });

    fireEvent.click(screen.getByTestId("login-submit"));

    await waitFor(() => {
      expect(loginSpy).toHaveBeenCalledWith({
        email: "demo@krama.dev",
        password: "krama-demo-pass",
      });
      expect(onSuccess).toHaveBeenCalledWith(
        expect.objectContaining({ email: "demo@krama.dev" }),
      );
    });
  });

  it("displays 401 error message when credentials are invalid", async () => {
    class FailingClient extends MockApiClient {
      override async login(): Promise<never> {
        throw new ApiRequestError("401 Unauthorized", 401, {
          code: "unauthorized",
          message: "Invalid email or password",
        });
      }
    }

    render(<LoginForm client={new FailingClient()} />);

    fireEvent.change(screen.getByTestId("login-email"), { target: { value: "wrong@krama.dev" } });
    fireEvent.change(screen.getByTestId("login-password"), { target: { value: "bad-password" } });

    fireEvent.click(screen.getByTestId("login-submit"));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/Invalid email or password/i);
  });
});
