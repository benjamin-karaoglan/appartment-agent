import { headers } from 'next/headers';
import RegisterForm from './RegisterForm';

export default async function RegisterPage() {
  // Reading headers forces dynamic rendering so env vars are read at runtime, not build time
  await headers();
  const googleAuthEnabled = !!(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET);

  return <RegisterForm googleAuthEnabled={googleAuthEnabled} />;
}
