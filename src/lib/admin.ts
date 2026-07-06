export const ADMIN_EMAILS = [
  "alelemos02@gmail.com",
  "alexandre.nogueira@noglem.com.br",
  "admin@noglem.com.br",
];

export function isAdminEmail(email: string | null | undefined): boolean {
  return !!email && ADMIN_EMAILS.includes(email);
}
