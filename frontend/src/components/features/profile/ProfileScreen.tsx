'use client'

import { FormEvent, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { AuthCard } from '@/src/components/features/auth/AuthLayout'
import { ProfileCardSkeleton } from '@/src/components/features/loading/PlaybookLoaders'
import { BrandLockup, Button, Input } from '@/src/components/ui'
import { useCurrentUser } from '@/src/hooks/useAuth'
import { useUpdateProfile } from '@/src/hooks/useProfile'

export function ProfileScreen() {
  const router = useRouter()
  const { data: user, isLoading } = useCurrentUser()
  const updateProfile = useUpdateProfile()
  const [name, setName] = useState(user?.name ?? '')
  const [sportTeam, setSportTeam] = useState('')
  const initializedNameRef = useRef(Boolean(user?.name))

  useEffect(() => {
    if (!initializedNameRef.current && user?.name) {
      setName(user.name)
      initializedNameRef.current = true
    }
  }, [user?.name])

  if (isLoading) return <ProfileCardSkeleton />

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const response = await updateProfile.mutateAsync({
      name: name.trim(),
      sport_team: sportTeam.trim(),
      selected_role: 'athlete',
    })
    router.push(response.next_route)
  }

  return (
    <AuthCard className="flex flex-col items-center text-center">
      <BrandLockup
        className="justify-center gap-[11px]"
        markSize={34}
        wordmarkClassName="pb-auth-wordmark"
      />
      <h1 className="pb-auth-heading mt-6">
        Complete your profile
      </h1>
      <p className="pb-auth-copy mt-3 max-w-[28ch]">
        We just need a few more details before getting started.
      </p>
      <form className="pb-auth-profile-form" onSubmit={handleSubmit}>
        <label className="pb-auth-label pb-auth-profile-field">
          Name
          <Input
            className="pb-auth-profile-input"
            onChange={(event) => setName(event.target.value)}
            required
            value={name}
          />
        </label>
        <label className="pb-auth-label pb-auth-profile-field">
          Sport or team
          <Input
            className="pb-auth-profile-input"
            onChange={(event) => setSportTeam(event.target.value)}
            placeholder="Basketball"
            required
            value={sportTeam}
          />
        </label>
        {updateProfile.error && <p className="pb-auth-copy text-danger">{updateProfile.error.message}</p>}
        <Button
          className="pb-auth-profile-submit"
          disabled={updateProfile.isPending}
          size="lg"
          type="submit"
        >
          {"I'm ready"}
        </Button>
      </form>
    </AuthCard>
  )
}
