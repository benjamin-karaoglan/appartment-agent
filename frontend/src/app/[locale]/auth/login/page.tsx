import { cookies } from 'next/headers';
import LoginForm from './LoginForm';

export default function LoginPage() {
  // Reading cookies forces dynamic rendering so env vars are read at runtime, not build time
  cookies();
  const googleAuthEnabled = !!(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET);

  return <LoginForm googleAuthEnabled={googleAuthEnabled} />;
}
