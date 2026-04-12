-- Temporary dev user for testing without Google SSO
-- Remove this migration when auth is wired up

INSERT INTO auth.users (id, instance_id, email, encrypted_password, aud, role, created_at, updated_at, confirmation_token, email_confirmed_at)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000000',
  'dev@legoworlds.local',
  '',
  'authenticated',
  'authenticated',
  now(),
  now(),
  '',
  now()
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.profiles (id, display_name, role)
VALUES ('00000000-0000-0000-0000-000000000001', 'Jackson', 'creator')
ON CONFLICT (id) DO NOTHING;
