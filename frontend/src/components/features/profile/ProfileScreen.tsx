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
        wordmarkClassName="text-[26px] leading-none tracking-normal"
      />
      <h1 className="mt-6 font-display text-lg font-bold leading-[1.2] tracking-normal text-fg-1">
        Complete your profile
      </h1>
      <p className="mt-3 max-w-[28ch] text-sm font-medium leading-5 text-fg-3">
        We just need a few more details before getting started.
      </p>
      <form className="mt-7 grid w-full gap-5 text-left" onSubmit={handleSubmit}>
        <label className="grid gap-2 text-sm font-semibold text-fg-2">
          Name
          <Input
            className="min-h-[52px] text-base"
            onChange={(event) => setName(event.target.value)}
            required
            value={name}
          />
        </label>
        <label className="grid gap-2 text-sm font-semibold text-fg-2">
          Sport or team
          <Input
            className="min-h-[52px] text-base"
            onChange={(event) => setSportTeam(event.target.value)}
            placeholder="Basketball"
            required
            value={sportTeam}
          />
        </label>
        {updateProfile.error && <p className="text-sm text-danger">{updateProfile.error.message}</p>}
        <Button
          className="min-h-[52px] w-full text-base"
          disabled={updateProfile.isPending}
          size="sm"
          type="submit"
        >
          {"I'm ready"}
        </Button>
      </form>
    </AuthCard>
  )
}
