import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas">
      <SignUp
        appearance={{
          elements: {
            formButtonPrimary: "bg-primary hover:bg-primary/90",
            card: "bg-card border border-edge shadow-lg",
          },
        }}
      />
    </div>
  );
}
