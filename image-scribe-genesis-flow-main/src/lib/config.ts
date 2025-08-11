export const BACKEND_BASE_URL: string = (import.meta as ImportMeta).env.VITE_BACKEND_URL ?? "";
// Set this to your Supabase Functions URL, e.g. https://<project-ref>.functions.supabase.co
export const FUNCTIONS_BASE_URL: string = (import.meta as ImportMeta).env.VITE_SUPABASE_FUNCTIONS_URL ?? "";
