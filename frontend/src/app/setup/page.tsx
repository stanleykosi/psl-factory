import { redirect } from 'next/navigation';

// Rules is the Setup landing page until the Roles screen lands (F-11C).
export default function SetupPage() {
  redirect('/setup/rules');
}
